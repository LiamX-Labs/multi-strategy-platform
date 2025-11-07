#!/usr/bin/env python3
"""
Fix LXAlgo trade data:
1. Handle duplicate fills (from dual bot instances)
2. Generate completed trade records from fills
3. Calculate accurate P&L for closed positions
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from collections import defaultdict

# Database connection
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=int(os.getenv('POSTGRES_PORT', 5432)),
    database=os.getenv('POSTGRES_DB', 'trading_db'),
    user=os.getenv('POSTGRES_USER', 'trading_user'),
    password=os.getenv('POSTGRES_PASSWORD')
)
conn.autocommit = False

def get_all_lxalgo_fills():
    """Get all LXAlgo fills ordered by time."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM trading.fills
            WHERE bot_id = 'lxalgo_001'
            ORDER BY symbol, exec_time
        """)
        return [dict(row) for row in cur.fetchall()]

def group_fills_by_symbol(fills):
    """Group fills by symbol."""
    symbol_fills = defaultdict(lambda: {'buys': [], 'sells': []})

    for fill in fills:
        symbol = fill['symbol']
        if fill['side'] == 'Buy':
            symbol_fills[symbol]['buys'].append(fill)
        else:
            symbol_fills[symbol]['sells'].append(fill)

    return symbol_fills

def calculate_completed_trades(symbol_fills):
    """
    Calculate completed trades from fills.

    Since sells come from dual instances, each sell is 2x the actual amount.
    We need to halve the sell quantities to match with buys.
    """
    completed_trades = []

    for symbol, data in symbol_fills.items():
        buys = data['buys']
        sells = data['sells']

        if not sells:
            print(f"  {symbol}: Still open ({len(buys)} entries)")
            continue

        # Get total buy quantity
        total_buy_qty = sum(float(f['exec_qty']) for f in buys)

        # Get total sell quantity (halved because of dual instances)
        total_sell_qty = sum(float(f['exec_qty']) for f in sells) / 2

        print(f"  {symbol}:")
        print(f"    Total bought: {total_buy_qty:.4f}")
        print(f"    Total sold (corrected): {total_sell_qty:.4f}")

        # Calculate weighted average entry price
        if total_buy_qty > 0:
            weighted_entry_price = sum(
                float(f['exec_price']) * float(f['exec_qty'])
                for f in buys
            ) / total_buy_qty
        else:
            weighted_entry_price = 0

        # Calculate weighted average exit price
        if len(sells) > 0:
            total_sell_value = sum(float(f['exec_price']) * float(f['exec_qty']) for f in sells)
            total_sell_qty_raw = sum(float(f['exec_qty']) for f in sells)
            weighted_exit_price = total_sell_value / total_sell_qty_raw if total_sell_qty_raw > 0 else 0
        else:
            weighted_exit_price = 0

        # Use earliest buy time and latest sell time
        entry_time = min(f['exec_time'] for f in buys) if buys else datetime.utcnow()
        exit_time = max(f['exec_time'] for f in sells) if sells else datetime.utcnow()

        # Calculate P&L (Long trades: profit = (exit - entry) * qty)
        gross_pnl = (weighted_exit_price - weighted_entry_price) * total_sell_qty

        # Calculate commissions
        total_entry_commission = sum(float(f.get('commission', 0)) for f in buys)
        total_exit_commission = sum(float(f.get('commission', 0)) for f in sells) / 2  # Halve for dual instance

        net_pnl = gross_pnl - total_entry_commission - total_exit_commission

        # Calculate percentage
        cost_basis = weighted_entry_price * total_sell_qty
        pnl_pct = (net_pnl / cost_basis * 100) if cost_basis > 0 else 0

        # Holding duration
        holding_duration = int((exit_time - entry_time).total_seconds())

        print(f"    Entry: {weighted_entry_price:.6f}")
        print(f"    Exit: {weighted_exit_price:.6f}")
        print(f"    Net P&L: ${net_pnl:.2f} ({pnl_pct:+.2f}%)")

        completed_trades.append({
            'symbol': symbol,
            'entry_price': weighted_entry_price,
            'exit_price': weighted_exit_price,
            'entry_qty': total_buy_qty,
            'exit_qty': total_sell_qty,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'entry_commission': total_entry_commission,
            'exit_commission': total_exit_commission,
            'holding_duration': holding_duration,
            'exit_reason': sells[0].get('close_reason', 'risk_management') if sells else 'unknown'
        })

    return completed_trades

def insert_completed_trades(trades):
    """Insert completed trades into database."""
    if not trades:
        print("\nNo completed trades to insert.")
        return

    print(f"\nInserting {len(trades)} completed trades...")

    with conn.cursor() as cur:
        for trade in trades:
            trade_id = f"lxalgo_001:{trade['symbol']}:{int(trade['entry_time'].timestamp())}:{int(trade['exit_time'].timestamp())}"

            try:
                cur.execute("""
                    INSERT INTO trading.completed_trades (
                        trade_id, bot_id, symbol,
                        entry_side, entry_price, entry_qty, entry_time, entry_reason, entry_commission,
                        exit_side, exit_price, exit_qty, exit_time, exit_reason, exit_commission,
                        gross_pnl, net_pnl, pnl_pct, total_commission,
                        holding_duration_seconds, source
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (trade_id) DO UPDATE SET
                        exit_price = EXCLUDED.exit_price,
                        exit_qty = EXCLUDED.exit_qty,
                        exit_time = EXCLUDED.exit_time,
                        gross_pnl = EXCLUDED.gross_pnl,
                        net_pnl = EXCLUDED.net_pnl,
                        pnl_pct = EXCLUDED.pnl_pct,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    trade_id, 'lxalgo_001', trade['symbol'],
                    'Buy', trade['entry_price'], trade['entry_qty'], trade['entry_time'], 'entry', trade['entry_commission'],
                    'Sell', trade['exit_price'], trade['exit_qty'], trade['exit_time'], trade['exit_reason'], trade['exit_commission'],
                    trade['gross_pnl'], trade['net_pnl'], trade['pnl_pct'], trade['entry_commission'] + trade['exit_commission'],
                    trade['holding_duration'], 'manual_sync'
                ))
                print(f"  ✅ {trade['symbol']}: ${trade['net_pnl']:.2f}")
            except Exception as e:
                print(f"  ❌ {trade['symbol']}: {e}")

    conn.commit()

def main():
    print("=" * 60)
    print("LXAlgo Trade Data Reconciliation")
    print("=" * 60)

    print("\n1. Fetching all LXAlgo fills...")
    fills = get_all_lxalgo_fills()
    print(f"   Found {len(fills)} fills")

    print("\n2. Grouping fills by symbol...")
    symbol_fills = group_fills_by_symbol(fills)
    print(f"   Found {len(symbol_fills)} unique symbols")

    print("\n3. Calculating completed trades (accounting for dual instances)...")
    completed_trades = calculate_completed_trades(symbol_fills)

    print("\n4. Summary:")
    print(f"   Closed positions: {len(completed_trades)}")
    if completed_trades:
        total_pnl = sum(t['net_pnl'] for t in completed_trades)
        winners = sum(1 for t in completed_trades if t['net_pnl'] > 0)
        losers = sum(1 for t in completed_trades if t['net_pnl'] < 0)
        print(f"   Total P&L: ${total_pnl:.2f}")
        print(f"   Winners: {winners}, Losers: {losers}")
        print(f"   Win rate: {winners/len(completed_trades)*100:.1f}%")

    print("\n5. Writing completed trades to database...")
    insert_completed_trades(completed_trades)

    print("\n✅ Done!")
    conn.close()

if __name__ == "__main__":
    main()
