# BOT INTEGRATION GUIDE
## How to Update Your Bots for the New Architecture

**Last Updated:** 2025-10-24
**Based on:** Execution logic analysis of all 3 bots

---

## 🎯 OVERVIEW

This guide shows you EXACTLY how to update each bot to work with the new PostgreSQL + Redis + WebSocket Listener architecture.

### Key Changes Required

1. **Add `client_order_id` to every order** - This enables performance tracking
2. **Read positions from Redis** - No more API polling
3. **Let WebSocket listener handle all state updates** - Bots become stateless
4. **Optional: Query PostgreSQL for historical data** - For performance analysis

---

## 📊 THE NEW ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                     YOUR BOT                             │
│  1. Generate signal                                      │
│  2. Read position from REDIS (not API!)                 │
│  3. Place order with custom client_order_id             │
│  4. That's it! WebSocket listener handles the rest      │
└─────────────────────────────────────────────────────────┘
                           │
                           │ Places order with
                           │ client_order_id="bot_id:reason:timestamp"
                           ▼
                  ┌──────────────┐
                  │ BYBIT API    │
                  └──────────────┘
                           │
                           │ Fills order
                           ▼
                  ┌──────────────┐
                  │ Bybit        │
                  │ WebSocket    │
                  └──────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         │                 │                 │
    execution          order            position
      stream           stream           stream
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  WEBSOCKET LISTENER SERVICE  │
            │  (Runs 24/7, independent)    │
            └──────────────────────────────┘
                     │            │
                     │            │
                     ▼            ▼
               ┌──────────┐  ┌────────┐
               │PostgreSQL│  │ Redis  │
               │ (fills)  │  │ (pos)  │
               └──────────┘  └────────┘
                                 │
                                 │
        ┌────────────────────────┘
        │ Bot reads position
        ▼
  ┌──────────────┐
  │  YOUR BOT    │
  │  Next loop   │
  └──────────────┘
```

---

## 🔧 IMPLEMENTATION BY BOT

### **1. SHORTSELLER BOT**

#### Current Implementation Issues
- ❌ No `client_order_id` used
- ❌ Polling API for positions
- ❌ No database persistence

#### File to Update
`/home/william/STRATEGIES/Alpha/shortseller/src/exchange/bybit_client.py`

#### Changes Needed

**A. Add Redis Connection (Lines 1-50)**

```python
import redis

class BybitClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        # ... existing init code ...

        # ADD: Redis connection
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            password=os.getenv('REDIS_PASSWORD'),
            db=0,
            decode_responses=True
        )
        self.bot_id = os.getenv('BOT_ID', 'shortseller_001')
```

**B. Update `place_order()` Method (Lines 305-372)**

```python
# BEFORE
async def place_order(self, symbol: str, side: str, order_type: str, qty: float,
                     stop_loss: float = None, take_profit: float = None):
    params = {
        'category': 'linear',
        'symbol': symbol,
        'side': side,
        'orderType': order_type,
        'qty': str(corrected_qty),
        'timeInForce': 'GTC'
    }
    # ... rest of method ...

# AFTER
async def place_order(self, symbol: str, side: str, order_type: str, qty: float,
                     stop_loss: float = None, take_profit: float = None,
                     order_reason: str = 'entry'):  # ADD THIS PARAMETER
    import time

    # Generate client_order_id: "bot_id:reason:timestamp"
    client_order_id = f"{self.bot_id}:{order_reason}:{int(time.time())}"

    params = {
        'category': 'linear',
        'symbol': symbol,
        'side': side,
        'orderType': order_type,
        'qty': str(corrected_qty),
        'timeInForce': 'GTC',
        'orderLinkId': client_order_id  # ADD THIS LINE
    }

    logger.info(f"Placing order with client_order_id: {client_order_id}")
    # ... rest of method ...
```

**C. Update Position Tracking - Use Redis (Lines 115-126)**

```python
# BEFORE (API polling)
async def get_positions(self, symbol: str = None):
    params = {'category': 'linear'}
    if symbol:
        params['symbol'] = symbol
    result = await self._make_request('GET', '/v5/position/list', params)
    # ... process positions ...

