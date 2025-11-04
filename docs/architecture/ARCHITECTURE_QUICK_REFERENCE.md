# ALPHA TRADING SYSTEM - QUICK REFERENCE GUIDE

**Generated**: October 24, 2025  
**Complete Architecture Doc**: `COMPLETE_SYSTEM_ARCHITECTURE.md` (37 KB)

---

## SYSTEM AT A GLANCE

```
┌─────────────────────────────────────────────────────────────────┐
│            ALPHA TRADING SYSTEM (UNIFIED DEPLOYMENT)            │
└─────────────────────────────────────────────────────────────────┘

Docker Compose: docker-compose.yml (238 lines)

┌─────────────────────────────────────────────────────────────────┐
│ 3 TRADING BOTS + COMMAND CENTER + 2 DATABASES + 1 CACHE         │
└─────────────────────────────────────────────────────────────────┘

    SHORTSELLER              LXALGO                MOMENTUM
    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
    │  EMA 240/600 │      │ Technical    │      │ Volatility   │
    │  Multi-Asset │      │ Analysis     │      │ Breakout     │
    │  Short Trade │      │ 8 Rules      │      │ 4H Altcoins  │
    ├──────────────┤      ├──────────────┤      ├──────────────┤
    │ 1,863 LOC    │      │ 4,397 LOC    │      │ 10,384 LOC   │
    │ PostgreSQL   │      │ In-Memory    │      │ SQLite       │
    │ + Redis      │      │ No DB        │      │ Local        │
    │ 7 Assets     │      │ 200 USD pos  │      │ 3 Positions  │
    │ 10x leverage │      │ 20 max open  │      │ 5% risk      │
    └──────────────┘      └──────────────┘      └──────────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                    ┌───────────────────────┐
                    │ TELEGRAM COMMAND      │
                    │ CENTER (C2)           │
                    │ Unified Control       │
                    │ Docker Integration    │
                    └───────────────────────┘
```

---

## QUICK START

```bash
# Start all systems (from Alpha directory)
cd /home/william/STRATEGIES/Alpha
docker compose -f docker-compose.yml up -d

# View logs (all systems)
docker compose -f docker-compose.yml logs -f

# View specific bot logs
docker compose -f docker-compose.yml logs -f shortseller
docker compose -f docker-compose.yml logs -f lxalgo
docker compose -f docker-compose.yml logs -f momentum

# Stop all
docker compose -f docker-compose.yml down

# Restart specific service
docker compose -f docker-compose.yml restart shortseller
```

---

## DATABASE MAPPING

```
SHORTSELLER
├─ PostgreSQL (shortseller-postgres)
│  ├─ Database: multiasset_trading
│  ├─ User: trading_user
│  ├─ Tables: trades, positions, market_data, signals, 
│  │           account_balance, risk_metrics
│  └─ Port: 5433
│
├─ Redis (shortseller-redis)
│  ├─ Cache & session management
│  ├─ Data persistence enabled
│  └─ Port: 6379

LXALGO
└─ In-Memory Storage (no external DB)
   └─ Real-time state only

MOMENTUM
└─ SQLite (momentum/data/trading.db)
   ├─ trades table
   ├─ daily_snapshots table
   ├─ system_events table
   └─ risk_events table
```

---

## KEY FILES

### Configuration Files
```
Root Level:
  ├─ .env                    (Master environment variables)
  └─ docker-compose.yml      (Service orchestration)

Shortseller:
  ├─ shortseller/.env        (API keys, DB config)
  └─ shortseller/init-db.sql (PostgreSQL schema)

LXAlgo:
  └─ lxalgo/.env             (API keys)

Momentum:
  ├─ momentum/.env            (API keys)
  ├─ momentum/config/trading_config.py (Settings)
  └─ momentum/database/trade_database.py (SQLite interface)
```

