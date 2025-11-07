# Position Tracking Integration Guide

## Overview

The new position tracking system solves P&L calculation issues by:
1. ✅ Tracking each position entry individually
2. ✅ Supporting scale-in with automatic weighted average
3. ✅ Handling container restarts via startup reconciliation
4. ✅ Using FIFO matching for accurate partial close P&L

## Database Components Created

### Tables
- `trading.position_entries` - Individual position entries with FIFO tracking
- View: `trading.current_positions` - Aggregated weighted average view

### AlphaDBClient New Methods
```python
# Create position entry (call on every buy)
db_client.create_position_entry(
    symbol, entry_price, quantity, entry_time,
    entry_order_id, entry_fill_id, commission
)

# Close position with FIFO matching (call on sell)
completed_trades = db_client.close_position_fifo(
    symbol, exit_price, close_qty, exit_time,
    exit_reason, exit_order_id, exit_commission
)

# Get current position summary (weighted average)
position = db_client.get_current_position_summary(symbol)
# Returns: {total_qty, avg_entry_price, entries, ...}

# Get individual entries
entries = db_client.get_open_position_entries(symbol)
```

## Integration Steps for Each Bot

### STEP 1: On Startup - Reconcile Positions

**Add to bot startup code:**

```python
from shared.position_reconciliation import reconcile_positions_on_startup

async def main():
    # Initialize database client
    alpha_client = AlphaDBClient(bot_id='lxalgo_001', redis_db=1)

    # Initialize exchange client
    exchange_client = BybitClient()

    # *** NEW: Reconcile positions on startup ***
    await reconcile_positions_on_startup(
        bot_id='lxalgo_001',
        db_client=alpha_client,
        exchange_client=exchange_client,
        redis_db=1
    )

    # Continue with normal startup
    ...
```

**What this does:**
- Compares database `position_entries` with actual exchange positions
- If position exists on both → Restores to Redis
- If in database but NOT on exchange → Backfills exit data from Bybit API
- Handles positions closed while container was down

---

### STEP 2: On Position Entry - Create Position Entry

**BEFORE (old way):**
```python
# Open position
result = place_order(symbol, 'Buy', quantity, price)

# Record fill only
alpha_client.write_fill(
    symbol=symbol,
    side='Buy',
    exec_price=price,
    exec_qty=quantity,
    order_id=result['orderId'],
    client_order_id=create_client_order_id(bot_id, 'entry'),
    close_reason='entry',
    commission=result['execFee']
)

# Update Redis
alpha_client.update_position_redis(symbol, quantity, 'Buy', price)
```

**AFTER (new way):**
```python
# Open position
result = place_order(symbol, 'Buy', quantity, price)

# Record fill
fill_id = alpha_client.write_fill(
    symbol=symbol,
    side='Buy',
    exec_price=price,
    exec_qty=quantity,
    order_id=result['orderId'],
    client_order_id=create_client_order_id(bot_id, 'entry'),
    close_reason='entry',
    commission=result['execFee']
)

# *** NEW: Create position entry ***
alpha_client.create_position_entry(
    symbol=symbol,
    entry_price=price,
    quantity=quantity,
    entry_time=datetime.now(timezone.utc),
    entry_order_id=result['orderId'],
    entry_fill_id=fill_id,
    commission=result['execFee']
)

# Get weighted average and update Redis
position = alpha_client.get_current_position_summary(symbol)
if position:
    alpha_client.update_position_redis(
        symbol=symbol,
        size=position['total_qty'],
        side='Buy',
        avg_price=position['avg_entry_price']
    )
```

---

### STEP 3: On Position Exit - Use FIFO Close

**BEFORE (old way):**
```python
# Close position
result = close_position(symbol, size)

# Record exit fill
alpha_client.write_fill(
    symbol=symbol,
    side='Sell',
    exec_price=exit_price,
    exec_qty=size,
    ...
)

# *** PROBLEM: P&L calculation was wrong for partial closes ***
# Old code tried to match with ALL entry fills using weighted average
```