# AFTER (Redis lookup)
def get_position_from_redis(self, symbol: str) -> float:
    """
    Get current position size from Redis.
    This is INSTANT (microseconds) vs API call (hundreds of ms).
    """
    redis_key = f"{self.bot_id}:position:{symbol}"

    try:
        size = self.redis_client.get(redis_key)
        return float(size) if size else 0.0
    except Exception as e:
        logger.error(f"Redis error, falling back to API: {e}")
        # Fallback to API if Redis fails
        return asyncio.run(self._get_position_from_api(symbol))

async def _get_position_from_api(self, symbol: str) -> float:
    """Fallback method - only used if Redis unavailable."""
    params = {'category': 'linear', 'symbol': symbol}
    result = await self._make_request('GET', '/v5/position/list', params)
    positions = result.get('result', {}).get('list', [])
    if positions:
        return float(positions[0].get('size', 0))
    return 0.0
```

**D. Update Main Trading Loop (`scripts/start_trading.py`)**

```python
# BEFORE
async def main_loop(self):
    while True:
        # ... fetch market data ...

        # Check if in position (API call - SLOW)
        positions = await self.client.get_positions(symbol)
        if positions and positions[0]['size'] > 0:
            in_position = True

# AFTER
async def main_loop(self):
    while True:
        # ... fetch market data ...

        # Check if in position (Redis - FAST)
        current_size = self.client.get_position_from_redis(symbol)
        in_position = current_size > 0

        if not in_position and signal == 'ENTER_SHORT':
            # Place order with reason
            await self.client.place_order(
                symbol=symbol,
                side='Sell',
                order_type='Market',
                qty=quantity,
                order_reason='entry'  # THIS IS CRITICAL
            )

        elif in_position:
            # Place exit order with reason
            if trailing_stop_hit:
                await self.client.place_order(
                    symbol=symbol,
                    side='Buy',
                    order_type='Market',
                    qty=current_size,
                    order_reason='trailing_stop'  # TRACKS WHY WE EXITED
                )
```

---

### **2. LXALGO BOT**

#### Current Implementation Issues
- ⚠️ Uses random `orderLinkId` (not actionable)
- ✅ Has WebSocket monitoring (good!)
- ✅ Has database logging (good!)

#### File to Update
`/home/william/STRATEGIES/Alpha/lxalgo/src/trading/executor.py`

#### Changes Needed

**A. Fix `client_order_id` Generation (Lines 160-192)**

```python
# BEFORE
async def execute_market_order_async(self, symbol: str, side: str, quantity: float):
    entry_order = {
        "category": "linear",
        "symbol": symbol,
        "side": side.capitalize(),
        "orderType": "Market",
        "qty": str(quantity),
        "orderLinkId": os.urandom(16).hex()  # RANDOM - NOT USEFUL!
    }

# AFTER
import time

async def execute_market_order_async(self, symbol: str, side: str, quantity: float,
                                    order_reason: str = 'entry'):  # ADD REASON
    # Generate meaningful client_order_id
    bot_id = os.getenv('BOT_ID', 'lxalgo_001')
    client_order_id = f"{bot_id}:{order_reason}:{int(time.time())}"

    entry_order = {
        "category": "linear",
        "symbol": symbol,
        "side": side.capitalize(),
        "orderType": "Market",
        "qty": str(quantity),
        "orderLinkId": client_order_id  # NOW MEANINGFUL!
    }

    logger.info(f"Order with client_order_id: {client_order_id}")
```

**B. Add Redis Position Tracking**

```python
import redis

class Executor:
    def __init__(self):
        # ... existing init ...

        # Add Redis
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            password=os.getenv('REDIS_PASSWORD'),
            db=1,
            decode_responses=True
        )
        self.bot_id = os.getenv('BOT_ID', 'lxalgo_001')

    def get_position_from_redis(self, symbol: str) -> float:
        redis_key = f"{self.bot_id}:position:{symbol}"
        size = self.redis_client.get(redis_key)
        return float(size) if size else 0.0
```

**C. Update Entry Logic with Reasons**

```python
# In execute_entry() method
async def execute_entry(self, symbol: str, rule_id: str):
    # ... existing logic ...

    # Place order with rule_id as reason
    await self.execute_market_order_async(
        symbol=symbol,
        side='Buy',
        quantity=quantity,
        order_reason=f"rule_{rule_id}"  # Track which rule triggered
    )

    # Set stop loss with reason
    # Note: Stop losses are separate orders, give them reasons too
    # Bybit will execute them automatically