### Core Trading Files
```
Shortseller (1,863 LOC):
  ├─ src/core/strategy_engine.py       (726 LOC) - EMA logic
  ├─ src/exchange/bybit_client.py      (577 LOC) - API calls
  ├─ src/notifications/telegram_bot.py (386 LOC) - Alerts
  ├─ order_manager.py                  (23 KB)   - Orders
  └─ risk_manager.py                   (36 KB)   - Risk control

LXAlgo (4,397 LOC):
  ├─ src/trading/executor.py           (488 LOC) - Trade execution
  ├─ src/data/market_data.py           (158 LOC) - Data mgmt
  ├─ src/data/websocket.py             (115 LOC) - WebSocket
  ├─ src/data/indicators.py            (93 LOC)  - Indicators
  └─ src/config/settings.py            - Config

Momentum (10,384 LOC):
  ├─ trading_system.py                 - Main loop
  ├─ signals/entry_signals.py          (212 LOC) - Entry
  ├─ signals/exit_signals.py           (294 LOC) - Exit
  ├─ database/trade_database.py        (15 KB)   - DB interface
  └─ exchange/bybit_exchange.py        (16 KB)   - Exchange API
```

---

## RISK MANAGEMENT SUMMARY

### SHORTSELLER
- Leverage: 10x per asset (210% total)
- Position allocation: 7% per asset
- Stop-loss: 1.5%
- Take-profit: 6%
- Max hold: 24 hours
- Exit priorities: Regime → Time → SL → TP

### LXALGO
- Daily equity drawdown: 2% circuit breaker
- Weekly equity L1: 4% (reduces 50%)
- Weekly equity L2: 6% (halts until Monday)
- Trade max age: 72 hours
- Negative PnL: 8-hour auto-close
- Symbol cooldown: 4 hours

### MOMENTUM
- Daily loss limit: -3% (stops entries)
- Weekly loss limit: -8% (reduces 50%)
- Max positions: 3 concurrent
- Risk per trade: 5%
- Backtest performance: 252% return (27 months)
- Win rate: 37.6%

---

## DATA STORAGE PATTERNS

### Shortseller
```
Input: Bybit V5 API (5-min bars)
  ↓
Processing: EMA calculations, regime detection
  ↓
Storage: PostgreSQL (persistent) + Redis (cache)
  ↓
Output: Trade execution + Telegram alerts
```

### LXAlgo
```
Input: Bybit WebSocket + REST API
  ↓
Processing: Technical indicators, 8 trading rules
  ↓
Storage: In-memory only (no external DB)
  ↓
Output: Trade execution + Telegram alerts
```

### Momentum
```
Input: Bybit API + Local CSV datawarehouse
  ↓
Processing: Bollinger Bands, MA, RVR, BTC filter
  ↓
Storage: SQLite database (trades, snapshots, events)
  ↓
Output: Trade execution + Telegram alerts
```

---

## DOCKER SERVICES CHECKLIST

```
✓ shortseller-postgres
  └─ Status: postgresql://trading_user@localhost:5433/multiasset_trading

✓ shortseller-redis
  └─ Status: redis://localhost:6379/0

✓ shortseller (trading bot)
  └─ Status: pgrep -f start_trading.py

✓ lxalgo (trading bot)
  └─ Status: pgrep -f main.py

✓ momentum (trading bot)
  └─ Status: pgrep -f trading_system.py

✓ telegram_manager (C2)
  └─ Status: Command center for all bots
```

---

## ENVIRONMENT VARIABLES

### Master .env (Root Level)
```
SHORTSELLER_BYBIT_API_KEY=...
SHORTSELLER_BYBIT_API_SECRET=...
SHORTSELLER_TELEGRAM_BOT_TOKEN=...
SHORTSELLER_TELEGRAM_CHANNEL_ID=...
C2_TELEGRAM_BOT_TOKEN=...
C2_TELEGRAM_ADMIN_IDS=...
```

### Bot-Specific .env Files
```
shortseller/.env       → BYBIT_API_KEY, POSTGRES_HOST, REDIS_HOST
lxalgo/.env            → BYBIT_API_KEY, TELEGRAM_BOT_TOKEN
momentum/.env          → BYBIT_DEMO_API_KEY, BYBIT_LIVE_API_KEY
telegram_manager/.env  → TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_IDS
```

---

## DATABASE SCHEMAS AT A GLANCE

### PostgreSQL (Shortseller)
```
SCHEMA: trading

trades           (entry/exit records)
positions        (current holdings)
market_data      (price history)
signals          (trading signals)
account_balance  (equity snapshots)
risk_metrics     (daily performance)

VIEWS:
  active_positions (open positions)
  daily_performance (daily PnL)
```

### SQLite (Momentum)
```
trades           (full trade lifecycle)
daily_snapshots  (daily performance)
system_events    (system events)
risk_events      (risk breaches)
```

