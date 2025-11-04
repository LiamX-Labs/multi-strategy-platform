"""
Alpha Trading System - Shared Database Client
All strategies use this to integrate with PostgreSQL and Redis infrastructure
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class AlphaDBClient:
    """
    Centralized database client for Alpha infrastructure integration.

    Provides unified interface for:
    - Writing fills to PostgreSQL (trading.fills table)
    - Managing position state in Redis
    - Querying bot registry and performance data

    Usage:
        client = AlphaDBClient(bot_id='shortseller_001')
        client.write_fill(symbol='BTCUSDT', side='Sell', ...)
        position = client.get_position_redis('BTCUSDT')
    """

    def __init__(self, bot_id: str, redis_db: int = 0):
        """
        Initialize database client.

        Args:
            bot_id: Bot identifier (e.g., 'shortseller_001', 'momentum_001')
            redis_db: Redis database number (0=ShortSeller, 1=LXAlgo, 2=Momentum)
        """
        self.bot_id = bot_id
        self.redis_db = redis_db

        # PostgreSQL connection (via PgBouncer for connection pooling)
        try:
            self.pg_conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'pgbouncer'),
                port=int(os.getenv('POSTGRES_PORT', '6432')),
                database=os.getenv('POSTGRES_DB', 'trading_db'),
                user=os.getenv('POSTGRES_USER', 'trading_user'),
                password=os.getenv('POSTGRES_PASSWORD')
            )
            self.pg_conn.autocommit = False  # Manual commit for transaction control
            logger.info(f"✅ PostgreSQL connected for bot {bot_id}")
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed for bot {bot_id}: {e}")
            raise

        # Redis connection
        try:
            redis_password = os.getenv('REDIS_PASSWORD', '')
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'redis'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=redis_db,
                password=redis_password if redis_password else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Redis connected (DB {redis_db}) for bot {bot_id}")
        except Exception as e:
            logger.error(f"❌ Redis connection failed for bot {bot_id}: {e}")
            raise

    # ========================================
    # FILLS MANAGEMENT (PostgreSQL)
    # ========================================

    def write_fill(
        self,
        symbol: str,
        side: str,
        exec_price: float,
        exec_qty: float,
        order_id: str,
        client_order_id: str,
        close_reason: str,
        commission: float,
        exec_time: datetime = None
    ) -> int:
        """
        Write a fill to trading.fills table.

        This is THE critical integration point. Every executed trade must be recorded here.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: 'Buy' or 'Sell'
            exec_price: Execution price
            exec_qty: Execution quantity
            order_id: Bybit order ID
            client_order_id: Custom order ID (format: bot_id:reason:timestamp)
            close_reason: Why the trade was executed ('entry', 'trailing_stop', etc.)
            commission: Fee paid
            exec_time: Execution timestamp (defaults to now)

        Returns:
            Fill ID (primary key)
        """
        if exec_time is None:
            exec_time = datetime.utcnow()

        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trading.fills (
                        bot_id, symbol, side, exec_price, exec_qty,
                        order_id, client_order_id, close_reason,
                        commission, exec_time
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    self.bot_id, symbol, side, exec_price, exec_qty,
                    order_id, client_order_id, close_reason,
                    commission, exec_time
                ))
                fill_id = cur.fetchone()[0]
            self.pg_conn.commit()

            logger.debug(f"✅ Fill written to PostgreSQL: {symbol} {side} {exec_qty} @ {exec_price}")
            return fill_id

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"❌ Failed to write fill to PostgreSQL: {e}")
            raise

    def get_recent_fills(self, symbol: str = None, limit: int = 50) -> List[Dict]:
        """
        Get recent fills for this bot.

        Args:
            symbol: Optional symbol filter
            limit: Number of fills to return

        Returns:
            List of fill dictionaries
        """
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
                if symbol:
                    cur.execute("""
                        SELECT * FROM trading.fills
                        WHERE bot_id = %s AND symbol = %s
                        ORDER BY exec_time DESC
                        LIMIT %s
                    """, (self.bot_id, symbol, limit))
                else:
                    cur.execute("""
                        SELECT * FROM trading.fills
                        WHERE bot_id = %s
                        ORDER BY exec_time DESC
                        LIMIT %s
                    """, (self.bot_id, limit))

                return [dict(row) for row in cur.fetchall()]

        except Exception as e:
            logger.error(f"❌ Failed to get fills from PostgreSQL: {e}")
            return []

    # ========================================
    # POSITION STATE (Redis)
    # ========================================

    def update_position_redis(
        self,
        symbol: str,
        size: float,
        side: str = None,
        avg_price: float = None,
        unrealized_pnl: float = None
    ):
        """
        Update position state in Redis (live state cache).

        This is read by the bot's trading loop to make decisions.

        Args:
            symbol: Trading pair
            size: Position size (0 = flat)
            side: 'Buy' (long), 'Sell' (short), or None (flat)
            avg_price: Average entry price
            unrealized_pnl: Current unrealized P&L
        """
        try:
            # Primary position size key
            position_key = f"position:{self.bot_id}:{symbol}"
            self.redis_client.set(position_key, size)

            # Position details hash
            details_key = f"{position_key}:details"
            details = {
                'size': size,
                'side': side or 'None',
                'last_update': datetime.utcnow().isoformat()
            }

            if avg_price is not None:
                details['avg_price'] = avg_price
            if unrealized_pnl is not None:
                details['unrealized_pnl'] = unrealized_pnl

            self.redis_client.hset(details_key, mapping=details)

            logger.debug(f"✅ Redis position updated: {symbol} = {size} ({side})")

        except Exception as e:
            logger.error(f"❌ Failed to update Redis position: {e}")
            # Don't raise - Redis failure shouldn't stop trading

    def get_position_redis(self, symbol: str) -> Optional[Dict]:
        """
        Get current position from Redis.

        Args:
            symbol: Trading pair

        Returns:
            Position dict or None if flat
        """
        try:
            position_key = f"position:{self.bot_id}:{symbol}"
            size = self.redis_client.get(position_key)

            if size is None:
                return None

            # Get detailed information
            details_key = f"{position_key}:details"
            details = self.redis_client.hgetall(details_key)

            return {
                'size': float(size),
                'side': details.get('side', 'None'),
                'avg_price': float(details.get('avg_price', 0)) if 'avg_price' in details else None,
                'unrealized_pnl': float(details.get('unrealized_pnl', 0)) if 'unrealized_pnl' in details else None,
                'last_update': details.get('last_update')
            }

        except Exception as e:
            logger.error(f"❌ Failed to get Redis position: {e}")
            return None

    def set_redis_key(self, key: str, value: str, ex: int = None):
        """
        Set arbitrary Redis key-value pair.

        Args:
            key: Redis key
            value: Value to store
            ex: Optional expiry in seconds
        """
        try:
            self.redis_client.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"❌ Failed to set Redis key {key}: {e}")

    def get_redis_key(self, key: str) -> Optional[str]:
        """
        Get arbitrary Redis key value.

        Args:
            key: Redis key

        Returns:
            Value or None
        """
        try:
            return self.redis_client.get(key)
        except Exception as e:
            logger.error(f"❌ Failed to get Redis key {key}: {e}")
            return None

    # ========================================
    # BOT REGISTRY
    # ========================================

    def update_heartbeat(self):
        """Update last_heartbeat timestamp for this bot in trading.bots table."""
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    UPDATE trading.bots
                    SET last_heartbeat = %s
                    WHERE bot_id = %s
                """, (datetime.utcnow(), self.bot_id))
            self.pg_conn.commit()

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"❌ Failed to update heartbeat: {e}")

    def update_equity(self, current_equity: float):
        """Update current equity in trading.bots table."""
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    UPDATE trading.bots
                    SET current_equity = %s, updated_at = %s
                    WHERE bot_id = %s
                """, (current_equity, datetime.utcnow(), self.bot_id))
            self.pg_conn.commit()

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"❌ Failed to update equity: {e}")

    # ========================================
    # PERFORMANCE QUERIES
    # ========================================

    def get_daily_pnl(self, days: int = 1) -> float:
        """
        Calculate P&L for the last N days.

        This is a simplified calculation based on fills.
        For accurate P&L, need to match entry/exit fills.

        Args:
            days: Number of days to look back

        Returns:
            Total P&L in USDT
        """
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        SUM(CASE
                            WHEN side = 'Sell' THEN exec_price * exec_qty
                            WHEN side = 'Buy' THEN -exec_price * exec_qty
                        END) as gross_pnl,
                        SUM(commission) as total_commission
                    FROM trading.fills
                    WHERE bot_id = %s
                    AND exec_time >= NOW() - INTERVAL '%s days'
                """, (self.bot_id, days))

                row = cur.fetchone()
                gross_pnl = float(row[0]) if row[0] else 0
                commission = float(row[1]) if row[1] else 0

                return gross_pnl - commission

        except Exception as e:
            logger.error(f"❌ Failed to calculate daily P&L: {e}")
            return 0.0

    def get_trade_count_today(self) -> int:
        """Get number of fills executed today."""
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM trading.fills
                    WHERE bot_id = %s
                    AND exec_time >= CURRENT_DATE
                """, (self.bot_id,))

                return cur.fetchone()[0]

        except Exception as e:
            logger.error(f"❌ Failed to get trade count: {e}")
            return 0

    # ========================================
    # CLEANUP
    # ========================================

    def close(self):
        """Close database connections."""
        try:
            if self.pg_conn:
                self.pg_conn.close()
                logger.info(f"PostgreSQL connection closed for bot {self.bot_id}")
        except:
            pass

        try:
            if self.redis_client:
                self.redis_client.close()
                logger.info(f"Redis connection closed for bot {self.bot_id}")
        except:
            pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ========================================
# HELPER FUNCTIONS
# ========================================

def parse_client_order_id(client_order_id: str) -> Dict[str, str]:
    """
    Parse client_order_id to extract bot_id and close_reason.

    Format: bot_id:reason:timestamp
    Example: "shortseller_001:entry:1698886400"

    Args:
        client_order_id: Custom order ID

    Returns:
        Dict with 'bot_id', 'close_reason', 'timestamp'
    """
    try:
        parts = client_order_id.split(':')
        return {
            'bot_id': parts[0] if len(parts) > 0 else 'unknown',
            'close_reason': parts[1] if len(parts) > 1 else 'unknown',
            'timestamp': parts[2] if len(parts) > 2 else ''
        }
    except:
        return {'bot_id': 'unknown', 'close_reason': 'unknown', 'timestamp': ''}


def create_client_order_id(bot_id: str, reason: str) -> str:
    """
    Create a properly formatted client_order_id.

    Args:
        bot_id: Bot identifier
        reason: Close reason ('entry', 'trailing_stop', 'take_profit', etc.)

    Returns:
        Formatted client_order_id
    """
    timestamp = int(datetime.utcnow().timestamp())
    return f"{bot_id}:{reason}:{timestamp}"