```

---

### **3. MOMENTUM BOT**

#### Current Implementation Issues
- ❌ No `client_order_id` used
- ❌ API polling for positions
- ✅ Good database logging (but can use PostgreSQL instead of SQLite)

#### File to Update
`/home/william/STRATEGIES/Alpha/momentum/exchange/bybit_exchange.py`

#### Changes Needed

**A. Add Redis Connection (Lines 1-50)**

```python
import redis

class BybitExchange:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        # ... existing init ...

        # Add Redis
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            password=os.getenv('REDIS_PASSWORD'),
            db=2,
            decode_responses=True
        )
        self.bot_id = os.getenv('BOT_ID', 'momentum_001')
```

**B. Update `place_order()` Method (Lines 202-287)**

```python
# BEFORE
def place_order(
    self,
    symbol: str,
    side: str,
    order_type: str,
    qty: float,
    # ... other params ...
) -> Dict:
    params = {
        "category": category,
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": str(formatted_qty),
        "timeInForce": time_in_force,
    }

# AFTER
def place_order(
    self,
    symbol: str,
    side: str,
    order_type: str,
    qty: float,
    order_reason: str = 'entry',  # ADD THIS
    # ... other params ...
) -> Dict:
    import time

    # Generate client_order_id
    client_order_id = f"{self.bot_id}:{order_reason}:{int(time.time())}"

    params = {
        "category": category,
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": str(formatted_qty),
        "timeInForce": time_in_force,
        "orderLinkId": client_order_id  # ADD THIS
    }

    logger.info(f"Placing order with client_order_id: {client_order_id}")
```

**C. Add Redis Position Method**

```python
def get_position_from_redis(self, symbol: str) -> float:
    """Get position from Redis (instant) instead of API (slow)."""
    redis_key = f"{self.bot_id}:position:{symbol}"

    try:
        size = self.redis_client.get(redis_key)
        return float(size) if size else 0.0
    except Exception as e:
        logger.error(f"Redis error: {e}")
        # Fallback to API
        positions = self.get_positions(symbol=symbol)
        if positions:
            return float(positions[0].get('size', 0))
        return 0.0
```

**D. Update Main Trading System (`trading_system.py`)**

```python
# In execute_entry() method
def execute_entry(self, signal):
    symbol = signal['symbol']

    # Place order with signal reason
    result = self.exchange.place_order(
        symbol=symbol,
        side='Buy',
        order_type='Market',
        qty=qty,
        order_reason='volatility_breakout'  # Clear reason
    )

# In check_exits() method
def check_exits(self):
    for position in self.open_positions:
        symbol = position['symbol']

        # Check position size from Redis
        current_size = self.exchange.get_position_from_redis(symbol)

        if current_size == 0:
            # Position closed by stop loss or take profit
            # WebSocket listener already logged it
            self.open_positions.remove(position)
            continue

        # Check MA exit
        if ma_exit_signal:
            self.exchange.place_order(
                symbol=symbol,
                side='Sell',
                order_type='Market',
                qty=current_size,
                order_reason='ma_exit'  # Track exit reason
            )
```

---

## 🎯 STANDARD `client_order_id` FORMAT

### Format Specification

```
{bot_id}:{reason}:{timestamp}
```

### Reason Codes (Standardized)

#### Entry Reasons
- `entry` - Standard entry signal
- `scale_in` - Adding to position
- `manual_entry` - Manual override

#### Exit Reasons
- `trailing_stop` - Trailing stop hit
- `take_profit` - Take profit hit
- `stop_loss` - Stop loss hit
- `ma_exit` - Moving average exit
- `time_exit` - Time-based exit
- `risk_limit` - Risk limit breach
- `manual_exit` - Manual override

#### Strategy-Specific Reasons
- `rule_1`, `rule_2`, ... - For LXAlgo
- `volatility_breakout` - For Momentum
- `ema_cross` - For Shortseller

### Examples

```python
# Shortseller entry
client_order_id = "shortseller_001:entry:1678886400"

# LXAlgo rule 3 trigger
client_order_id = "lxalgo_001:rule_3:1678886400"

# Momentum trailing stop
client_order_id = "momentum_001:trailing_stop:1678886600"