---

## DEPENDENCIES SUMMARY

### Shortseller: 48 packages
- Core: pandas, numpy, websockets, aiohttp
- DB: psycopg2-binary, sqlalchemy, alembic, redis
- Exchange: requests, cryptography, ccxt
- Notifications: python-telegram-bot, discord.py
- Monitoring: prometheus-client, colorlog

### LXAlgo: Minimal stack
- Core: aiohttp, pandas, websockets, numpy
- Technical: ta, reportlab, matplotlib
- Utilities: python-dotenv, nest-asyncio

### Momentum: Minimal stack
- Core: pandas, numpy, requests
- Exchange: pybit (Bybit wrapper)
- Database: sqlite3 (built-in)
- Testing: pytest

### Telegram Manager: Control layer
- Bot: python-telegram-bot==20.7
- Docker: docker==7.0.0
- DB: psycopg2-binary, redis
- Utilities: requests, python-dotenv

---

## DEPLOYMENT WORKFLOW

```
1. Configuration
   ├─ Set .env files (root + individual)
   ├─ Verify API keys
   └─ Ensure TESTNET mode initially

2. Docker Compose Startup
   ├─ PostgreSQL + Redis (health checks)
   ├─ Shortseller (waits for DB/Redis)
   ├─ LXAlgo (independent)
   ├─ Momentum (independent)
   └─ Telegram Manager (control layer)

3. Health Verification
   ├─ Docker containers running
   ├─ Database connectivity
   ├─ Exchange connectivity
   ├─ Telegram notifications
   └─ Log monitoring

4. Trading Startup
   ├─ Symbol loading
   ├─ Account verification
   ├─ Signal generation starts
   └─ Real-time monitoring begins
```

---

## PERFORMANCE METRICS

### Shortseller
- Strategy: EMA 240/600 crossover
- Timeframe: 5-minute bars
- Assets: BTC, ETH, SOL (multi-asset)
- Leverage: 10x per asset

### LXAlgo
- Strategy: Technical analysis (8 rules)
- Position sizing: 200 USD base
- Max concurrent: 20 trades
- Breakeven management: Automatic

### Momentum
- Backtest Return: +252% (27 months)
- Total Trades: 306
- Win Rate: 37.6%
- Profit Factor: 2.18
- Max Drawdown: -23.11%
- Sharpe Ratio: 0.67

---

## IMPORTANT NOTES

1. **Always start in TESTNET mode** first
2. **Database**: Shortseller has persistent storage (PostgreSQL)
3. **Isolation**: All 3 bots run independently
4. **Monitoring**: Check logs daily via Telegram
5. **Scaling**: Memory limits: 900m per bot, 256m for C2
6. **Networking**: All services on `trading-network` bridge

---

## TROUBLESHOOTING QUICK GUIDE

| Issue | Command | Solution |
|-------|---------|----------|
| Container won't start | `docker logs [container]` | Check configuration |
| DB connection failed | `docker ps` | Ensure PostgreSQL healthy |
| Restart stuck | `docker compose down` | Clean shutdown first |
| Check service status | `docker compose ps` | Verify all running |
| View DB directly | `docker exec -it shortseller-postgres psql -U trading_user -d multiasset_trading` | Direct query |
| Clear logs | `docker compose logs --follow [service]` | Real-time logs |

---

## KEY METRICS TO MONITOR

### Shortseller
- EMA Regime (ACTIVE/INACTIVE)
- Active positions count
- Daily cross count
- Cooldown status

### LXAlgo
- Active trades count
- Daily equity change %
- Weekly equity tracking
- Last trade time

### Momentum
- Daily PnL
- Weekly PnL
- Win/loss ratio
- Max drawdown current

### All Systems
- Container status
- CPU/Memory usage
- Log error rate
- Telegram alerts delivered

---

## ARCHITECTURE DOCUMENTATION

**Detailed Documentation**: `/home/william/STRATEGIES/Alpha/COMPLETE_SYSTEM_ARCHITECTURE.md` (37 KB)

Covers:
- Complete directory structure
- Detailed data flow diagrams
- Full database schemas
- All configuration files
- Risk management details
- Deployment architecture
- Integration points

---

**Last Updated**: October 24, 2025  
**System Status**: Production Ready  
**Documentation Complete**: Yes
