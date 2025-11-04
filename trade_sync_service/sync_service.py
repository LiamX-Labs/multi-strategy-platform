"""
Trade Sync Service - Main service for syncing completed trades from Bybit
"""

import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone

from bybit_client import BybitSyncClient
from trade_matcher import TradeMatcher
from closed_pnl_mapper import ClosedPnLMapper
from database import SyncDatabase
from config import (
    REGISTERED_BOTS,
    BACKFILL_MONTHS,
    BACKFILL_BATCH_DAYS,
    HOURLY_SYNC_OVERLAP_HOURS,
    SYNC_INTERVAL_SECONDS,
    BOT_API_KEYS
)

logger = logging.getLogger(__name__)


class TradeSyncService:
    """Service for syncing completed trades from Bybit API to PostgreSQL"""

    def __init__(self):
        self.db = SyncDatabase()
        self.matcher = TradeMatcher()
        self.mapper = ClosedPnLMapper()
        self.is_running = False

    async def sync_time_range_closed_pnl(
        self,
        bot_id: str,
        start_time: datetime,
        end_time: datetime,
        sync_type: str = 'backfill'
    ) -> tuple[int, int]:
        """
        Sync trades using Bybit closed PnL endpoint (for backfill)

        This method fetches COMPLETED trades directly from Bybit.
        Since closed PnL doesn't include orderLinkId, we assign bot_id manually.

        Args:
            bot_id: Bot identifier
            start_time: Start of time range (timezone-aware)
            end_time: End of time range (timezone-aware)
            sync_type: Type of sync (default: 'backfill')

        Returns:
            Tuple of (matched_trades_count, inserted_count)
        """
        logger.info(f"Starting {sync_type} sync for {bot_id} using closed PnL: {start_time} to {end_time}")

        # Create sync status record
        sync_id = self.db.create_sync_status(bot_id, sync_type, start_time, end_time)

        try:
            # Convert to milliseconds for Bybit API
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            # Get bot-specific API credentials
            bot_creds = BOT_API_KEYS.get(bot_id, {})
            if not bot_creds:
                raise ValueError(f"No API credentials found for bot_id: {bot_id}")

            logger.info(f"Using API key for {bot_id}: {bot_creds['api_key'][:10]}...")

            # Fetch closed PnL (completed trades) from Bybit using bot-specific credentials
            async with BybitSyncClient(
                api_key=bot_creds.get('api_key'),
                api_secret=bot_creds.get('api_secret')
            ) as client:
                closed_pnl_records = await client.get_all_closed_pnl_in_range(
                    start_time=start_ms,
                    end_time=end_ms,
                    category='linear'
                )

            if not closed_pnl_records:
                logger.info(f"No closed PnL records found in time range")
                self.db.update_sync_status(sync_id, 'completed', 0)
                return 0, 0

            logger.info(f"Found {len(closed_pnl_records)} closed PnL records from Bybit API for {bot_id}")

            # Map closed PnL records to completed_trades schema
            # Pass bot_id since closed PnL doesn't include orderLinkId
            completed_trades = self.mapper.map_all(closed_pnl_records, bot_id)

            if not completed_trades:
                logger.info(f"No valid trades after mapping for {bot_id}")
                self.db.update_sync_status(sync_id, 'completed', 0)
                return 0, 0

            logger.info(f"Mapped {len(completed_trades)} completed trades from closed PnL records")

            # Insert into database
            inserted_count, skipped_count = self.db.bulk_insert_completed_trades(completed_trades)

            # Update sync status
            self.db.update_sync_status(sync_id, 'completed', inserted_count)

            logger.info(f"Sync completed for {bot_id}: {inserted_count} inserted, "
                       f"{skipped_count} skipped")

            return len(completed_trades), inserted_count

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg)
            self.db.update_sync_status(sync_id, 'failed', 0, error_msg)
            raise

    async def sync_time_range_executions(
        self,
        bot_id: str,
        start_time: datetime,
        end_time: datetime,
        sync_type: str = 'hourly'
    ) -> tuple[int, int]:
        """
        Sync trades using execution matching (for hourly sync)

        This method fetches individual executions and matches buy/sell pairs.
        Preserves orderLinkId for bot_id and entry/exit reasons.

        Args:
            bot_id: Bot identifier
            start_time: Start of time range (timezone-aware)
            end_time: End of time range (timezone-aware)
            sync_type: Type of sync (default: 'hourly')

        Returns:
            Tuple of (matched_trades_count, inserted_count)
        """
        logger.info(f"Starting {sync_type} sync for {bot_id} using executions: {start_time} to {end_time}")

        # Create sync status record
        sync_id = self.db.create_sync_status(bot_id, sync_type, start_time, end_time)

        try:
            # Convert to milliseconds for Bybit API
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            # Get bot-specific API credentials
            bot_creds = BOT_API_KEYS.get(bot_id, {})
            if not bot_creds:
                raise ValueError(f"No API credentials found for bot_id: {bot_id}")

            logger.info(f"Using API key for {bot_id}: {bot_creds['api_key'][:10]}...")

            # Fetch executions from Bybit using bot-specific credentials
            async with BybitSyncClient(
                api_key=bot_creds.get('api_key'),
                api_secret=bot_creds.get('api_secret')
            ) as client:
                executions = await client.get_all_executions_in_range(
                    start_time=start_ms,
                    end_time=end_ms,
                    category='linear'
                )

            if not executions:
                logger.info(f"No executions found in time range")
                self.db.update_sync_status(sync_id, 'completed', 0)
                return 0, 0

            # Filter executions for this bot (by parsing orderLinkId)
            bot_executions = []
            for exec in executions:
                order_link_id = exec.get('orderLinkId', '')
                if order_link_id.startswith(f"{bot_id}:"):
                    bot_executions.append(exec)

            logger.info(f"Found {len(bot_executions)} executions for {bot_id} "
                       f"out of {len(executions)} total executions")

            if not bot_executions:
                logger.info(f"No executions found for {bot_id}")
                self.db.update_sync_status(sync_id, 'completed', 0)
                return 0, 0

            # Match buy/sell executions into completed trades
            matched_trades = self.matcher.match_all_symbols(bot_executions)

            if not matched_trades:
                logger.info(f"No completed trades matched for {bot_id}")
                self.db.update_sync_status(sync_id, 'completed', 0)
                return 0, 0

            # Validate trades
            valid_trades = []
            for trade in matched_trades:
                is_valid, error = self.matcher.validate_trade(trade)
                if is_valid:
                    valid_trades.append(trade)
                else:
                    logger.warning(f"Invalid trade {trade.get('trade_id')}: {error}")

            logger.info(f"Validated {len(valid_trades)} out of {len(matched_trades)} matched trades")

            # Insert into database
            inserted_count, skipped_count = self.db.bulk_insert_completed_trades(valid_trades)

            # Update sync status
            self.db.update_sync_status(sync_id, 'completed', inserted_count)

            logger.info(f"Sync completed for {bot_id}: {inserted_count} inserted, "
                       f"{skipped_count} skipped")

            return len(matched_trades), inserted_count

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg)
            self.db.update_sync_status(sync_id, 'failed', 0, error_msg)
            raise

    async def backfill_bot(self, bot_id: str, months: int = BACKFILL_MONTHS):
        """
        Backfill historical trades for a bot

        Args:
            bot_id: Bot identifier
            months: Number of months to backfill
        """
        logger.info(f"Starting backfill for {bot_id}: last {months} months")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=months * 30)

        total_matched = 0
        total_inserted = 0

        # Process in daily batches to respect rate limits
        current_start = start_time
        batch_size = timedelta(days=BACKFILL_BATCH_DAYS)

        while current_start < end_time:
            current_end = min(current_start + batch_size, end_time)

            logger.info(f"Backfilling batch: {current_start.date()} to {current_end.date()}")

            try:
                # Use closed PnL endpoint for backfill (per-bot API call)
                matched, inserted = await self.sync_time_range_closed_pnl(
                    bot_id=bot_id,
                    start_time=current_start,
                    end_time=current_end,
                    sync_type='backfill'
                )

                total_matched += matched
                total_inserted += inserted

                logger.info(f"Batch complete: {matched} matched, {inserted} inserted")

            except Exception as e:
                logger.error(f"Batch failed for {current_start.date()}: {str(e)}")
                # Continue with next batch even if one fails

            current_start = current_end

            # Small delay between batches
            await asyncio.sleep(1)

        logger.info(f"Backfill complete for {bot_id}: {total_matched} total matched, "
                   f"{total_inserted} total inserted")

        return total_matched, total_inserted

    async def backfill_all_bots(self, months: int = BACKFILL_MONTHS):
        """Backfill all registered bots"""
        logger.info(f"Starting backfill for all bots: {REGISTERED_BOTS}")

        results = {}
        for bot_id in REGISTERED_BOTS:
            try:
                matched, inserted = await self.backfill_bot(bot_id, months)
                results[bot_id] = {
                    'status': 'success',
                    'matched': matched,
                    'inserted': inserted
                }
            except Exception as e:
                logger.error(f"Backfill failed for {bot_id}: {str(e)}")
                results[bot_id] = {
                    'status': 'failed',
                    'error': str(e)
                }

        return results

    async def hourly_sync_bot(self, bot_id: str):
        """
        Perform hourly sync for a bot

        Fetches trades from the last HOURLY_SYNC_OVERLAP_HOURS to ensure no gaps
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=HOURLY_SYNC_OVERLAP_HOURS)

        logger.info(f"Hourly sync for {bot_id}: last {HOURLY_SYNC_OVERLAP_HOURS} hours")

        try:
            # Use execution matching for hourly sync (preserves orderLinkId/reasons)
            matched, inserted = await self.sync_time_range_executions(
                bot_id=bot_id,
                start_time=start_time,
                end_time=end_time,
                sync_type='hourly'
            )

            logger.info(f"Hourly sync complete for {bot_id}: {matched} matched, {inserted} inserted")
            return matched, inserted

        except Exception as e:
            logger.error(f"Hourly sync failed for {bot_id}: {str(e)}")
            raise

    async def hourly_sync_all_bots(self):
        """Perform hourly sync for all registered bots"""
        logger.info(f"Starting hourly sync for all bots: {REGISTERED_BOTS}")

        results = {}
        for bot_id in REGISTERED_BOTS:
            try:
                matched, inserted = await self.hourly_sync_bot(bot_id)
                results[bot_id] = {
                    'status': 'success',
                    'matched': matched,
                    'inserted': inserted
                }
            except Exception as e:
                logger.error(f"Hourly sync failed for {bot_id}: {str(e)}")
                results[bot_id] = {
                    'status': 'failed',
                    'error': str(e)
                }

        return results

    async def run_continuous_sync(self):
        """Run continuous hourly sync loop"""
        logger.info("Starting continuous sync loop")
        self.is_running = True

        while self.is_running:
            try:
                logger.info("Running scheduled hourly sync")
                results = await self.hourly_sync_all_bots()

                # Log results
                for bot_id, result in results.items():
                    if result['status'] == 'success':
                        logger.info(f"{bot_id}: {result['matched']} matched, {result['inserted']} inserted")
                    else:
                        logger.error(f"{bot_id}: Failed - {result.get('error')}")

                # Wait for next sync interval
                logger.info(f"Waiting {SYNC_INTERVAL_SECONDS}s until next sync")
                await asyncio.sleep(SYNC_INTERVAL_SECONDS)

            except Exception as e:
                logger.error(f"Sync loop error: {str(e)}")
                # Wait before retrying
                await asyncio.sleep(60)

    def stop_continuous_sync(self):
        """Stop continuous sync loop"""
        logger.info("Stopping continuous sync loop")
        self.is_running = False

    async def test_connection(self) -> bool:
        """Test connections to Bybit API and database"""
        logger.info("Testing connections...")

        # Test database
        db_ok = self.db.test_connection()
        if not db_ok:
            logger.error("Database connection test failed")
            return False

        # Test Bybit API
        async with BybitSyncClient() as client:
            api_ok = await client.test_connection()
            if not api_ok:
                logger.error("Bybit API connection test failed")
                return False

        logger.info("All connection tests passed")
        return True

    async def get_sync_stats(self, bot_id: Optional[str] = None) -> Dict:
        """Get sync statistics"""
        stats = self.db.get_sync_statistics(bot_id)

        # Get completed trades count for each bot
        if bot_id:
            bots = [bot_id]
        else:
            bots = REGISTERED_BOTS

        trades_count = {}
        for bot in bots:
            trades_count[bot] = self.db.get_completed_trades_count(bot)

        return {
            'sync_statistics': stats,
            'completed_trades_count': trades_count
        }
