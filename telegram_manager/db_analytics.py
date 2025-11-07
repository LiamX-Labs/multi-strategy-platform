#!/usr/bin/env python3
"""
Database Analytics Module for Telegram Command Center - PRODUCTION VERSION
Queries the production fills-based schema (not the unified trades schema)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import redis
except ImportError:
    psycopg2 = None
    redis = None

logger = logging.getLogger(__name__)


class DatabaseAnalytics:
    """Analytics interface for PostgreSQL (fills-based) and Redis databases"""

    def __init__(self):
        """Initialize database connections"""
        self.pg_conn = None
        self.redis_client = None

        # PostgreSQL connection parameters
        # Connect directly to PostgreSQL (PgBouncer has DNS issues)
        self.pg_params = {
            'host': os.getenv('POSTGRES_HOST', 'trading_postgres'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'database': os.getenv('POSTGRES_DB', 'trading_db'),
            'user': os.getenv('POSTGRES_USER', 'trading_user'),
            'password': os.getenv('POSTGRES_PASSWORD', ''),
        }

        # Redis connection parameters
        self.redis_params = {
            'host': os.getenv('REDIS_HOST', 'redis'),
            'port': int(os.getenv('REDIS_PORT', 6379)),
            'password': os.getenv('REDIS_PASSWORD', ''),
            'db': 0,
            'decode_responses': True
        }

        self._connect()

    def _connect(self):
        """Establish database connections"""
        try:
            if psycopg2:
                self.pg_conn = psycopg2.connect(**self.pg_params)
                logger.info("✓ PostgreSQL connection established")
            else:
                logger.warning("psycopg2 not installed - PostgreSQL features disabled")

            if redis:
                self.redis_client = redis.Redis(**self.redis_params)
                self.redis_client.ping()
                logger.info("✓ Redis connection established")
            else:
                logger.warning("redis not installed - Redis features disabled")

        except Exception as e:
            logger.error(f"Database connection error: {e}")

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute PostgreSQL query and return results as list of dicts"""
        if not self.pg_conn:
            return []

        try:
            # Reconnect if connection is closed
            if self.pg_conn.closed:
                self._connect()

            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return []

    def get_portfolio_summary(self) -> Dict:
        """Get overall portfolio summary across all bots"""
        query = """
        SELECT
            COUNT(DISTINCT bot_id) as total_bots,
            SUM(current_equity) as total_equity,
            SUM(initial_capital) as total_capital,
            COUNT(*) FILTER (WHERE status = 'active') as active_bots,
            COUNT(*) FILTER (WHERE status = 'paused') as paused_bots
        FROM trading.bots;
        """

        result = self._execute_query(query)
        if result:
            return dict(result[0])
        return {}

    def get_bot_summary(self, bot_id: str = None) -> List[Dict]:
        """Get summary for specific bot or all bots"""
        if bot_id:
            query = """
            SELECT
                bot_id,
                bot_name,
                bot_type,
                status,
                initial_capital,
                current_equity,
                ROUND((current_equity - initial_capital) / initial_capital * 100, 2) as return_pct,
                last_heartbeat
            FROM trading.bots
            WHERE bot_id = %s;
            """
            params = (bot_id,)
        else:
            query = """
            SELECT
                bot_id,
                bot_name,
                bot_type,
                status,
                initial_capital,
                current_equity,
                ROUND((current_equity - initial_capital) / initial_capital * 100, 2) as return_pct,
                last_heartbeat
            FROM trading.bots
            ORDER BY bot_type, bot_id;
            """
            params = None

        return self._execute_query(query, params)

    def get_trading_summary(self, bot_id: str = None, days: int = 7) -> Dict:
        """
        Get trading summary from completed_trades table (Bybit API synced data)
        Falls back to trades_pnl view if completed_trades is empty
        """
        date_filter = datetime.now() - timedelta(days=days)

        if bot_id:
            # First try the new completed_trades table
            query = """
            SELECT
                bot_id,
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE net_pnl > 0) as winning_trades,
                COUNT(*) FILTER (WHERE net_pnl <= 0) as losing_trades,
                COUNT(*) as closed_trades,
                ROUND(SUM(net_pnl), 2) as total_pnl,
                ROUND(AVG(net_pnl), 2) as avg_pnl,
                ROUND(MAX(net_pnl), 2) as max_win,
                ROUND(MIN(net_pnl), 2) as max_loss,
                ROUND(SUM(total_commission), 2) as total_fees
            FROM trading.completed_trades
            WHERE bot_id = %s AND exit_time >= %s
            GROUP BY bot_id;
            """
            params = (bot_id, date_filter)
        else:
            query = """
            SELECT
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE net_pnl > 0) as winning_trades,
                COUNT(*) FILTER (WHERE net_pnl <= 0) as losing_trades,
                COUNT(*) as closed_trades,
                ROUND(SUM(net_pnl), 2) as total_pnl,
                ROUND(AVG(net_pnl), 2) as avg_pnl,
                ROUND(MAX(net_pnl), 2) as max_win,
                ROUND(MIN(net_pnl), 2) as max_loss,
                ROUND(SUM(total_commission), 2) as total_fees
            FROM trading.completed_trades
            WHERE exit_time >= %s;
            """
            params = (date_filter,)

        # Also get count of active fills (not yet closed)
        if bot_id:
            fills_query = """
            SELECT COUNT(*) FILTER (WHERE side = 'Buy') as open_trades
            FROM trading.fills f
            WHERE bot_id = %s AND exec_time >= %s
                AND NOT EXISTS (
                    SELECT 1 FROM trading.fills f2
                    WHERE f2.bot_id = f.bot_id
                        AND f2.symbol = f.symbol
                        AND f2.side = 'Sell'
                        AND f2.exec_time > f.exec_time
                );
            """
            fills_params = (bot_id, date_filter)
        else:
            fills_query = """
            SELECT COUNT(*) FILTER (WHERE side = 'Buy') as open_trades
            FROM trading.fills f
            WHERE exec_time >= %s
                AND NOT EXISTS (
                    SELECT 1 FROM trading.fills f2
                    WHERE f2.bot_id = f.bot_id
                        AND f2.symbol = f.symbol
                        AND f2.side = 'Sell'
                        AND f2.exec_time > f.exec_time
                );
            """
            fills_params = (date_filter,)

        result = self._execute_query(query, params)
        fills_result = self._execute_query(fills_query, fills_params)

        # Always count fills to show activity even if no completed trades
        if bot_id:
            total_fills_query = """
            SELECT COUNT(*) as fill_count
            FROM trading.fills
            WHERE bot_id = %s AND exec_time >= %s;
            """
            total_fills_params = (bot_id, date_filter)
        else:
            total_fills_query = """
            SELECT COUNT(*) as fill_count
            FROM trading.fills
            WHERE exec_time >= %s;
            """
            total_fills_params = (date_filter,)

        fills_count_result = self._execute_query(total_fills_query, total_fills_params)
        total_fills = fills_count_result[0].get('fill_count', 0) if fills_count_result else 0

        if result and result[0].get('total_trades'):
            summary = dict(result[0])
            # Add open trades count
            if fills_result:
                summary['open_trades'] = fills_result[0].get('open_trades', 0) or 0
            else:
                summary['open_trades'] = 0

            # Add filled_trades (same as total_trades for completed)
            summary['filled_trades'] = summary.get('total_trades', 0)

            # Calculate win rate
            if summary.get('closed_trades', 0) > 0:
                summary['win_rate'] = round(
                    (summary.get('winning_trades', 0) / summary['closed_trades']) * 100, 2
                )
            else:
                summary['win_rate'] = 0.0
            return summary
        else:
            # No completed trades, but show fills activity
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'closed_trades': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'max_win': 0,
                'max_loss': 0,
                'total_fees': 0,
                'open_trades': 0,
                'filled_trades': total_fills,  # Show fill activity
                'win_rate': 0.0
            }

    def get_active_positions(self, bot_id: str = None) -> List[Dict]:
        """Get all active positions from the positions table"""
        if bot_id:
            query = """
            SELECT
                bot_id,
                symbol,
                side,
                size,
                avg_entry_price,
                updated_at as opened_at
            FROM trading.positions
            WHERE bot_id = %s AND size > 0
            ORDER BY updated_at DESC;
            """
            params = (bot_id,)
        else:
            query = """
            SELECT
                bot_id,
                symbol,
                side,
                size,
                avg_entry_price,
                updated_at as opened_at
            FROM trading.positions
            WHERE size > 0
            ORDER BY bot_id, updated_at DESC;
            """
            params = None

        return self._execute_query(query, params)

    def get_recent_trades(self, bot_id: str = None, limit: int = 10) -> List[Dict]:
        """Get recent completed trades from completed_trades table"""
        if bot_id:
            query = """
            SELECT
                bot_id,
                symbol,
                entry_side as side,
                entry_time,
                exit_time,
                entry_price,
                exit_price,
                entry_qty as quantity,
                net_pnl as pnl_usd,
                pnl_pct,
                exit_reason,
                'filled' as status
            FROM trading.completed_trades
            WHERE bot_id = %s
            ORDER BY exit_time DESC
            LIMIT %s;
            """
            params = (bot_id, limit)
        else:
            query = """
            SELECT
                bot_id,
                symbol,
                entry_side as side,
                entry_time,
                exit_time,
                entry_price,
                exit_price,
                entry_qty as quantity,
                net_pnl as pnl_usd,
                pnl_pct,
                exit_reason,
                'filled' as status
            FROM trading.completed_trades
            ORDER BY exit_time DESC
            LIMIT %s;
            """
            params = (limit,)

        return self._execute_query(query, params)

    def get_daily_performance(self, bot_id: str = None, days: int = 7) -> List[Dict]:
        """Get daily performance from completed_trades table"""
        date_filter = datetime.now() - timedelta(days=days)

        if bot_id:
            query = """
            SELECT
                DATE(exit_time) as trade_date,
                COUNT(*) as trades,
                COUNT(*) FILTER (WHERE net_pnl > 0) as wins,
                COUNT(*) FILTER (WHERE net_pnl <= 0) as losses,
                ROUND(SUM(net_pnl), 2) as daily_pnl,
                ROUND(AVG(net_pnl), 2) as avg_pnl
            FROM trading.completed_trades
            WHERE bot_id = %s AND exit_time >= %s
            GROUP BY DATE(exit_time)
            ORDER BY trade_date DESC;
            """
            params = (bot_id, date_filter)
        else:
            query = """
            SELECT
                DATE(exit_time) as trade_date,
                COUNT(*) as trades,
                COUNT(*) FILTER (WHERE net_pnl > 0) as wins,
                COUNT(*) FILTER (WHERE net_pnl <= 0) as losses,
                ROUND(SUM(net_pnl), 2) as daily_pnl,
                ROUND(AVG(net_pnl), 2) as avg_pnl
            FROM trading.completed_trades
            WHERE exit_time >= %s
            GROUP BY DATE(exit_time)
            ORDER BY trade_date DESC;
            """
            params = (date_filter,)

        return self._execute_query(query, params)

    def get_exit_reason_breakdown(self, bot_id: str = None, days: int = 7) -> List[Dict]:
        """Get breakdown of exit reasons from completed_trades table"""
        date_filter = datetime.now() - timedelta(days=days)

        if bot_id:
            query = """
            SELECT
                exit_reason,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE net_pnl > 0) as wins,
                COUNT(*) FILTER (WHERE net_pnl <= 0) as losses,
                ROUND(SUM(net_pnl), 2) as total_pnl,
                ROUND(AVG(net_pnl), 2) as avg_pnl,
                ROUND(AVG(holding_duration_seconds) / 60, 2) as avg_holding_minutes
            FROM trading.completed_trades
            WHERE bot_id = %s AND exit_time >= %s
            GROUP BY exit_reason
            ORDER BY count DESC;
            """
            params = (bot_id, date_filter)
        else:
            query = """
            SELECT
                exit_reason,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE net_pnl > 0) as wins,
                COUNT(*) FILTER (WHERE net_pnl <= 0) as losses,
                ROUND(SUM(net_pnl), 2) as total_pnl,
                ROUND(AVG(net_pnl), 2) as avg_pnl,
                ROUND(AVG(holding_duration_seconds) / 60, 2) as avg_holding_minutes
            FROM trading.completed_trades
            WHERE exit_time >= %s
            GROUP BY exit_reason
            ORDER BY count DESC;
            """
            params = (date_filter,)

        return self._execute_query(query, params)

    def get_redis_stats(self) -> Dict:
        """Get Redis cache statistics"""
        if not self.redis_client:
            return {}

        try:
            info = self.redis_client.info()
            return {
                'total_keys': self.redis_client.dbsize(),
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'uptime_days': info.get('uptime_in_days', 0),
                'hit_rate': round(
                    (info.get('keyspace_hits', 0) /
                     (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1))) * 100, 2
                ) if info.get('keyspace_hits', 0) > 0 else 0.0
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {}

    def get_fills_count(self, bot_id: str = None, days: int = 7) -> Dict:
        """Get fill statistics (buy/sell activity)"""
        date_filter = datetime.now() - timedelta(days=days)

        if bot_id:
            query = """
            SELECT
                COUNT(*) as total_fills,
                COUNT(*) FILTER (WHERE side = 'Buy') as buy_fills,
                COUNT(*) FILTER (WHERE side = 'Sell') as sell_fills,
                ROUND(SUM(commission), 2) as total_fees,
                COUNT(DISTINCT symbol) as symbols_traded
            FROM trading.fills
            WHERE bot_id = %s AND exec_time >= %s;
            """
            params = (bot_id, date_filter)
        else:
            query = """
            SELECT
                COUNT(*) as total_fills,
                COUNT(*) FILTER (WHERE side = 'Buy') as buy_fills,
                COUNT(*) FILTER (WHERE side = 'Sell') as sell_fills,
                ROUND(SUM(commission), 2) as total_fees,
                COUNT(DISTINCT symbol) as symbols_traded
            FROM trading.fills
            WHERE exec_time >= %s;
            """
            params = (date_filter,)

        result = self._execute_query(query, params)
        if result:
            return dict(result[0])
        return {}

    def close(self):
        """Close database connections"""
        if self.pg_conn and not self.pg_conn.closed:
            self.pg_conn.close()
            logger.info("PostgreSQL connection closed")

        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis connection closed")


# Singleton instance
_analytics = None


def get_analytics() -> DatabaseAnalytics:
    """Get or create analytics instance"""
    global _analytics
    if _analytics is None:
        _analytics = DatabaseAnalytics()
    return _analytics
