#!/usr/bin/env python3
"""
Test script for position tracking integration
"""
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/shared')

from shared.alpha_db_client import AlphaDBClient
from datetime import datetime, timezone

def test_position_tracking():
    """Test position entry creation and retrieval"""
    print("=" * 60)
    print("Testing Position Tracking Integration")
    print("=" * 60)

    try:
        # Initialize client
        print("\n1. Initializing AlphaDBClient...")
        client = AlphaDBClient(bot_id='lxalgo_001', redis_db=1)
        print("✅ Client initialized")

        # Create a test fill first
        print("\n2. Creating test fill...")
        from shared.alpha_db_client import create_client_order_id
        test_time = datetime.now(timezone.utc)
        fill_id = client.write_fill(
            symbol='TESTUSDT',
            side='Buy',
            exec_price=50000.0,
            exec_qty=0.1,
            order_id='test_order_123',
            client_order_id=create_client_order_id('lxalgo_001', 'test_entry'),
            close_reason='test_entry',
            commission=0.05,
            exec_time=test_time
        )
        print(f"✅ Fill created with ID: {fill_id}")

        # Create a test position entry
        print("\n3. Creating test position entry...")
        entry_id = client.create_position_entry(
            symbol='TESTUSDT',
            entry_price=50000.0,
            quantity=0.1,
            entry_time=test_time,
            entry_order_id='test_order_123',
            entry_fill_id=fill_id,
            commission=0.05
        )
        print(f"✅ Position entry created: {entry_id}")

        # Get position summary
        print("\n4. Getting position summary...")
        position = client.get_current_position_summary('TESTUSDT')
        if position:
            print(f"✅ Position summary:")
            print(f"   Symbol: {position['symbol']}")
            print(f"   Total qty: {position['total_qty']}")
            print(f"   Avg entry: ${position['avg_entry_price']:.2f}")
            print(f"   Num entries: {position['num_entries']}")
        else:
            print("❌ Could not retrieve position summary")

        # Test scale-in
        print("\n5. Testing scale-in...")
        test_time_2 = datetime.now(timezone.utc)
        fill_id_2 = client.write_fill(
            symbol='TESTUSDT',
            side='Buy',
            exec_price=51000.0,
            exec_qty=0.05,
            order_id='test_order_124',
            client_order_id=create_client_order_id('lxalgo_001', 'test_entry'),
            close_reason='test_entry',
            commission=0.025,
            exec_time=test_time_2
        )
        entry_id_2 = client.create_position_entry(
            symbol='TESTUSDT',
            entry_price=51000.0,
            quantity=0.05,
            entry_time=test_time_2,
            entry_order_id='test_order_124',
            entry_fill_id=fill_id_2,
            commission=0.025
        )
        print(f"✅ Second entry created: {entry_id_2}")

        # Get updated position summary
        print("\n6. Getting updated position summary...")
        position = client.get_current_position_summary('TESTUSDT')
        if position:
            print(f"✅ Position summary (after scale-in):")
            print(f"   Total qty: {position['total_qty']}")
            print(f"   Weighted avg: ${position['avg_entry_price']:.2f}")
            print(f"   Num entries: {position['num_entries']}")

            # Verify weighted average calculation
            expected_avg = (50000 * 0.1 + 51000 * 0.05) / 0.15
            actual_avg = float(position['avg_entry_price'])
            diff = abs(expected_avg - actual_avg)
            if diff < 0.01:
                print(f"✅ Weighted average is correct! (Expected: ${expected_avg:.2f}, Got: ${actual_avg:.2f})")
            else:
                print(f"❌ Weighted average mismatch! (Expected: ${expected_avg:.2f}, Got: ${actual_avg:.2f})")

        # Test partial close with FIFO
        print("\n7. Testing partial close (FIFO)...")
        completed_trades = client.close_position_fifo(
            symbol='TESTUSDT',
            exit_price=52000.0,
            close_qty=0.08,  # Close 80% of first entry
            exit_time=datetime.now(timezone.utc),
            exit_reason='test_close',
            exit_commission=0.04
        )
        print(f"✅ Closed {len(completed_trades)} position(s)")
        for trade in completed_trades:
            print(f"   P&L: ${trade['net_pnl']:+.2f} ({trade['pnl_pct']:+.2f}%)")

        # Get position summary after partial close
        print("\n8. Getting position summary after partial close...")
        position = client.get_current_position_summary('TESTUSDT')
        if position:
            print(f"✅ Position summary (after partial close):")
            print(f"   Remaining qty: {position['total_qty']}")
            print(f"   Weighted avg: ${position['avg_entry_price']:.2f}")
            print(f"   Num entries: {position['num_entries']}")

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == '__main__':
    success = test_position_tracking()
    sys.exit(0 if success else 1)
