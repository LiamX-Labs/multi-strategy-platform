#!/usr/bin/env python3
"""
One-time migration: Convert existing fills to completed_trades
Matches buy/sell pairs from trading.fills table
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import timezone
from trade_matcher import TradeMatcher
import logging
from config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_fills_from_db(bot_id):
    """Fetch all fills for a bot from database"""
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            bot_id,
            symbol,
            order_id as "orderId",
            client_order_id as "orderLinkId",
            side,
            exec_price as "execPrice",
            exec_qty as "execQty",
            EXTRACT(EPOCH FROM exec_time) * 1000 as "execTime",
            commission as "execFee"
        FROM trading.fills
        WHERE bot_id = %s
        ORDER BY exec_time ASC
    """, (bot_id,))

    fills = cursor.fetchall()
    conn.close()

    # Convert to list of dicts
    return [dict(fill) for fill in fills]


def insert_completed_trade(trade, conn):
    """Insert a completed trade into database"""
    cursor = conn.cursor()

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
        ON CONFLICT (trade_id) DO NOTHING
    """

    cursor.execute(query, trade)
    cursor.close()


def migrate_bot_fills(bot_id):
    """Migrate fills to completed trades for a specific bot"""
    logger.info(f"Migrating fills for {bot_id}...")

    # Fetch fills
    fills = fetch_fills_from_db(bot_id)
    logger.info(f"  Found {len(fills)} fills")

    if not fills:
        logger.info(f"  No fills to migrate for {bot_id}")
        return 0

    # Match trades
    matcher = TradeMatcher()
    matched_trades = matcher.match_all_symbols(fills)
    logger.info(f"  Matched {len(matched_trades)} completed trades")

    if not matched_trades:
        logger.info(f"  No completed trades to migrate for {bot_id}")
        return 0

    # Insert into database
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

    inserted = 0
    for trade in matched_trades:
        try:
            # Update source to 'manual' (fills_migration not in check constraint)
            trade['source'] = 'manual'
            insert_completed_trade(trade, conn)
            inserted += 1
        except Exception as e:
            logger.error(f"  Failed to insert trade {trade.get('trade_id')}: {str(e)}")
            conn.rollback()  # Rollback failed transaction

    conn.commit()
    conn.close()

    logger.info(f"  Inserted {inserted} completed trades for {bot_id}")
    return inserted


def main():
    """Main migration function"""
    logger.info("=" * 60)
    logger.info("MIGRATING FILLS TO COMPLETED_TRADES")
    logger.info("=" * 60)

    bots = ['shortseller_001', 'lxalgo_001', 'momentum_001']

    total_inserted = 0
    for bot_id in bots:
        try:
            inserted = migrate_bot_fills(bot_id)
            total_inserted += inserted
        except Exception as e:
            logger.error(f"Migration failed for {bot_id}: {str(e)}")

    logger.info("=" * 60)
    logger.info(f"MIGRATION COMPLETE: {total_inserted} total trades migrated")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
