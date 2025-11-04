#!/usr/bin/env python3
"""
Database Analytics Module for Telegram Command Center
Provides summary analytics from PostgreSQL and Redis for trading operations
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
    """Analytics interface for PostgreSQL and Redis databases"""

    def __init__(self):
        """Initialize database connections"""
        self.pg_conn = None
        self.redis_client = None

        # PostgreSQL connection parameters
        # Production uses pgbouncer (port 6432) for connection pooling
        # Fallback to direct postgres (port 5432) if pgbouncer not available
        self.pg_params = {
            'host': os.getenv('POSTGRES_HOST', 'pgbouncer'),  # Production default
            'port': int(os.getenv('POSTGRES_PORT', 6432)),     # PgBouncer port
            'database': os.getenv('POSTGRES_DB', 'trading_db'),
            'user': os.getenv('POSTGRES_USER', 'trading_user'),
            'password': os.getenv('POSTGRES_PASSWORD', ''),
        }

        # Redis connection parameters
        # Production uses trading_redis container
        self.redis_params = {
            'host': os.getenv('REDIS_HOST', 'redis'),  # Production default
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
        FROM trading.bots
        WHERE deployment_mode = 'live';
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
                max_positions,
                leverage_limit,
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
                max_positions,
                last_heartbeat
            FROM trading.bots
            WHERE deployment_mode = 'live'
            ORDER BY bot_type, bot_id;
            """
            params = None

        return self._execute_query(query, params)

    def get_trading_summary(self, bot_id: str = None, days: int = 7) -> Dict:
        """Get trading summary for the last N days"""
        date_filter = datetime.now() - timedelta(days=days)

        if bot_id:
            query = """
            SELECT
                bot_id,
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE status = 'filled') as filled_trades,
                COUNT(*) FILTER (WHERE exit_time IS NOT NULL) as closed_trades,
                COUNT(*) FILTER (WHERE exit_time IS NULL AND status = 'filled') as open_trades,
                COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
                COUNT(*) FILTER (WHERE pnl_usd <= 0 AND exit_time IS NOT NULL) as losing_trades,
                ROUND(SUM(pnl_usd), 2) as total_pnl,
                ROUND(AVG(pnl_usd) FILTER (WHERE exit_time IS NOT NULL), 2) as avg_pnl,
                ROUND(MAX(pnl_usd), 2) as max_win,
                ROUND(MIN(pnl_usd), 2) as max_loss,
                ROUND(SUM(fees), 2) as total_fees
            FROM trading.trades
            WHERE bot_id = %s AND entry_time >= %s
            GROUP BY bot_id;
            """
            params = (bot_id, date_filter)
        else:
            query = """
            SELECT
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE status = 'filled') as filled_trades,
                COUNT(*) FILTER (WHERE exit_time IS NOT NULL) as closed_trades,
                COUNT(*) FILTER (WHERE exit_time IS NULL AND status = 'filled') as open_trades,
                COUNT(*) FILTER (WHERE pnl_usd > 0) as winning_trades,
                COUNT(*) FILTER (WHERE pnl_usd <= 0 AND exit_time IS NOT NULL) as losing_trades,
                ROUND(SUM(pnl_usd), 2) as total_pnl,
                ROUND(AVG(pnl_usd) FILTER (WHERE exit_time IS NOT NULL), 2) as avg_pnl,
                ROUND(MAX(pnl_usd), 2) as max_win,
                ROUND(MIN(pnl_usd), 2) as max_loss,
                ROUND(SUM(fees), 2) as total_fees
            FROM trading.trades
            WHERE entry_time >= %s;
            """
            params = (date_filter,)

        result = self._execute_query(query, params)
        if result:
            summary = dict(result[0])
            # Calculate win rate
            if summary.get('closed_trades', 0) > 0:
                summary['win_rate'] = round(
                    (summary.get('winning_trades', 0) / summary['closed_trades']) * 100, 2
                )
            else:
                summary['win_rate'] = 0.0
            return summary
        return {}

    def get_active_positions(self, bot_id: str = None) -> List[Dict]:
        """Get all active positions"""
        if bot_id:
            query = """
            SELECT
                position_id,
                bot_id,
                symbol,
                side,
                size,
                avg_entry_price,
                current_price,
                unrealized_pnl,
                unrealized_pnl_pct,
                stop_loss,
                take_profit,
                opened_at
            FROM trading.positions
            WHERE bot_id = %s AND status = 'open'
            ORDER BY opened_at DESC;
            """
            params = (bot_id,)
        else:
            query = """
            SELECT
                position_id,
                bot_id,
                symbol,
                side,
                size,
                avg_entry_price,
                current_price,
                unrealized_pnl,
                unrealized_pnl_pct,
                stop_loss,
                take_profit,
                opened_at
            FROM trading.positions
            WHERE status = 'open'
            ORDER BY bot_id, opened_at DESC;
            """
            params = None

        return self._execute_query(query, params)

    def get_recent_trades(self, bot_id: str = None, limit: int = 10) -> List[Dict]:
        """Get recent trades"""
        if bot_id:
            query = """
            SELECT
                trade_id,
                bot_id,
                symbol,
                side,
                quantity,
                entry_price,
                exit_price,
                pnl_usd,
                pnl_pct,
                status,
                entry_time,
                exit_time,
                exit_reason
            FROM trading.trades
            WHERE bot_id = %s
            ORDER BY entry_time DESC
            LIMIT %s;
            """
            params = (bot_id, limit)
        else:
            query = """
            SELECT
                trade_id,
                bot_id,
                symbol,
                side,
                quantity,
                entry_price,
                exit_price,
                pnl_usd,
                pnl_pct,
                status,
                entry_time,
                exit_time,
                exit_reason
            FROM trading.trades
            ORDER BY entry_time DESC
            LIMIT %s;
            """
            params = (limit,)

        return self._execute_query(query, params)

    def get_daily_performance(self, bot_id: str = None, days: int = 7) -> List[Dict]:
        """Get daily performance breakdown"""
        date_filter = datetime.now() - timedelta(days=days)

        if bot_id:
            query = """
            SELECT
                DATE(entry_time) as trade_date,
                COUNT(*) as trades,
                COUNT(*) FILTER (WHERE pnl_usd > 0) as wins,
                COUNT(*) FILTER (WHERE pnl_usd <= 0 AND exit_time IS NOT NULL) as losses,
                ROUND(SUM(pnl_usd), 2) as daily_pnl,
                ROUND(AVG(pnl_usd) FILTER (WHERE exit_time IS NOT NULL), 2) as avg_pnl
            FROM trading.trades
            WHERE bot_id = %s AND entry_time >= %s
            GROUP BY DATE(entry_time)
            ORDER BY trade_date DESC;
            """
            params = (bot_id, date_filter)
        else:
            query = """
            SELECT
                DATE(entry_time) as trade_date,
                COUNT(*) as trades,
                COUNT(*) FILTER (WHERE pnl_usd > 0) as wins,
                COUNT(*) FILTER (WHERE pnl_usd <= 0 AND exit_time IS NOT NULL) as losses,
                ROUND(SUM(pnl_usd), 2) as daily_pnl,
                ROUND(AVG(pnl_usd) FILTER (WHERE exit_time IS NOT NULL), 2) as avg_pnl
            FROM trading.trades
            WHERE entry_time >= %s
            GROUP BY DATE(entry_time)
            ORDER BY trade_date DESC;
            """
            params = (date_filter,)

        return self._execute_query(query, params)

    def get_risk_metrics(self, bot_id: str = None) -> Dict:
        """Get current risk metrics"""
        query = """
        SELECT
            date,
            bot_id,
            win_rate,
            profit_factor,
            sharpe_ratio,
            max_drawdown,
            avg_win,
            avg_loss,
            total_trades
        FROM trading.risk_metrics
        WHERE date = CURRENT_DATE
        """ + (f" AND bot_id = '{bot_id}'" if bot_id else "") + """
        ORDER BY bot_id;
        """

        return self._execute_query(query)

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
