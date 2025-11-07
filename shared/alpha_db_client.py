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

    def record_completed_trade(
        self,
        symbol: str,
        entry_side: str,
        entry_price: float,
        entry_qty: float,
        entry_time: datetime,
        entry_reason: str,
        exit_side: str,
        exit_price: float,
        exit_qty: float,
        exit_time: datetime,
        exit_reason: str,
        entry_order_id: str = None,
        exit_order_id: str = None,
        entry_commission: float = 0.0,
        exit_commission: float = 0.0
    ) -> int:
        """
        Record a completed trade to trading.completed_trades table.

        Automatically calculates P&L and other metrics.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            entry_side: 'Buy' or 'Sell'
            entry_price: Entry execution price
            entry_qty: Entry quantity
            entry_time: Entry timestamp
            entry_reason: Why entered ('entry', 'signal', etc.)
            exit_side: 'Buy' or 'Sell' (opposite of entry)
            exit_price: Exit execution price
            exit_qty: Exit quantity
            exit_time: Exit timestamp
            exit_reason: Why exited ('risk_management', 'take_profit', etc.)
            entry_order_id: Optional Bybit entry order ID
            exit_order_id: Optional Bybit exit order ID
            entry_commission: Entry fee
            exit_commission: Exit fee

        Returns:
            Trade ID (primary key)
        """
        try:
            # Calculate P&L
            if entry_side == 'Buy':
                # Long trade: profit = (exit - entry) * qty
                gross_pnl = (exit_price - entry_price) * exit_qty
            else:
                # Short trade: profit = (entry - exit) * qty
                gross_pnl = (entry_price - exit_price) * exit_qty

            total_commission = entry_commission + exit_commission
            net_pnl = gross_pnl - total_commission

            # Calculate percentage return
            cost_basis = entry_price * entry_qty
            pnl_pct = (net_pnl / cost_basis * 100) if cost_basis > 0 else 0

            # Calculate holding duration
            holding_duration = int((exit_time - entry_time).total_seconds())

            # Generate trade_id
            trade_id = f"{self.bot_id}:{symbol}:{int(entry_time.timestamp())}:{int(exit_time.timestamp())}"

            # Generate client order IDs if not provided
            entry_client_id = create_client_order_id(self.bot_id, entry_reason)
            exit_client_id = create_client_order_id(self.bot_id, exit_reason)

            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trading.completed_trades (
                        trade_id, bot_id, symbol,
                        entry_order_id, entry_client_order_id, entry_side,
                        entry_price, entry_qty, entry_time, entry_reason, entry_commission,
                        exit_order_id, exit_client_order_id, exit_side,
                        exit_price, exit_qty, exit_time, exit_reason, exit_commission,
                        gross_pnl, net_pnl, pnl_pct, total_commission,
                        holding_duration_seconds, source
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (trade_id) DO UPDATE SET
                        exit_price = EXCLUDED.exit_price,
                        exit_qty = EXCLUDED.exit_qty,
                        exit_time = EXCLUDED.exit_time,
                        gross_pnl = EXCLUDED.gross_pnl,
                        net_pnl = EXCLUDED.net_pnl,
                        pnl_pct = EXCLUDED.pnl_pct,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (
                    trade_id, self.bot_id, symbol,
                    entry_order_id, entry_client_id, entry_side,
                    entry_price, entry_qty, entry_time, entry_reason, entry_commission,
                    exit_order_id, exit_client_id, exit_side,
                    exit_price, exit_qty, exit_time, exit_reason, exit_commission,
                    gross_pnl, net_pnl, pnl_pct, total_commission,
                    holding_duration, 'bybit_api'
                ))
                db_id = cur.fetchone()[0]
            self.pg_conn.commit()

            logger.info(f"✅ Completed trade recorded: {symbol} {entry_side} → {exit_side}, P&L: ${net_pnl:.2f} ({pnl_pct:.2f}%)")
            return db_id

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"❌ Failed to record completed trade: {e}")
            raise

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
    # POSITION ENTRY TRACKING (New System)
    # ========================================

    def create_position_entry(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        entry_time: datetime,
        entry_order_id: str = None,
        entry_fill_id: int = None,
        commission: float = 0.0
    ) -> str:
        """
        Create a new position entry (supports scale-in and restart recovery).

        Each call creates a separate entry, enabling:
        - Weighted average calculation via current_positions view
        - FIFO matching for partial closes
        - Position continuity across restarts

        Args:
            symbol: Trading pair
            entry_price: Entry execution price
            quantity: Quantity entered
            entry_time: Entry timestamp
            entry_order_id: Optional order ID
            entry_fill_id: Optional fill table reference
            commission: Entry commission

        Returns:
            entry_id: Unique identifier for this entry
        """
        try:
            # Generate unique entry_id (with microseconds for scalping scenarios)
            entry_id = f"{self.bot_id}:{symbol}:{entry_time.timestamp()}"

            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trading.position_entries (
                        bot_id, symbol, entry_id,
                        entry_price, original_qty, remaining_qty,
                        entry_time, entry_order_id, entry_fill_id,
                        entry_commission, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING entry_id
                """, (
                    self.bot_id, symbol, entry_id,
                    entry_price, quantity, quantity,
                    entry_time, entry_order_id, entry_fill_id,
                    commission, 'open'
                ))
                result_id = cur.fetchone()[0]
            self.pg_conn.commit()

            logger.info(f"✅ Position entry created: {symbol} {quantity} @ {entry_price} (entry_id: {entry_id})")
            return result_id

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"❌ Failed to create position entry: {e}")
            raise

    def close_position_fifo(
        self,
        symbol: str,
        exit_price: float,
        close_qty: float,
        exit_time: datetime,
        exit_reason: str,
        exit_order_id: str = None,
        exit_commission: float = 0.0
    ) -> List[Dict]:
        """
        Close position using FIFO (First In, First Out) matching.

        Handles partial closes correctly by matching against oldest entries first.

        Args:
            symbol: Trading pair
            exit_price: Exit execution price
            close_qty: Quantity to close
            exit_time: Exit timestamp
            exit_reason: Reason for exit
            exit_order_id: Optional order ID
            exit_commission: Exit commission

        Returns:
            List of completed trade dictionaries
        """
        # Ensure exit_time is timezone-aware
        if exit_time.tzinfo is None:
            from datetime import timezone
            exit_time = exit_time.replace(tzinfo=timezone.utc)

        try:
            completed_trades = []
            remaining_to_close = close_qty

            # Get all open entries for this symbol, oldest first (FIFO)
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM trading.position_entries
                    WHERE bot_id = %s AND symbol = %s
                      AND status != 'closed' AND remaining_qty > 0
                    ORDER BY entry_time ASC
                    FOR UPDATE
                """, (self.bot_id, symbol))

                entries = cur.fetchall()

            if not entries:
                logger.warning(f"⚠️ No open entries found for {symbol} to close")
                return []

            # Process each entry using FIFO
            for entry in entries:
                if remaining_to_close <= 0:
                    break

                # How much of this entry can we close?
                qty_to_close = min(float(entry['remaining_qty']), remaining_to_close)

                # Calculate P&L for this portion
                entry_price = float(entry['entry_price'])
                gross_pnl = (exit_price - entry_price) * qty_to_close

                # Proportional commission
                entry_comm_portion = float(entry['entry_commission']) * (qty_to_close / float(entry['original_qty']))
                exit_comm_portion = exit_commission * (qty_to_close / close_qty) if close_qty > 0 else 0

                net_pnl = gross_pnl - entry_comm_portion - exit_comm_portion
                cost_basis = entry_price * qty_to_close
                pnl_pct = (net_pnl / cost_basis * 100) if cost_basis > 0 else 0

                # Update entry remaining quantity
                new_remaining = float(entry['remaining_qty']) - qty_to_close
                new_status = 'closed' if new_remaining == 0 else 'partially_closed'

                with self.pg_conn.cursor() as cur:
                    cur.execute("""
                        UPDATE trading.position_entries
                        SET remaining_qty = %s, status = %s
                        WHERE entry_id = %s
                    """, (new_remaining, new_status, entry['entry_id']))

                # Record completed trade
                holding_duration = int((exit_time - entry['entry_time']).total_seconds())

                trade_id = self.record_completed_trade(
                    symbol=symbol,
                    entry_side='Buy',  # Assuming long positions for now
                    entry_price=entry_price,
                    entry_qty=qty_to_close,
                    entry_time=entry['entry_time'],
                    entry_reason='entry',
                    exit_side='Sell',
                    exit_price=exit_price,
                    exit_qty=qty_to_close,
                    exit_time=exit_time,
                    exit_reason=exit_reason,
                    entry_order_id=entry.get('entry_order_id'),
                    exit_order_id=exit_order_id,
                    entry_commission=entry_comm_portion,
                    exit_commission=exit_comm_portion
                )

                completed_trades.append({
                    'entry_id': entry['entry_id'],
                    'trade_id': trade_id,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'quantity': qty_to_close,
                    'gross_pnl': gross_pnl,
                    'net_pnl': net_pnl,
                    'pnl_pct': pnl_pct
                })

                remaining_to_close -= qty_to_close

            self.pg_conn.commit()

            total_pnl = sum(t['net_pnl'] for t in completed_trades)
            logger.info(f"✅ Position closed (FIFO): {symbol} {len(completed_trades)} entries, Total P&L: ${total_pnl:.2f}")

            return completed_trades

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"❌ Failed to close position: {e}")
            raise

    def get_open_position_entries(self, symbol: str = None) -> List[Dict]:
        """
        Get open position entries for this bot.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open position entry dictionaries
        """
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
                if symbol:
                    cur.execute("""
                        SELECT * FROM trading.position_entries
                        WHERE bot_id = %s AND symbol = %s
                          AND status != 'closed' AND remaining_qty > 0
                        ORDER BY entry_time ASC
                    """, (self.bot_id, symbol))
                else:
                    cur.execute("""
                        SELECT * FROM trading.position_entries
                        WHERE bot_id = %s
                          AND status != 'closed' AND remaining_qty > 0
                        ORDER BY symbol, entry_time ASC
                    """, (self.bot_id,))

                return [dict(row) for row in cur.fetchall()]

        except Exception as e:
            logger.error(f"❌ Failed to get open position entries: {e}")
            return []

    def get_current_position_summary(self, symbol: str) -> Optional[Dict]:
        """
        Get aggregated position summary (weighted average) for a symbol.

        Uses the current_positions view which automatically calculates
        weighted average entry price across all open entries.

        Args:
            symbol: Trading pair

        Returns:
            Position summary dict with weighted average, or None
        """
        try:
            with self.pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM trading.current_positions
                    WHERE bot_id = %s AND symbol = %s
                """, (self.bot_id, symbol))

                result = cur.fetchone()
                return dict(result) if result else None

        except Exception as e:
            logger.error(f"❌ Failed to get position summary: {e}")
            return None

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
