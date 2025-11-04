#!/usr/bin/env python3
"""
Migrate Momentum Bot Data from SQLite to PostgreSQL
===================================================

This script migrates all Momentum bot trading data from the SQLite database
to the unified PostgreSQL schema.

Usage:
    python migrate_momentum_sqlite_to_postgres.py

Prerequisites:
    - PostgreSQL with unified schema (migration 001 completed)
    - Momentum bot SQLite database at: momentum/data/trading.db
    - pip install psycopg2-binary
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import json
from typing import Dict, List
import os
from pathlib import Path

# Configuration
SQLITE_DB_PATH = "momentum/data/trading.db"
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "trading_db"),
    "user": os.getenv("POSTGRES_USER", "trading_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "secure_password")
}
BOT_ID = "momentum_001"


class MomentumMigrator:
    """Migrates Momentum bot data from SQLite to PostgreSQL."""

    def __init__(self, sqlite_path: str, postgres_config: Dict):
        self.sqlite_path = sqlite_path
        self.postgres_config = postgres_config
        self.stats = {
            "trades": 0,
            "risk_metrics": 0,
            "system_events": 0,
            "risk_events": 0,
            "errors": []
        }

    def connect_sqlite(self):
        """Connect to SQLite database."""
        if not Path(self.sqlite_path).exists():
            raise FileNotFoundError(f"SQLite database not found: {self.sqlite_path}")

        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        print(f"✓ Connected to SQLite: {self.sqlite_path}")
        return conn

    def connect_postgres(self):
        """Connect to PostgreSQL database."""
        conn = psycopg2.connect(**self.postgres_config)
        print(f"✓ Connected to PostgreSQL: {self.postgres_config['database']}")
        return conn

    def migrate_trades(self, sqlite_conn, postgres_conn):
        """Migrate trades from SQLite to PostgreSQL."""
        print("\n📊 Migrating trades...")

        # Read from SQLite
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("""
            SELECT
                trade_id,
                mode,
                symbol,
                side,
                entry_time,
                entry_price,
                exit_time,
                exit_price,
                quantity,
                position_size_usd,
                stop_loss,
                take_profit,
                pnl_usd,
                pnl_pct,
                exit_reason,
                holding_time_seconds,
                signal_strength
            FROM trades
            ORDER BY entry_time
        """)

        trades = sqlite_cur.fetchall()
        print(f"  Found {len(trades)} trades in SQLite")

        if len(trades) == 0:
            print("  No trades to migrate")
            return

        # Prepare data for PostgreSQL
        postgres_cur = postgres_conn.cursor()

        insert_query = """
            INSERT INTO trading.trades (
                trade_id, bot_id, symbol, side, trade_type,
                quantity, entry_price, exit_price, position_size_usd,
                leverage, stop_loss, take_profit, status,
                entry_time, exit_time, holding_time_seconds,
                pnl_usd, pnl_pct, fees, exit_reason,
                strategy, signal_strength, created_at, updated_at
            ) VALUES %s
            ON CONFLICT (trade_id) DO NOTHING
        """

        values = []
        for trade in trades:
            # Determine status
            if trade['exit_time']:
                status = 'filled'
            else:
                status = 'pending'

            # Determine deployment mode from trade
            deployment_mode = trade['mode'] if trade['mode'] else 'demo'

            values.append((
                f"{BOT_ID}_{trade['trade_id']}",  # Prefix with bot_id
                BOT_ID,
                trade['symbol'],
                trade['side'],
                'market',  # trade_type
                float(trade['quantity']),
                float(trade['entry_price']),
                float(trade['exit_price']) if trade['exit_price'] else None,
                float(trade['position_size_usd']),
                1,  # leverage (spot trading)
                float(trade['stop_loss']) if trade['stop_loss'] else None,
                float(trade['take_profit']) if trade['take_profit'] else None,
                status,
                trade['entry_time'],
                trade['exit_time'],
                trade['holding_time_seconds'],
                float(trade['pnl_usd']) if trade['pnl_usd'] else 0,
                float(trade['pnl_pct']) if trade['pnl_pct'] else 0,
                0,  # fees (not tracked in SQLite)
                trade['exit_reason'],
                'volatility_breakout',
                float(trade['signal_strength']) if trade['signal_strength'] else None,
                datetime.now(),
                datetime.now()
            ))

        # Batch insert
        execute_values(postgres_cur, insert_query, values)
        postgres_conn.commit()

        self.stats['trades'] = len(values)
        print(f"  ✓ Migrated {len(values)} trades")

    def migrate_risk_metrics(self, sqlite_conn, postgres_conn):
        """Migrate daily snapshots as risk metrics."""
        print("\n📊 Migrating daily snapshots to risk metrics...")

        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("""
            SELECT
                date,
                mode,
                starting_equity,
                ending_equity,
                daily_pnl,
                daily_pnl_pct,
                trades_count,
                wins_count,
                losses_count,
                open_positions
            FROM daily_snapshots
            ORDER BY date
        """)

        snapshots = sqlite_cur.fetchall()
        print(f"  Found {len(snapshots)} daily snapshots")

        if len(snapshots) == 0:
            print("  No snapshots to migrate")
            return

        postgres_cur = postgres_conn.cursor()

        insert_query = """
            INSERT INTO trading.risk_metrics (
                bot_id, date, starting_equity, ending_equity,
                daily_pnl, daily_pnl_pct, total_trades,
                winning_trades, losing_trades, win_rate,
                net_profit, created_at
            ) VALUES %s
            ON CONFLICT (bot_id, date) DO NOTHING
        """

        values = []
        for snapshot in snapshots:
            total_trades = snapshot['trades_count'] or 0
            wins = snapshot['wins_count'] or 0

            values.append((
                BOT_ID,
                snapshot['date'],
                float(snapshot['starting_equity']),
                float(snapshot['ending_equity']),
                float(snapshot['daily_pnl']),
                float(snapshot['daily_pnl_pct']),
                total_trades,
                wins,
                snapshot['losses_count'] or 0,
                float(wins) / total_trades if total_trades > 0 else 0,
                float(snapshot['daily_pnl']),
                datetime.now()
            ))

        execute_values(postgres_cur, insert_query, values)
        postgres_conn.commit()

        self.stats['risk_metrics'] = len(values)
        print(f"  ✓ Migrated {len(values)} daily snapshots")

    def migrate_system_events(self, sqlite_conn, postgres_conn):
        """Migrate system events."""
        print("\n📊 Migrating system events...")

        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("""
            SELECT
                event_time,
                event_type,
                event_level,
                message,
                details
            FROM system_events
            ORDER BY event_time
        """)

        events = sqlite_cur.fetchall()
        print(f"  Found {len(events)} system events")

        if len(events) == 0:
            print("  No events to migrate")
            return

        postgres_cur = postgres_conn.cursor()

        insert_query = """
            INSERT INTO audit.system_events (
                event_time, event_type, event_level, bot_id,
                component, message, details, created_at
            ) VALUES %s
        """

        values = []
        for event in events:
            # Parse details JSON
            details = None
            if event['details']:
                try:
                    details = json.loads(event['details'])
                except:
                    details = {"raw": event['details']}

            values.append((
                event['event_time'],
                event['event_type'],
                event['event_level'],
                BOT_ID,
                'momentum_bot',
                event['message'],
                json.dumps(details) if details else None,
                datetime.now()
            ))

        execute_values(postgres_cur, insert_query, values)
        postgres_conn.commit()

        self.stats['system_events'] = len(values)
        print(f"  ✓ Migrated {len(values)} system events")

    def migrate_risk_events(self, sqlite_conn, postgres_conn):
        """Migrate risk events."""
        print("\n📊 Migrating risk events...")

        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("""
            SELECT
                event_time,
                risk_type,
                current_value,
                limit_value,
                action_taken
            FROM risk_events
            ORDER BY event_time
        """)

        events = sqlite_cur.fetchall()
        print(f"  Found {len(events)} risk events")

        if len(events) == 0:
            print("  No risk events to migrate")
            return

        postgres_cur = postgres_conn.cursor()

        insert_query = """
            INSERT INTO audit.risk_events (
                event_time, bot_id, risk_type, current_value,
                limit_value, action_taken, created_at
            ) VALUES %s
        """

        values = []
        for event in events:
            values.append((
                event['event_time'],
                BOT_ID,
                event['risk_type'],
                float(event['current_value']),
                float(event['limit_value']),
                event['action_taken'],
                datetime.now()
            ))

        execute_values(postgres_cur, insert_query, values)
        postgres_conn.commit()

        self.stats['risk_events'] = len(values)
        print(f"  ✓ Migrated {len(values)} risk events")

    def update_bot_equity(self, postgres_conn):
        """Update bot current equity from latest metrics."""
        print("\n📊 Updating bot equity...")

        postgres_cur = postgres_conn.cursor()
        postgres_cur.execute("""
            UPDATE trading.bots
            SET
                current_equity = (
                    SELECT ending_equity
                    FROM trading.risk_metrics
                    WHERE bot_id = %s
                    ORDER BY date DESC
                    LIMIT 1
                ),
                last_heartbeat = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE bot_id = %s
            RETURNING current_equity
        """, (BOT_ID, BOT_ID))

        result = postgres_cur.fetchone()
        postgres_conn.commit()

        if result:
            print(f"  ✓ Updated bot equity: ${result[0]:.2f}")
        else:
            print("  ⚠ Could not update bot equity")

    def log_migration(self, postgres_conn):
        """Log migration completion in audit table."""
        postgres_cur = postgres_conn.cursor()
        postgres_cur.execute("""
            INSERT INTO audit.system_events (
                event_type, event_level, bot_id, component,
                message, details
            ) VALUES (
                'DATA_MIGRATION', 'INFO', %s, 'migration_script',
                'Momentum bot data migrated from SQLite to PostgreSQL',
                %s::jsonb
            )
        """, (
            BOT_ID,
            json.dumps(self.stats)
        ))
        postgres_conn.commit()

    def run(self):
        """Execute the full migration."""
        print("=" * 60)
        print("Momentum Bot Data Migration: SQLite → PostgreSQL")
        print("=" * 60)

        try:
            # Connect to databases
            sqlite_conn = self.connect_sqlite()
            postgres_conn = self.connect_postgres()

            # Run migrations
            self.migrate_trades(sqlite_conn, postgres_conn)
            self.migrate_risk_metrics(sqlite_conn, postgres_conn)
            self.migrate_system_events(sqlite_conn, postgres_conn)
            self.migrate_risk_events(sqlite_conn, postgres_conn)

            # Update bot equity
            self.update_bot_equity(postgres_conn)

            # Log migration
            self.log_migration(postgres_conn)

            # Close connections
            sqlite_conn.close()
            postgres_conn.close()

            # Print summary
            print("\n" + "=" * 60)
            print("✓ MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print(f"  Trades migrated:        {self.stats['trades']}")
            print(f"  Risk metrics migrated:  {self.stats['risk_metrics']}")
            print(f"  System events migrated: {self.stats['system_events']}")
            print(f"  Risk events migrated:   {self.stats['risk_events']}")

            if self.stats['errors']:
                print(f"\n⚠ Errors encountered: {len(self.stats['errors'])}")
                for error in self.stats['errors']:
                    print(f"  - {error}")

            print("\n✓ Momentum bot is now ready in the unified system!")
            print("=" * 60)

        except Exception as e:
            print(f"\n❌ MIGRATION FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

        return True


def main():
    """Main entry point."""
    # Check if SQLite database exists
    if not Path(SQLITE_DB_PATH).exists():
        print(f"❌ SQLite database not found: {SQLITE_DB_PATH}")
        print("Please ensure the Momentum bot database exists at this location.")
        return

    # Run migration
    migrator = MomentumMigrator(SQLITE_DB_PATH, POSTGRES_CONFIG)
    success = migrator.run()

    if success:
        print("\n💡 Next steps:")
        print("  1. Verify data in PostgreSQL")
        print("  2. Update Momentum bot to use PostgreSQL connection")
        print("  3. Test bot operation with unified database")
        print("  4. Backup SQLite database and archive it")
    else:
        print("\n⚠ Please fix errors and run migration again")


if __name__ == "__main__":
    main()
