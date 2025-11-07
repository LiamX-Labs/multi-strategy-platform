"""
Position Reconciliation Utility
Handles syncing database state with exchange reality on bot startup
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from shared.alpha_db_client import AlphaDBClient

logger = logging.getLogger(__name__)


async def reconcile_positions_on_startup(
    bot_id: str,
    db_client: AlphaDBClient,
    exchange_client,
    redis_db: int = 0
):
    """
    Reconcile open position entries with actual exchange positions on startup.

    Handles positions that were closed while container was down by:
    1. Fetching current positions from exchange
    2. Comparing with open position_entries in database
    3. Backfilling exit data for positions closed on exchange
    4. Restoring Redis state for positions still open

    Args:
        bot_id: Bot identifier
        db_client: Alpha database client instance
        exchange_client: Exchange API client (with get_positions method)
        redis_db: Redis database number
    """
    logger.info(f"🔄 Starting position reconciliation for {bot_id}...")

    try:
        # Step 1: Get all open position entries from database
        db_positions = db_client.get_open_position_entries()

        if not db_positions:
            logger.info(f"✅ No open position entries in database")
            return

        logger.info(f"📊 Found {len(db_positions)} open position entries in database")

        # Step 2: Get actual positions from exchange
        try:
            exchange_positions = await exchange_client.get_positions()

            # Convert to dict keyed by symbol for easy lookup
            exchange_pos_map = {
                pos.get('symbol'): pos
                for pos in exchange_positions
                if float(pos.get('size', 0)) > 0
            }

            logger.info(f"📊 Found {len(exchange_pos_map)} actual positions on exchange")

        except Exception as e:
            logger.error(f"❌ Failed to fetch positions from exchange: {e}")
            logger.warning("⚠️ Cannot reconcile without exchange data - using database state only")
            # Restore all positions from database to Redis
            for db_pos in db_positions:
                _restore_position_to_redis(db_client, db_pos)
            return

        # Step 3: Group database entries by symbol
        db_symbols = {}
        for entry in db_positions:
            symbol = entry['symbol']
            if symbol not in db_symbols:
                db_symbols[symbol] = []
            db_symbols[symbol].append(entry)

        # Step 4: Reconcile each symbol
        for symbol, entries in db_symbols.items():
            if symbol in exchange_pos_map:
                # Position still exists on exchange - restore to Redis
                exchange_pos = exchange_pos_map[symbol]
                _restore_position_to_redis_from_exchange(
                    db_client, symbol, entries, exchange_pos
                )
                logger.info(f"✅ Restored {symbol}: {len(entries)} entries still open on exchange")

            else:
                # Position was closed while we were down - backfill exit data
                await _backfill_closed_position(
                    bot_id, db_client, exchange_client, symbol, entries
                )
                logger.warning(f"⚠️ {symbol}: Position closed while container down - backfilled exit data")

        logger.info(f"✅ Position reconciliation complete for {bot_id}")

    except Exception as e:
        logger.error(f"❌ Position reconciliation failed: {e}")
        raise


def _restore_position_to_redis_from_exchange(
    db_client: AlphaDBClient,
    symbol: str,
    entries: List[Dict],
    exchange_pos: Dict
):
    """
    Restore position to Redis using exchange data as source of truth.

    Calculates weighted average from database entries but uses
    exchange position size as the actual quantity.
    """
    try:
        # Calculate weighted average from database entries
        total_qty = sum(float(e['remaining_qty']) for e in entries)
        if total_qty == 0:
            return

        weighted_avg_price = sum(
            float(e['entry_price']) * float(e['remaining_qty'])
            for e in entries
        ) / total_qty

        # Get actual size from exchange
        exchange_size = float(exchange_pos.get('size', 0))
        exchange_side = exchange_pos.get('side', 'None')

        # Update Redis with weighted average entry price
        db_client.update_position_redis(
            symbol=symbol,
            size=exchange_size,
            side=exchange_side,
            avg_price=weighted_avg_price,
            unrealized_pnl=float(exchange_pos.get('unrealisedPnl', 0))
        )

        logger.info(f"  Restored {symbol} to Redis: {exchange_size} @ avg ${weighted_avg_price:.4f}")

    except Exception as e:
        logger.error(f"Failed to restore {symbol} to Redis: {e}")


async def _backfill_closed_position(
    bot_id: str,
    db_client: AlphaDBClient,
    exchange_client,
    symbol: str,
    entries: List[Dict]
):
    """
    Backfill exit data for positions that were closed while container was down.

    Fetches closed P&L from exchange and creates completed trade records.
    """
    try:
        # Fetch closed P&L data from exchange API
        # Note: This requires exchange to support closed P&L history
        closed_pnl_records = await exchange_client.get_pnl_history(limit=50)

        # Find the most recent close for this symbol
        symbol_close = None
        for record in closed_pnl_records:
            if record.get('symbol') == symbol:
                symbol_close = record
                break

        if not symbol_close:
            logger.warning(f"⚠️ Could not find closed P&L data for {symbol} on exchange")
            # Fallback: Close entries with estimated exit price (last known price)
            # This is not ideal but prevents orphaned entries
            total_qty = sum(float(e['remaining_qty']) for e in entries)

            # Mark all entries as closed (we don't know actual exit details)
            for entry in entries:
                db_client.pg_conn.cursor().execute("""
                    UPDATE trading.position_entries
                    SET remaining_qty = 0, status = 'closed'
                    WHERE entry_id = %s
                """, (entry['entry_id'],))
            db_client.pg_conn.commit()

            logger.warning(f"⚠️ Marked {len(entries)} entries as closed (no exit data available)")
            return

        # Extract exit data from exchange
        exit_price = float(symbol_close.get('avgExitPrice', 0))
        exit_qty = sum(float(e['remaining_qty']) for e in entries)
        exit_time_ms = int(symbol_close.get('updatedTime', 0))
        exit_time = datetime.fromtimestamp(exit_time_ms / 1000, tz=timezone.utc)

        # Close using FIFO matching
        completed_trades = db_client.close_position_fifo(
            symbol=symbol,
            exit_price=exit_price,
            close_qty=exit_qty,
            exit_time=exit_time,
            exit_reason='backfilled_close',
            exit_commission=0.0  # Unknown, use 0
        )

        logger.info(f"  Backfilled {len(completed_trades)} completed trades for {symbol}")

    except Exception as e:
        logger.error(f"Failed to backfill {symbol}: {e}")
        # Still mark as closed to prevent orphaned entries
        for entry in entries:
            try:
                with db_client.pg_conn.cursor() as cur:
                    cur.execute("""
                        UPDATE trading.position_entries
                        SET remaining_qty = 0, status = 'closed'
                        WHERE entry_id = %s
                    """, (entry['entry_id'],))
                db_client.pg_conn.commit()
            except:
                pass


def _restore_position_to_redis(
    db_client: AlphaDBClient,
    entry: Dict
):
    """
    Simple restore from database entry only (no exchange verification).
    Used as fallback when exchange is unavailable.
    """
    try:
        db_client.update_position_redis(
            symbol=entry['symbol'],
            size=float(entry['remaining_qty']),
            side='Buy',  # Assuming long for now
            avg_price=float(entry['entry_price']),
            unrealized_pnl=0.0
        )
    except Exception as e:
        logger.error(f"Failed to restore {entry['symbol']}: {e}")
