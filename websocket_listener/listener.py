#!/usr/bin/env python3
"""
Bybit WebSocket Listener Service
=================================

This is THE CRITICAL SERVICE for the Alpha Trading System.

It listens to Bybit's Private WebSocket v5 streams:
1. execution - Every fill (THE PERFORMANCE STREAM)
2. order - Order lifecycle
3. position - Exchange reconciliation

And updates:
- PostgreSQL (fills table) - Permanent history
- Redis (live positions) - Current state

This service is the SINGLE SOURCE OF TRUTH for position state.
All bots read from Redis, this service writes to Redis.

Author: Alpha Trading System
Based on: docs/guides/data.md specifications
"""

import os
import sys
import json
import time
import hmac
import hashlib
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

import websockets
import psycopg2
from psycopg2.extras import RealDictCursor
import redis.asyncio as redis

# ============================================
# CONFIGURATION
# ============================================

# Database Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'pgbouncer')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '6432'))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'trading_db')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'trading_user')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

# Bybit Configuration
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')
BYBIT_TESTNET = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
BYBIT_DEMO = os.getenv('BYBIT_DEMO', 'true').lower() == 'true'

# Stream Configuration
ENABLE_EXECUTION_STREAM = os.getenv('ENABLE_EXECUTION_STREAM', 'true').lower() == 'true'
ENABLE_ORDER_STREAM = os.getenv('ENABLE_ORDER_STREAM', 'true').lower() == 'true'
ENABLE_POSITION_STREAM = os.getenv('ENABLE_POSITION_STREAM', 'true').lower() == 'true'

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# WebSocket URLs
# Priority: Demo > Testnet > Mainnet
if BYBIT_DEMO:
    WS_URL = "wss://stream-demo.bybit.com/v5/private"
elif BYBIT_TESTNET:
    WS_URL = "wss://stream-testnet.bybit.com/v5/private"
else:
    WS_URL = "wss://stream.bybit.com/v5/private"

# ============================================
# SETUP LOGGING
# ============================================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/websocket_listener.log')
    ]
)

logger = logging.getLogger(__name__)


# ============================================
# DATABASE CONNECTIONS
# ============================================

