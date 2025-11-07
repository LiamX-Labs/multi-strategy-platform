#!/usr/bin/env python3
"""
Backfill position_entries for existing fills that don't have them yet.
Run this once to migrate old data to the new position tracking system.
"""
import sys
sys.path.insert(0, '.')
from shared.alpha_db_client import AlphaDBClient
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

def backfill_lxalgo_position_entries():
    """Backfill position entries for LXAlgo bot"""

    print("=" * 70)
    print("Backfilling Position Entries for LXAlgo")
    print("=" * 70)

    try:
        client = AlphaDBClient(bot_id='lxalgo_001', redis_db=1)

        # Find all Buy fills that don't have position entries
        print("\n1. Finding Buy fills without position entries...")
        with client.pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT f.*
                FROM trading.fills f
                LEFT JOIN trading.position_entries pe ON f.id = pe.entry_fill_id
                WHERE f.bot_id = 'lxalgo_001'
                  AND f.side = 'Buy'
                  AND pe.entry_fill_id IS NULL
                ORDER BY f.exec_time
            """)
            missing_fills = [dict(row) for row in cur.fetchall()]

        print(f"   Found {len(missing_fills)} fills without position entries")

        if not missing_fills:
            print("\n✅ All fills already have position entries!")
            return

        # Create position entries for each
        print(f"\n2. Creating position entries...")
        created = 0
        failed = 0

        for fill in missing_fills:
            try:
                entry_id = client.create_position_entry(
                    symbol=fill['symbol'],
                    entry_price=float(fill['exec_price']),
                    quantity=float(fill['exec_qty']),
                    entry_time=fill['exec_time'],
                    entry_order_id=fill['order_id'],
                    entry_fill_id=fill['id'],
                    commission=float(fill.get('commission', 0))
                )
                created += 1
                print(f"   ✅ {fill['symbol']}: {fill['exec_qty']} @ ${fill['exec_price']} (fill_id={fill['id']})")
            except Exception as e:
                failed += 1
                print(f"   ❌ {fill['symbol']}: {e}")

        print(f"\n3. Summary:")
        print(f"   Created: {created}")
        print(f"   Failed: {failed}")

        if created > 0:
            print(f"\n✅ Successfully backfilled {created} position entries!")

    except Exception as e:
        print(f"\n❌ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == '__main__':
    success = backfill_lxalgo_position_entries()
    sys.exit(0 if success else 1)
