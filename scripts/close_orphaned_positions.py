#!/usr/bin/env python3
"""
Close orphaned position entries that have corresponding sell fills but weren't closed via FIFO.
This is a one-time cleanup for positions that were sold before the new integration was deployed.
"""
import sys
sys.path.insert(0, '.')
from shared.alpha_db_client import AlphaDBClient
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

def close_orphaned_positions():
    """Find and close orphaned position entries"""

    print("=" * 70)
    print("Closing Orphaned Position Entries")
    print("=" * 70)

    try:
        client = AlphaDBClient(bot_id='lxalgo_001', redis_db=1)

        # Find symbols that have sell fills but open position entries
        print("\n1. Finding symbols with sell fills and open position entries...")
        with client.pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT pe.symbol,
                       SUM(pe.remaining_qty) as total_remaining_qty,
                       f.exec_price as sell_price,
                       f.exec_qty as sell_qty,
                       f.exec_time as sell_time,
                       f.close_reason
                FROM trading.position_entries pe
                INNER JOIN trading.fills f ON f.symbol = pe.symbol
                WHERE pe.bot_id = 'lxalgo_001'
                  AND pe.status != 'closed'
                  AND pe.remaining_qty > 0
                  AND f.bot_id = 'lxalgo_001'
                  AND f.side = 'Sell'
                  AND f.exec_time > pe.entry_time
                GROUP BY pe.symbol, f.exec_price, f.exec_qty, f.exec_time, f.close_reason
                ORDER BY pe.symbol, f.exec_time
            """)
            orphaned = [dict(row) for row in cur.fetchall()]

        print(f"   Found {len(orphaned)} symbols with sell fills")

        if not orphaned:
            print("\n✅ No orphaned positions found!")
            return True

        # Process each orphaned position
        print(f"\n2. Closing orphaned positions...")
        closed_count = 0
        failed_count = 0

        for row in orphaned:
            symbol = row['symbol']
            sell_price = float(row['sell_price'])
            sell_qty = float(row['sell_qty'])
            sell_time = row['sell_time']
            close_reason = row['close_reason']

            try:
                # Account for dual bot instances (divide by 2)
                actual_qty = sell_qty / 2

                print(f"\n   {symbol}:")
                print(f"      Sell: {actual_qty} @ ${sell_price} on {sell_time}")

                # Close using FIFO matching
                completed_trades = client.close_position_fifo(
                    symbol=symbol,
                    exit_price=sell_price,
                    close_qty=actual_qty,
                    exit_time=sell_time,
                    exit_reason=close_reason,
                    exit_commission=0.0
                )

                total_pnl = sum(t['net_pnl'] for t in completed_trades)
                print(f"      ✅ Closed {len(completed_trades)} entries, P&L: ${total_pnl:+.2f}")
                closed_count += 1

            except Exception as e:
                print(f"      ❌ Failed: {e}")
                failed_count += 1

        print(f"\n3. Summary:")
        print(f"   Closed: {closed_count}")
        print(f"   Failed: {failed_count}")

        if closed_count > 0:
            print(f"\n✅ Successfully closed {closed_count} orphaned positions!")

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = close_orphaned_positions()
    sys.exit(0 if success else 1)