class DatabaseManager:
    """Manages PostgreSQL and Redis connections."""

    def __init__(self):
        self.pg_conn = None
        self.redis_client = None

    async def connect(self):
        """Connect to databases."""
        # PostgreSQL
        try:
            self.pg_conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                cursor_factory=RealDictCursor
            )
            logger.info(f"✓ Connected to PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

        # Redis
        try:
            self.redis_client = await redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info(f"✓ Connected to Redis: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def close(self):
        """Close database connections."""
        if self.pg_conn:
            self.pg_conn.close()
        if self.redis_client:
            asyncio.create_task(self.redis_client.close())


# ============================================
# CLIENT ORDER ID PARSER
# ============================================

def parse_client_order_id(client_order_id: str) -> Dict[str, str]:
    """
    Parse client_order_id to extract bot_id and close_reason.

    Expected format: "bot_id:close_reason:timestamp"
    Examples:
        - "shortseller_001:entry:1678886400"
        - "momentum_001:trailing_stop:1678886600"
        - "lxalgo_001:take_profit:1678886700"

    Returns:
        dict with bot_id, close_reason, timestamp
    """
    try:
        parts = client_order_id.split(':')
        if len(parts) >= 2:
            return {
                'bot_id': parts[0],
                'close_reason': parts[1],
                'timestamp': parts[2] if len(parts) > 2 else None
            }
        else:
            # Fallback for non-standard format
            return {
                'bot_id': 'unknown',
                'close_reason': client_order_id,
                'timestamp': None
            }
    except Exception as e:
        logger.warning(f"Failed to parse client_order_id '{client_order_id}': {e}")
        return {
            'bot_id': 'unknown',
            'close_reason': 'unknown',
            'timestamp': None
        }


# ============================================
# STREAM HANDLERS
# ============================================

class StreamHandler:
    """Handles incoming WebSocket messages."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def handle_execution(self, data: Dict):
        """
        Handle execution stream (THE CRITICAL ONE).

        This is the "book of record" for performance.
        Every fill is permanently logged to PostgreSQL.

        From data.md:
        "This is your "book of record" for performance. It sends a message
         every single time one of your orders is filled."
        """
        try:
            # Extract fields from execution message
            order_id = data.get('orderId')
            client_order_id = data.get('orderLinkId', '')
            symbol = data.get('symbol')
            side = data.get('side')  # Buy or Sell
            exec_price = float(data.get('execPrice', 0))
            exec_qty = float(data.get('execQty', 0))
            exec_fee = float(data.get('execFee', 0))
            exec_time = data.get('execTime')  # milliseconds timestamp

            # Parse client_order_id to get bot_id and close_reason
            parsed = parse_client_order_id(client_order_id)
            bot_id = parsed['bot_id']
            close_reason = parsed['close_reason']

            # Convert timestamp
            exec_timestamp = datetime.fromtimestamp(int(exec_time) / 1000)

            # Insert into PostgreSQL fills table
            cursor = self.db.pg_conn.cursor()
            cursor.execute("""
                INSERT INTO trading.fills (
                    bot_id, symbol, order_id, client_order_id,
                    side, exec_price, exec_qty, exec_time,
                    close_reason, commission, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
            """, (
                bot_id, symbol, order_id, client_order_id,
                side, exec_price, exec_qty, exec_timestamp,
                close_reason, exec_fee
            ))
            self.db.pg_conn.commit()

            logger.info(
                f"✓ FILL LOGGED: {bot_id} | {symbol} | {side} | "
                f"{exec_qty} @ {exec_price} | Reason: {close_reason} | Fee: {exec_fee}"
            )

        except Exception as e:
            logger.error(f"Error handling execution: {e}", exc_info=True)
            self.db.pg_conn.rollback()

    async def handle_order(self, data: Dict):
        """
        Handle order stream (lifecycle tracking).

        Tracks order status: New, PartiallyFilled, Filled, Cancelled, Rejected.
        """
        try:
            order_id = data.get('orderId')
            client_order_id = data.get('orderLinkId', '')
            symbol = data.get('symbol')
            side = data.get('side')
            order_type = data.get('orderType')
            order_status = data.get('orderStatus')
            qty = float(data.get('qty', 0))
            price = float(data.get('price', 0)) if data.get('price') else None

            # Parse bot_id
            parsed = parse_client_order_id(client_order_id)
            bot_id = parsed['bot_id']

            # Upsert into orders table
            cursor = self.db.pg_conn.cursor()
            cursor.execute("""
                INSERT INTO trading.orders (
                    bot_id, symbol, order_id, client_order_id,
                    order_type, side, quantity, price, status,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                )
                ON CONFLICT (order_id) DO UPDATE
                SET status = EXCLUDED.status, updated_at = NOW()
            """, (
                bot_id, symbol, order_id, client_order_id,
                order_type, side, qty, price, order_status
            ))
            self.db.pg_conn.commit()

            logger.info(
                f"✓ ORDER UPDATE: {bot_id} | {symbol} | {order_id} | "
                f"Status: {order_status}"
            )

        except Exception as e:
            logger.error(f"Error handling order: {e}", exc_info=True)
            self.db.pg_conn.rollback()

    async def handle_position(self, data: Dict):
        """
        Handle position stream (THE RECONCILIATION STREAM).

        This is the exchange's "source of truth".
        Updates BOTH PostgreSQL and Redis.

        From data.md:
        "This is your "source of truth" from the exchange. Your system's
         internal state (in Redis) must be synced to this message to
         prevent "drift.""
        """
        try:
            symbol = data.get('symbol')
            size = float(data.get('size', 0))
            side = data.get('side')  # Buy, Sell, or None
            avg_price = float(data.get('avgPrice', 0)) if data.get('avgPrice') else None

            # We need to determine bot_id from symbol mapping
            # For now, we'll update ALL bot positions for this symbol
            # (In production, you'd maintain a symbol -> bot_id mapping)

            # Update PostgreSQL positions table
            cursor = self.db.pg_conn.cursor()

            # Get all bots
            cursor.execute("SELECT bot_id FROM trading.bots WHERE status = 'active'")
            bots = cursor.fetchall()

            for bot in bots:
                bot_id = bot['bot_id']

                cursor.execute("""
                    INSERT INTO trading.positions (
                        bot_id, symbol, size, side, avg_entry_price, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, NOW()
                    )
                    ON CONFLICT (bot_id, symbol) DO UPDATE
                    SET size = EXCLUDED.size,
                        side = EXCLUDED.side,
                        avg_entry_price = EXCLUDED.avg_entry_price,
                        updated_at = NOW()
                """, (bot_id, symbol, size, side, avg_price))

                # Update Redis (THIS IS CRITICAL FOR BOTS)
                # Store full position object as JSON for bot consumption
                redis_key = f"{bot_id}:position:{symbol}"
                position_data = json.dumps({
                    'symbol': symbol,
                    'size': str(size),
                    'side': side,
                    'avgPrice': str(avg_price) if avg_price else '0',
                    'unrealisedPnl': str(data.get('unrealisedPnl', 0)),
                    'updatedTime': str(int(time.time() * 1000))
                })
                await self.db.redis_client.set(redis_key, position_data)

                logger.info(
                    f"✓ POSITION UPDATE: {bot_id} | {symbol} | "
                    f"Size: {size} | Side: {side} | Redis: {redis_key} (JSON)"
                )

            self.db.pg_conn.commit()

        except Exception as e:
            logger.error(f"Error handling position: {e}", exc_info=True)
            self.db.pg_conn.rollback()


# ============================================
# WEBSOCKET CLIENT
# ============================================

class BybitWebSocketClient:
    """Bybit Private WebSocket v5 Client."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.handler = StreamHandler(db_manager)
        self.ws = None
        self.running = False

    def _generate_signature(self, expires: int) -> str:
        """Generate authentication signature."""
        signature = hmac.new(
            bytes(BYBIT_API_SECRET, 'utf-8'),
            bytes(f'GET/realtime{expires}', 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _authenticate(self):
        """Send authentication message."""
        expires = int((time.time() + 10) * 1000)
        signature = self._generate_signature(expires)

        auth_message = {
            "req_id": "auth_001",
            "op": "auth",
            "args": [BYBIT_API_KEY, expires, signature]
        }

        await self.ws.send(json.dumps(auth_message))
        logger.info("Sent authentication request")

    async def _subscribe_streams(self):
        """Subscribe to execution, order, and position streams."""
        topics = []

        if ENABLE_EXECUTION_STREAM:
            topics.append("execution")
            logger.info("Subscribing to execution stream")

        if ENABLE_ORDER_STREAM:
            topics.append("order")
            logger.info("Subscribing to order stream")

        if ENABLE_POSITION_STREAM:
            topics.append("position")
            logger.info("Subscribing to position stream")

        if topics:
            subscribe_message = {
                "req_id": "subscribe_001",
                "op": "subscribe",
                "args": topics
            }
            await self.ws.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed to: {topics}")

    async def _handle_message(self, message: Dict):
        """Route incoming messages to appropriate handlers."""
        try:
            # Handle auth response
            if message.get('op') == 'auth':
                if message.get('success'):
                    logger.info("✓ Authentication successful")
                    await self._subscribe_streams()
                else:
                    logger.error(f"Authentication failed: {message}")
                    return

            # Handle subscription response
            elif message.get('op') == 'subscribe':
                if message.get('success'):
                    logger.info(f"✓ Subscription successful: {message.get('req_id')}")
                else:
                    logger.error(f"Subscription failed: {message}")
                    return

            # Handle data messages
            elif message.get('topic'):
                topic = message['topic']
                data_list = message.get('data', [])

                for data in data_list:
                    if topic == 'execution':
                        await self.handler.handle_execution(data)
                    elif topic == 'order':
                        await self.handler.handle_order(data)
                    elif topic == 'position':
                        await self.handler.handle_position(data)

            # Handle ping/pong
            elif message.get('op') == 'pong':
                logger.debug("Received pong")

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    async def _heartbeat(self):
        """Send ping every 20 seconds to keep connection alive."""
        while self.running:
            try:
                await asyncio.sleep(20)
                if self.ws and not self.ws.closed:
                    ping_message = {"req_id": "ping", "op": "ping"}
                    await self.ws.send(json.dumps(ping_message))
                    logger.debug("Sent ping")
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def connect(self):
        """Connect to WebSocket and start listening."""
        self.running = True

        while self.running:
            try:
                logger.info(f"Connecting to Bybit WebSocket: {WS_URL}")

                async with websockets.connect(
                    WS_URL,
                    ping_interval=None,  # We handle ping manually
                    ping_timeout=None
                ) as ws:
                    self.ws = ws
                    logger.info("✓ WebSocket connected")

                    # Authenticate
                    await self._authenticate()

                    # Start heartbeat task
                    heartbeat_task = asyncio.create_task(self._heartbeat())

                    # Listen for messages
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            await self._handle_message(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}", exc_info=True)

                    # Cancel heartbeat when connection closes
                    heartbeat_task.cancel()

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting in 5s...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                await asyncio.sleep(5)

    def stop(self):
        """Stop the WebSocket client."""
        self.running = False
        if self.ws:
            asyncio.create_task(self.ws.close())


# ============================================
# MAIN APPLICATION
# ============================================

async def main():
    """Main application entry point."""
    logger.info("=" * 60)
    logger.info("Bybit WebSocket Listener Service Starting")
    logger.info("=" * 60)
    logger.info(f"Demo Mode: {BYBIT_DEMO}")
    logger.info(f"Testnet Mode: {BYBIT_TESTNET}")
    logger.info(f"WebSocket URL: {WS_URL}")
    logger.info(f"Execution Stream: {ENABLE_EXECUTION_STREAM}")
    logger.info(f"Order Stream: {ENABLE_ORDER_STREAM}")
    logger.info(f"Position Stream: {ENABLE_POSITION_STREAM}")
    logger.info("=" * 60)

    # Validate configuration
    if not BYBIT_API_KEY or not BYBIT_API_SECRET:
        logger.error("BYBIT_API_KEY and BYBIT_API_SECRET must be set")
        sys.exit(1)

    if not POSTGRES_PASSWORD:
        logger.error("POSTGRES_PASSWORD must be set")
        sys.exit(1)

    # Initialize database connections
    db_manager = DatabaseManager()
    await db_manager.connect()

    # Initialize WebSocket client
    ws_client = BybitWebSocketClient(db_manager)

    try:
        # Start listening
        await ws_client.connect()

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")

    finally:
        ws_client.stop()
        db_manager.close()
        logger.info("Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
