"""
Database operations for Trade Sync Service
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager

from config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)

logger = logging.getLogger(__name__)


class SyncDatabase:
    """Database manager for trade sync operations"""

    def __init__(self):
        self.conn_params = {
            'host': POSTGRES_HOST,
            'port': POSTGRES_PORT,
            'database': POSTGRES_DB,
            'user': POSTGRES_USER,
            'password': POSTGRES_PASSWORD
        }
        self.conn = None

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.conn_params)
            self.conn.autocommit = False
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Database operation failed: {str(e)}")
            raise
        finally:
            cursor.close()

    def insert_completed_trade(self, trade: Dict) -> bool:
        """
        Insert a completed trade with duplicate detection

        Returns:
            True if inserted, False if duplicate
        """
        query = """
            INSERT INTO trading.completed_trades (
                trade_id, bot_id, symbol,
                entry_order_id, entry_client_order_id, entry_side, entry_price, entry_qty,
                entry_time, entry_reason, entry_commission,
                exit_order_id, exit_client_order_id, exit_side, exit_price, exit_qty,
                exit_time, exit_reason, exit_commission,
                gross_pnl, net_pnl, pnl_pct, total_commission, holding_duration_seconds,
                source, synced_at
            ) VALUES (
                %(trade_id)s, %(bot_id)s, %(symbol)s,
                %(entry_order_id)s, %(entry_client_order_id)s, %(entry_side)s, %(entry_price)s, %(entry_qty)s,
                %(entry_time)s, %(entry_reason)s, %(entry_commission)s,
                %(exit_order_id)s, %(exit_client_order_id)s, %(exit_side)s, %(exit_price)s, %(exit_qty)s,
                %(exit_time)s, %(exit_reason)s, %(exit_commission)s,
                %(gross_pnl)s, %(net_pnl)s, %(pnl_pct)s, %(total_commission)s, %(holding_duration_seconds)s,
                %(source)s, NOW()
            )
            ON CONFLICT (trade_id) DO UPDATE SET
                synced_at = EXCLUDED.synced_at,
                source = CASE
                    WHEN trading.completed_trades.source = 'websocket' THEN 'websocket'
                    ELSE EXCLUDED.source
                END
            RETURNING (xmax = 0) AS inserted
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, trade)
                result = cursor.fetchone()
                was_inserted = result['inserted'] if result else False

                if was_inserted:
                    logger.info(f"Inserted new trade: {trade['trade_id']}")
                else:
                    logger.info(f"Trade already exists (duplicate): {trade['trade_id']}")

                return was_inserted
        except Exception as e:
            logger.error(f"Failed to insert trade {trade.get('trade_id')}: {str(e)}")
            raise

    def bulk_insert_completed_trades(self, trades: List[Dict]) -> tuple[int, int]:
        """
        Bulk insert completed trades with duplicate detection

        Returns:
            Tuple of (inserted_count, skipped_count)
        """
        if not trades:
            return 0, 0

        inserted_count = 0
        skipped_count = 0

        for trade in trades:
            try:
                was_inserted = self.insert_completed_trade(trade)
                if was_inserted:
                    inserted_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Failed to insert trade {trade.get('trade_id')}: {str(e)}")
                skipped_count += 1

        logger.info(f"Bulk insert complete: {inserted_count} inserted, {skipped_count} duplicates skipped")
        return inserted_count, skipped_count

    def create_sync_status(
        self,
        bot_id: str,
        sync_type: str,
        start_time: datetime,
        end_time: datetime
    ) -> int:
        """
        Create a new sync status record

        Returns:
            sync_status_id
        """
        query = """
            INSERT INTO trading.sync_status (
                bot_id, sync_type, start_time, end_time, status, sync_started_at
            ) VALUES (
                %s, %s, %s, %s, 'running', NOW()
            )
            ON CONFLICT (bot_id, sync_type, start_time, end_time) DO UPDATE SET
                status = 'running',
                sync_started_at = NOW(),
                sync_completed_at = NULL,
                error_message = NULL
            RETURNING id
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (bot_id, sync_type, start_time, end_time))
                result = cursor.fetchone()
                sync_id = result['id']
                logger.info(f"Created sync status record: {sync_id}")
                return sync_id
        except Exception as e:
            logger.error(f"Failed to create sync status: {str(e)}")
            raise

    def update_sync_status(
        self,
        sync_id: int,
        status: str,
        trades_synced: int = 0,
        error_message: Optional[str] = None
    ):
        """Update sync status record"""
        query = """
            UPDATE trading.sync_status SET
                status = %s,
                trades_synced = %s,
                error_message = %s,
                sync_completed_at = NOW(),
                duration_seconds = EXTRACT(EPOCH FROM (NOW() - sync_started_at))
            WHERE id = %s
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (status, trades_synced, error_message, sync_id))
                logger.info(f"Updated sync status {sync_id}: {status}, {trades_synced} trades")
        except Exception as e:
            logger.error(f"Failed to update sync status {sync_id}: {str(e)}")
            raise

    def get_last_sync_time(self, bot_id: str, sync_type: str) -> Optional[datetime]:
        """Get the end time of the last successful sync"""
        query = """
            SELECT end_time
            FROM trading.sync_status
            WHERE bot_id = %s
              AND sync_type = %s
              AND status = 'completed'
            ORDER BY end_time DESC
            LIMIT 1
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (bot_id, sync_type))
                result = cursor.fetchone()
                if result:
                    return result['end_time']
                return None
        except Exception as e:
            logger.error(f"Failed to get last sync time: {str(e)}")
            return None

    def get_completed_trades_count(self, bot_id: str) -> int:
        """Get count of completed trades for a bot"""
        query = """
            SELECT COUNT(*) as count
            FROM trading.completed_trades
            WHERE bot_id = %s
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (bot_id,))
                result = cursor.fetchone()
                return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Failed to get completed trades count: {str(e)}")
            return 0

    def get_sync_statistics(self, bot_id: Optional[str] = None) -> List[Dict]:
        """Get sync statistics"""
        query = """
            SELECT
                bot_id,
                sync_type,
                COUNT(*) as total_syncs,
                COUNT(*) FILTER (WHERE status = 'completed') as successful_syncs,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_syncs,
                SUM(trades_synced) as total_trades_synced,
                AVG(duration_seconds) as avg_duration_seconds,
                MAX(sync_completed_at) as last_sync_time
            FROM trading.sync_status
        """

        if bot_id:
            query += " WHERE bot_id = %s"
            params = (bot_id,)
        else:
            params = None

        query += """
            GROUP BY bot_id, sync_type
            ORDER BY bot_id, sync_type
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get sync statistics: {str(e)}")
            return []

    def get_recent_completed_trades(
        self,
        bot_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent completed trades for a bot"""
        query = """
            SELECT *
            FROM trading.completed_trades
            WHERE bot_id = %s
            ORDER BY exit_time DESC
            LIMIT %s
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, (bot_id, limit))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get recent completed trades: {str(e)}")
            return []

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result:
                    logger.info("Database connection test successful")
                    return True
            return False
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False