**AFTER (new way):**
```python
# Close position
result = close_position(symbol, size)

# Record exit fill
alpha_client.write_fill(
    symbol=symbol,
    side='Sell',
    exec_price=exit_price,
    exec_qty=size,
    order_id=result['orderId'],
    client_order_id=create_client_order_id(bot_id, close_reason),
    close_reason=close_reason,
    commission=result['execFee']
)

# *** NEW: Close using FIFO matching ***
completed_trades = alpha_client.close_position_fifo(
    symbol=symbol,
    exit_price=exit_price,
    close_qty=size,
    exit_time=datetime.now(timezone.utc),
    exit_reason=close_reason,
    exit_order_id=result['orderId'],
    exit_commission=result['execFee']
)

# This automatically:
# - Matches with oldest entries first (FIFO)
# - Handles partial closes correctly
# - Creates accurate completed_trade records
# - Updates remaining_qty in position_entries

# Update Redis to flat
alpha_client.update_position_redis(symbol, 0.0, 'None', 0.0)

# Log results
for trade in completed_trades:
    print(f"  Trade: {trade['quantity']} @ {trade['entry_price']} → {trade['exit_price']}")
    print(f"  P&L: ${trade['net_pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
```

---

## Example: Scale-In Scenario

```python
# Day 1: Open initial position
buy(symbol='BTCUSDT', qty=100, price=50000)
create_position_entry(symbol='BTCUSDT', price=50000, qty=100)
# position_entries: 100 @ 50000

# Day 2: Scale in (add to position)
buy(symbol='BTCUSDT', qty=50, price=51000)
create_position_entry(symbol='BTCUSDT', price=51000, qty=50)
# position_entries: 100 @ 50000, 50 @ 51000

# Query weighted average:
position = get_current_position_summary('BTCUSDT')
# Returns: total_qty=150, avg_entry_price=50333.33

# Day 3: Partial close
sell(symbol='BTCUSDT', qty=120, price=53000)
completed_trades = close_position_fifo('BTCUSDT', exit_price=53000, close_qty=120)

# FIFO matching:
# - Closes 100 from first entry @ 50000 → P&L = (53000-50000)*100 = +$300,000
# - Closes 20 from second entry @ 51000 → P&L = (53000-51000)*20 = +$40,000
# Total P&L = $340,000

# Remaining position: 30 @ 51000 (from second entry)
```

---

## Bot-Specific Integration

### LXAlgo
**Files to modify:**
1. `order_manager.py` - Update `open_trade()` and `close_trade()`
2. `src/main.py` - Add startup reconciliation

### Momentum
**Files to modify:**
1. `integration/alpha_integration.py` - Update `log_trade_entry()` and `log_trade_exit()`
2. `trading_system.py` - Add startup reconciliation in `__init__()`

### ShortSeller
**Files to modify:**
1. `src/integration/alpha_integration.py` - Add position entry methods
2. `scripts/start_trading.py` - Add startup reconciliation and update entry/exit logic

---

## Testing Checklist

- [ ] Normal open → close works
- [ ] Scale-in (multiple entries) calculates weighted average correctly
- [ ] Partial close uses FIFO and calculates correct P&L
- [ ] Container restart restores open positions from database
- [ ] Position closed while down gets backfilled from Bybit API
- [ ] Dual bot instances don't create duplicate entries

---

## Migration

For existing fills in database:
1. Run migration script to create position_entries from existing fills
2. Mark all old completed_trades as migrated
3. Going forward, new system handles everything

See: `/home/william/STRATEGIES/Alpha/scripts/migrate_fills_to_position_entries.py` (to be created)

---

## Benefits Summary

| Issue | Old System | New System |
|-------|-----------|------------|
| Container restarts | ❌ Loses position state | ✅ Restores from database |
| Positions closed while down | ❌ Missing data | ✅ Backfills from Bybit API |
| Scale-in | ❌ No tracking | ✅ Automatic weighted average |
| Partial closes | ❌ Wrong P&L (weighted avg) | ✅ Correct P&L (FIFO) |
| Dual instances | ❌ Duplicate issues | ✅ Handled correctly |
| Audit trail | ❌ Incomplete | ✅ Full history preserved |

---

## Next Steps

1. ✅ Database schema created
2. ✅ AlphaDBClient methods added
3. ✅ Reconciliation utility created
4. ⏳ Integrate into LXAlgo
5. ⏳ Integrate into Momentum
6. ⏳ Integrate into ShortSeller
7. ⏳ Create migration script
8. ⏳ Test all scenarios
