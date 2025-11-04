#!/usr/bin/env python3
"""
Trade Sync Service - Main Entry Point
"""

import asyncio
import argparse
import logging
import sys
import signal
from pathlib import Path

from sync_service import TradeSyncService
from config import LOG_LEVEL, LOG_FILE

# Setup logging
def setup_logging(log_level: str, log_file: str = None):
    """Configure logging for the service"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Create formatters and handlers
    formatter = logging.Formatter(log_format, date_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handler (if specified)
    handlers = [console_handler]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers
    )

    # Reduce noise from libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


class ServiceRunner:
    """Runner for the trade sync service"""

    def __init__(self):
        self.service = TradeSyncService()
        self.running = False

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        self.service.stop_continuous_sync()

    async def run_backfill(self, months: int, bot_id: str = None):
        """Run backfill operation"""
        logger.info("=" * 60)
        logger.info("STARTING BACKFILL OPERATION")
        logger.info("=" * 60)

        # Test connections first
        if not await self.service.test_connection():
            logger.error("Connection test failed, aborting backfill")
            return False

        try:
            if bot_id:
                logger.info(f"Backfilling {bot_id} for last {months} months")
                matched, inserted = await self.service.backfill_bot(bot_id, months)
                logger.info(f"Backfill complete: {matched} matched, {inserted} inserted")
            else:
                logger.info(f"Backfilling all bots for last {months} months")
                results = await self.service.backfill_all_bots(months)

                logger.info("=" * 60)
                logger.info("BACKFILL RESULTS")
                logger.info("=" * 60)
                for bot, result in results.items():
                    if result['status'] == 'success':
                        logger.info(f"{bot}: {result['matched']} matched, {result['inserted']} inserted")
                    else:
                        logger.error(f"{bot}: FAILED - {result.get('error')}")

            return True

        except Exception as e:
            logger.error(f"Backfill failed: {str(e)}", exc_info=True)
            return False

    async def run_hourly_sync(self, bot_id: str = None):
        """Run single hourly sync operation"""
        logger.info("=" * 60)
        logger.info("STARTING HOURLY SYNC")
        logger.info("=" * 60)

        # Test connections first
        if not await self.service.test_connection():
            logger.error("Connection test failed, aborting sync")
            return False

        try:
            if bot_id:
                logger.info(f"Syncing {bot_id}")
                matched, inserted = await self.service.hourly_sync_bot(bot_id)
                logger.info(f"Sync complete: {matched} matched, {inserted} inserted")
            else:
                logger.info("Syncing all bots")
                results = await self.service.hourly_sync_all_bots()

                logger.info("=" * 60)
                logger.info("SYNC RESULTS")
                logger.info("=" * 60)
                for bot, result in results.items():
                    if result['status'] == 'success':
                        logger.info(f"{bot}: {result['matched']} matched, {result['inserted']} inserted")
                    else:
                        logger.error(f"{bot}: FAILED - {result.get('error')}")

            return True

        except Exception as e:
            logger.error(f"Hourly sync failed: {str(e)}", exc_info=True)
            return False

    async def run_continuous(self):
        """Run continuous sync loop"""
        logger.info("=" * 60)
        logger.info("STARTING CONTINUOUS SYNC SERVICE")
        logger.info("=" * 60)

        # Test connections first
        if not await self.service.test_connection():
            logger.error("Connection test failed, aborting")
            return False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.running = True

        try:
            await self.service.run_continuous_sync()
        except Exception as e:
            logger.error(f"Continuous sync failed: {str(e)}", exc_info=True)
            return False
        finally:
            logger.info("Service stopped")

        return True

    async def show_stats(self, bot_id: str = None):
        """Show sync statistics"""
        logger.info("=" * 60)
        logger.info("SYNC STATISTICS")
        logger.info("=" * 60)

        try:
            stats = await self.service.get_sync_stats(bot_id)

            # Completed trades count
            logger.info("\nCompleted Trades Count:")
            for bot, count in stats['completed_trades_count'].items():
                logger.info(f"  {bot}: {count:,} trades")

            # Sync statistics
            logger.info("\nSync History:")
            for stat in stats['sync_statistics']:
                logger.info(f"\n{stat['bot_id']} - {stat['sync_type']}:")
                logger.info(f"  Total syncs: {stat['total_syncs']}")
                logger.info(f"  Successful: {stat['successful_syncs']}")
                logger.info(f"  Failed: {stat['failed_syncs']}")
                logger.info(f"  Trades synced: {stat['total_trades_synced']:,}")
                logger.info(f"  Avg duration: {stat['avg_duration_seconds']:.2f}s")
                logger.info(f"  Last sync: {stat['last_sync_time']}")

            return True

        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}", exc_info=True)
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Trade Sync Service - Sync completed trades from Bybit API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run 3-month backfill for all bots
  python main.py backfill --months 3

  # Run backfill for specific bot
  python main.py backfill --months 3 --bot shortseller_001

  # Run single hourly sync
  python main.py sync

  # Run continuous sync service (hourly)
  python main.py run

  # Show statistics
  python main.py stats
        """
    )

    parser.add_argument(
        'command',
        choices=['backfill', 'sync', 'run', 'stats', 'test'],
        help='Command to execute'
    )

    parser.add_argument(
        '--months',
        type=int,
        default=3,
        help='Number of months to backfill (default: 3)'
    )

    parser.add_argument(
        '--bot',
        type=str,
        help='Specific bot ID to sync (default: all bots)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default=LOG_LEVEL,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--log-file',
        type=str,
        default=LOG_FILE,
        help='Log file path (default: /var/log/trade_sync_service/sync.log)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level, args.log_file)

    # Create runner
    runner = ServiceRunner()

    # Execute command
    try:
        if args.command == 'backfill':
            success = asyncio.run(runner.run_backfill(args.months, args.bot))
        elif args.command == 'sync':
            success = asyncio.run(runner.run_hourly_sync(args.bot))
        elif args.command == 'run':
            success = asyncio.run(runner.run_continuous())
        elif args.command == 'stats':
            success = asyncio.run(runner.show_stats(args.bot))
        elif args.command == 'test':
            service = TradeSyncService()
            success = asyncio.run(service.test_connection())
        else:
            parser.print_help()
            success = False

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