# Manual override
client_order_id = "shortseller_001:manual_exit:1678886700"
```

---

## 📊 QUERYING YOUR PERFORMANCE

### Query 1: All Fills for a Bot

```python
import psycopg2

conn = psycopg2.connect(
    host='pgbouncer',
    port=6432,
    database='trading_db',
    user='trading_user',
    password=os.getenv('POSTGRES_PASSWORD')
)

cursor = conn.cursor()
cursor.execute("""
    SELECT
        exec_time,
        symbol,
        side,
        exec_qty,
        exec_price,
        commission,
        close_reason
    FROM trading.fills
    WHERE bot_id = %s
    ORDER BY exec_time DESC
    LIMIT 100
""", ('shortseller_001',))

fills = cursor.fetchall()
for fill in fills:
    print(fill)
```

### Query 2: PnL by Close Reason

```sql
SELECT
    close_reason,
    COUNT(*) as trade_count,
    SUM(net_pnl) as total_pnl,
    AVG(net_pnl) as avg_pnl,
    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate
FROM trading.trades_pnl
WHERE bot_id = 'momentum_001'
GROUP BY close_reason
ORDER BY total_pnl DESC;
```

### Query 3: Current Positions (from Redis)

```python
import redis

r = redis.Redis(
    host='redis',
    port=6379,
    password=os.getenv('REDIS_PASSWORD'),
    decode_responses=True
)

# Get all position keys for a bot
keys = r.keys("shortseller_001:position:*")

for key in keys:
    size = r.get(key)
    symbol = key.split(':')[-1]
    print(f"{symbol}: {size}")
```

---

## ✅ TESTING CHECKLIST

### Before Deployment

- [ ] Bot generates client_order_id in correct format
- [ ] Bot reads position from Redis (not API)
- [ ] Bot logs client_order_id in local logs
- [ ] WebSocket listener is running
- [ ] PostgreSQL connection works
- [ ] Redis connection works
- [ ] Test trade in demo mode
- [ ] Verify fill appears in `trading.fills` table
- [ ] Verify position updates in Redis
- [ ] Verify close_reason is parsed correctly

### Deployment Steps

1. Update bot code with changes above
2. Start WebSocket listener first
3. Verify listener is connected (check logs)
4. Start bot
5. Place test trade
6. Check `trading.fills` table
7. Check Redis keys
8. Verify bot sees updated position

---

## 🔍 DEBUGGING

### Check if WebSocket Listener is Working

```bash
# Check container logs
docker logs trading_websocket_listener

# Should see:
# ✓ Connected to PostgreSQL
# ✓ Connected to Redis
# ✓ WebSocket connected
# ✓ Authentication successful
# ✓ Subscription successful
```

### Check if Fills are Being Logged

```bash
# Connect to PostgreSQL
docker exec -it trading_postgres psql -U trading_user -d trading_db

# Query recent fills
SELECT * FROM trading.fills ORDER BY exec_time DESC LIMIT 10;
```

### Check if Redis is Updated

```bash
# Connect to Redis
docker exec -it trading_redis redis-cli -a $REDIS_PASSWORD

# Get all position keys
KEYS *:position:*

# Get specific position
GET shortseller_001:position:BTCUSDT
```

### Bot Not Seeing Position Updates

**Problem:** Bot places order but doesn't see position change

**Solution:**
1. Check WebSocket listener logs - is it receiving position stream?
2. Check Redis - does the key exist?
3. Check bot code - is it reading from Redis?
4. Check bot_id - does it match?

---

## 📝 SUMMARY

### What Each Component Does

| Component | Responsibility | Writes To | Reads From |
|-----------|---------------|-----------|------------|
| **Your Bot** | Generate signals, place orders | Bybit API | Redis (positions) |
| **WebSocket Listener** | Listen to Bybit streams | PostgreSQL, Redis | Bybit WebSocket |
| **PostgreSQL** | Store permanent history | - | Bots (for analysis) |
| **Redis** | Store current state | - | Bots (for decisions) |

### The Data Flow

1. Bot generates signal
2. Bot checks position in Redis
3. Bot places order with `client_order_id`
4. Bybit fills order
5. **WebSocket listener gets fill event**
6. **Listener writes to PostgreSQL (fills table)**
7. **Listener writes to Redis (position key)**
8. Bot's next loop sees updated position in Redis
9. Bot makes next decision

---

**Everything is event-driven and real-time. No polling needed!**
