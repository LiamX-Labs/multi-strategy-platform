# ALPHA TRADING SYSTEM - COMPLETE ARCHITECTURE MAP

**Date**: October 23, 2025  
**Status**: Production Ready  
**Documentation Level**: Very Thorough  

---

## TABLE OF CONTENTS

1. [System Overview](#system-overview)
2. [Project Directory Structure](#project-directory-structure)
3. [Bot Projects Details](#bot-projects-details)
4. [Database Systems](#database-systems)
5. [Configuration & Environment](#configuration--environment)
6. [Data Flow Architecture](#data-flow-architecture)
7. [Dependencies & Requirements](#dependencies--requirements)
8. [Deployment Architecture](#deployment-architecture)
9. [Risk Management & Monitoring](#risk-management--monitoring)

---

## SYSTEM OVERVIEW

The Alpha Trading System is a **unified cryptocurrency trading platform** consisting of three independent but coordinated trading bots deployed via Docker Compose. All systems are designed to trade on Bybit exchange with various strategies.

### Core Components:
- **3 Independent Trading Bots** (Shortseller, LXAlgo, Momentum)
- **1 Telegram Command Center** (C2 - unified control interface)
- **2 Database Systems** (PostgreSQL + SQLite)
- **1 Cache Layer** (Redis)
- **Unified Docker Deployment** (docker-compose.yml at root)

### Total Codebase Size:
- **Shortseller**: 1,863 lines of Python
- **LXAlgo**: ~4,397 lines of Python
- **Momentum**: 10,384 lines of Python
- **Telegram Manager**: Python + Docker integration
- **Total Active Code**: ~16,644 lines (excluding venv and documentation)

---

## PROJECT DIRECTORY STRUCTURE

```
/home/william/STRATEGIES/Alpha/
│
├── ROOT DEPLOYMENT FILES
│   ├── docker-compose.yml          ← PRIMARY unified deployment config
│   ├── .env                         ← Master environment variables
│   ├── .env.example                 ← Template for .env
│   ├── deploy_c2.sh                 ← Deployment script
│   └── fix_build.sh                 ← Build fix script
│
├── DOCUMENTATION (59+ KB)
│   ├── README.md                    ← Main system documentation
│   ├── DOCKER_STARTUP_GUIDE.md      ← Startup instructions
│   ├── IMPLEMENTATION_SUMMARY.md    ← Implementation details
│   ├── tradingsystemguide.md        ← Comprehensive guide
│   ├── CONFLICT_RESOLUTION_SUMMARY.md
│   ├── COMMAND_CENTER_GUIDE.md
│   ├── C2_IMPLEMENTATION_SUMMARY.md
│   └── QUICK_REFERENCE.md
│
├── SHORTSELLER/ (Multi-Asset Short Trading)
│   ├── Dockerfile
│   ├── docker-compose.yml.standalone
│   ├── .env                         ← API Keys for shortseller
│   ├── requirements.txt             ← Python dependencies
│   ├── init-db.sql                  ← PostgreSQL schema
│   ├── main.py                      ← Alternative entry point
│   ├── order_manager.py             ← Order execution (23 KB)
│   ├── risk_manager.py              ← Risk management (36 KB)
│   ├── settings.py                  ← Configuration
│   ├── system_logger.py             ← Logging system
│   ├── telegram_alerts.py           ← Telegram integration
│   ├── trade_tracker.py             ← Trade logging
│   ├── async_trade_processor.py     ← Async processing
│   ├── logs/
│   │   ├── trading.log              ← Current log file
│   │   └── [archives]
│   │
│   ├── src/                         ← Core modules (1,863 LOC)
│   │   ├── core/
│   │   │   ├── strategy_engine.py   ← EMA crossover strategy (726 LOC)
│   │   │   └── __init__.py
│   │   ├── exchange/
│   │   │   ├── bybit_client.py      ← Bybit API integration (577 LOC)
│   │   │   └── __init__.py
│   │   ├── notifications/
│   │   │   ├── telegram_bot.py      ← Telegram bot (386 LOC)
│   │   │   └── __init__.py
│   │   ├── utils/
│   │   │   ├── trade_duration_tracker.py (174 LOC)
│   │   │   └── __init__.py
│   │   └── __init__.py
│   │
│   ├── config/
│   │   ├── settings.py
│   │   └── [config files]
│   │
│   ├── scripts/
│   │   ├── start_trading.py         ← Entry point
│   │   └── [other scripts]
│   │
│   ├── backtesting/
│   └── performance_analysis/
│
├── LXALGO/ (CFT Prop Trading Bot)
│   ├── Dockerfile
│   ├── .env                         ← API Keys for lxalgo
│   ├── .env.server.example
│   ├── requirements.txt             ← Python dependencies
│   ├── main.py                      ← Entry point (32 LOC)
│   ├── settings.py                  ← Configuration
│   ├── order_manager.py             ← Order management (22 KB)
│   ├── risk_manager.py              ← Risk system (36 KB)
│   ├── system_logger.py             ← Logging
│   ├── telegram_alerts.py           ← Notifications
│   ├── async_trade_processor.py     ← Async processing
│   │
│   ├── src/                         ← Modular architecture (~4,397 LOC)
│   │   ├── main.py                  ← Restructured entry point
│   │   ├── config/
│   │   │   ├── settings.py          ← Configuration management
│   │   │   ├── bridge.py
│   │   │   └── __init__.py
│   │   ├── data/
│   │   │   ├── market_data.py       ← Data management (158 LOC)
│   │   │   ├── websocket.py         ← WebSocket feeds (115 LOC)
│   │   │   ├── indicators.py        ← Technical analysis (93 LOC)
│   │   │   └── __init__.py
│   │   ├── trading/
│   │   │   ├── executor.py          ← Trade execution (488 LOC)
│   │   │   └── __init__.py
│   │   ├── core/
│   │   │   ├── trading_engine.py
│   │   │   └── __init__.py
│   │   ├── utils/
│   │   │   ├── helpers.py           ← Utilities (156 LOC)
│   │   │   └── __init__.py
│   │   ├── monitoring/
│   │   │   └── __init__.py
│   │   └── __init__.py
│   │
│   ├── docs/
│   ├── backtesting/
│   └── logs/ (empty)
│
├── MOMENTUM/ (Momentum Strategy Bot)
│   ├── Dockerfile
│   ├── .env                         ← API Keys for momentum
│   ├── .env.server.example
│   ├── requirements.txt             ← Python dependencies
│   ├── trading_system.py            ← Entry point (main trading system)
│   │
│   ├── config/                      (Configuration)
│   │   ├── trading_config.py        ← Trading parameters & mode switching
│   │   ├── assets.py                ← Asset configuration
│   │   └── __init__.py
│   │
│   ├── exchange/
│   │   ├── bybit_exchange.py        ← Bybit API wrapper
│   │   ├── bybit_testnet.py
│   │   └── __pycache__
│   │
│   ├── database/
│   │   └── trade_database.py        ← SQLite trade logging (15 KB)
│   │
│   ├── data/                        (Data Management)
│   │   ├── bybit_api.py             ← API client (17 KB)
│   │   ├── data_loader.py           ← Historical data loading
│   │   ├── data_updater.py          ← Data updates
│   │   ├── data_validator.py        ← Data validation
│   │   ├── cache/                   ← Market data cache
│   │   ├── backups/
│   │   ├── trading.db               ← SQLite database (49 KB)
│   │   └── __pycache__
│   │
│   ├── signals/                     (Trading Signals)
│   │   ├── entry_signals.py         ← Entry logic (212 LOC)
│   │   ├── exit_signals.py          ← Exit logic (294 LOC)
│   │   ├── btc_regime_filter.py     ← BTC filter (170 LOC)
│   │   ├── regime_filter.py         ← Regime detection (178 LOC)
│   │   └── __init__.py
│   │
│   ├── indicators/                  (Technical Indicators)
│   │   ├── bollinger_bands.py       ← BBands
│   │   ├── moving_averages.py       ← MA calculations
│   │   ├── adx.py                   ← ADX indicator
│   │   ├── volume.py                ← Volume analysis
│   │   └── __init__.py
│   │
│   ├── alerts/
│   │   └── telegram_bot.py          ← Telegram notifications
│   │
│   ├── backtest/                    (Backtesting System)
│   │   ├── position_sizer.py
│   │   └── [other backtest files]
│   │
│   ├── scripts/                     (Utility Scripts - 2.3 KB total)
│   │   ├── check_btc_regime.py      ← BTC regime check (101 LOC)
│   │   ├── performance_analysis.py  ← Perf analysis (378 LOC)
│   │   ├── run_backtest.py          ← Backtest runner (170 LOC)
│   │   ├── run_realistic_backtest.py (290 LOC)
│   │   ├── test_api_simple.py       ← API testing (202 LOC)
│   │   ├── test_connection.py       ← Connection test (132 LOC)
│   │   ├── test_exchange_execution.py (392 LOC)
│   │   ├── test_telegram.py         ← Telegram test (252 LOC)
│   │   └── test_telegram_simple.py  (266 LOC)
│   │
│   ├── tests/                       (Unit Tests - 724 LOC total)
│   │   ├── test_data_loader.py      ← Data loading tests (130 LOC)
│   │   ├── test_data_validator.py   ← Validator tests (151 LOC)
│   │   ├── test_indicators.py       ← Indicator tests (227 LOC)
│   │   ├── test_signals.py          ← Signal tests (216 LOC)
│   │   └── __init__.py
│   │
│   ├── results/                     (Backtest results)
│   ├── cache/                       (Market data cache)
│   ├── data/                        (Trading data)
│   ├── logs/ (empty)
│   ├── docs/
│   ├── config/
│   ├── archive/
│   └── README.md
│
├── TELEGRAM_MANAGER/ (Command & Control)
│   ├── Dockerfile
│   ├── .env                         ← C2 bot token and admin IDs
│   ├── requirements.txt             ← Dependencies
│   ├── bot.py                       ← Telegram bot implementation
│   ├── logs/
│   └── config/
│
└── .git/                           (Git repositories in each project)
```

---

## BOT PROJECTS DETAILS

### 1. SHORTSELLER - Multi-Asset Short Trading System

**Strategy**: 240/600 EMA Crossover  
**Assets**: BTC, ETH, SOL  
**Position Sizing**: 7% per asset with 10x leverage (210% total exposure)  
**Infrastructure**: PostgreSQL + Redis  
**Status**: Production Ready  
**Code**: 1,863 lines

#### Core Components:

| Component | File | Size | Purpose |
|-----------|------|------|---------|
| Strategy Engine | `src/core/strategy_engine.py` | 726 LOC | EMA crossover signal generation, market regime analysis |
| Bybit Client | `src/exchange/bybit_client.py` | 577 LOC | Bybit V5 API integration, order execution |
| Telegram Bot | `src/notifications/telegram_bot.py` | 386 LOC | Notifications & alerts |
| Trade Duration Tracker | `src/utils/trade_duration_tracker.py` | 174 LOC | Position lifecycle tracking |
| Order Manager | `order_manager.py` | 23 KB | Order execution & management |
| Risk Manager | `risk_manager.py` | 36 KB | Position sizing & risk controls |
| System Logger | `system_logger.py` | Comprehensive logging system |
| Trade Tracker | `trade_tracker.py` | Trade lifecycle logging |

#### Key Features:
- **Market Regime Detection**: ACTIVE (bearish alignment) vs INACTIVE
- **Multi-Level Exit Strategy**: 
  - Regime-based exit (highest priority)
  - Time-based exit (24-hour max)
  - Stop-loss (1.5%)
  - Take-profit (6%)
- **Cooldown Mechanisms**: 1-hour pause after quick exits
- **Daily Cross Limits**: Max 12 EMA crosses per asset per day
- **Real-time Monitoring**: Position tracking without exchange queries

#### Data Entry Points:
- Live Bybit feed (5-minute intervals)
- Market regime analysis every bar
- Trade notifications to Telegram

---

### 2. LXALGO - CFT Prop Trading Bot

**Strategy**: Technical Analysis-based Trading  
**Infrastructure**: Standalone (no external DB)  
**Status**: Production Ready  
**Code**: ~4,397 lines (modular architecture)

#### Core Components:

| Component | File | Size | Purpose |
|-----------|------|------|---------|
| Trading Engine | `src/core/trading_engine.py` | - | Main trading engine |
| Trade Executor | `src/trading/executor.py` | 488 LOC | Trade execution logic |
| Market Data | `src/data/market_data.py` | 158 LOC | Data management |
| WebSocket Feed | `src/data/websocket.py` | 115 LOC | Real-time market data |
| Indicators | `src/data/indicators.py` | 93 LOC | Technical indicators |
| Configuration | `src/config/settings.py` | Config management |
| Utilities | `src/utils/helpers.py` | 156 LOC | Helper functions |

#### Trading Parameters:
- **Position Sizing**: 200 USD base
- **Max Active Trades**: 20 concurrent
- **Stop Loss**: 8%
- **Take Profit**: 30%
- **Breakeven Threshold**: 8% profit
- **Trailing Stop**: Activation at 20%, offset 10%

#### Risk Management Features:
- **Daily Equity Drawdown**: 2% circuit breaker
- **Weekly Equity Drawdown**: 
  - 4% triggers 50% position size reduction
  - 6% halts trading until Monday
- **Trade Age Limits**: 72-hour auto-expiry
- **Negative PnL Rule**: 8-hour auto-close for losing trades
- **Symbol Cooldown**: 4-hour intervals

---

### 3. MOMENTUM - Momentum Strategy Bot

**Strategy**: Volatility Breakout + 4H Altcoin Trading  
**Infrastructure**: SQLite (local database)  
**Performance**: 252% return over 27 months (306 trades, 37.6% win rate)  
**Status**: Production Ready  
**Code**: 10,384 lines

#### Core Components:

| Component | File | Size | Purpose |
|-----------|------|------|---------|
| Main System | `trading_system.py` | - | Central orchestration |
| Trade Database | `database/trade_database.py` | 15 KB | SQLite trade logging |
| Exchange Wrapper | `exchange/bybit_exchange.py` | 16 KB | Bybit integration |
| Data Loader | `data/data_loader.py` | - | Historical data loading |
| Data Validator | `data/data_validator.py` | 10 KB | Data validation |
| Bybit API | `data/bybit_api.py` | 17 KB | API client |
| Entry Signals | `signals/entry_signals.py` | 212 LOC | Entry logic |
| Exit Signals | `signals/exit_signals.py` | 294 LOC | Exit logic |
| BTC Regime Filter | `signals/btc_regime_filter.py` | 170 LOC | BTC-based filtering |

#### Entry Criteria (ALL must be met):
1. **Volatility Compression**: BBWidth < 35th percentile (90-day lookback)
2. **Risk/Reward Setup**: RVR > 2.0 (2x+ reward vs risk)
3. **Momentum Confirmation**: Price action on 4H timeframe
4. **Position Sizing**: 5% risk per trade, max 3 positions
5. **BTC Regime Filter**: When available

#### Exit Strategy:
- **Primary (71% of trades)**: MA Exit (20-period MA cross)
- **Backup (29% of trades)**: 10% Trailing Stop (exchange-side)
- **Hybrid Protection**: Software + exchange-side redundancy

#### Risk Management:
- **Daily Loss Limit**: -3% (stops new entries)
- **Weekly Loss Limit**: -8% (reduces size 50%)
- **Max Positions**: 3 concurrent
- **Max Drawdown**: -23.11% (backtest)

#### Data Sources:
- **Historical**: `/home/william/STRATEGIES/datawarehouse/bybit_data/`
- **Real-time**: Bybit WebSocket + API
- **Cache**: `data/cache/` directory
- **Database**: SQLite at `data/trading.db` (49 KB)

---

## DATABASE SYSTEMS

### 1. PostgreSQL (Shortseller Only)

**Purpose**: Multi-asset trading data persistence  
**Container**: `shortseller-postgres` (postgres:14)  
**Port**: 5433 (external), 5432 (internal)  
**Database**: `multiasset_trading`  
**User**: `trading_user`  
**Connection String**: `postgresql://trading_user:secure_password@shortseller-postgres:5432/multiasset_trading`

#### Schema (`init-db.sql` - 148 lines):

```sql
SCHEMA: trading

TABLES:
├── trades (8 columns)
│   ├── id, symbol, side, quantity, price
│   ├── order_id, exchange_order_id, status
│   ├── strategy, timestamp, executed_at
│   ├── pnl, fees, notes
│   └── Indexes: symbol_timestamp, status
│
├── positions (9 columns)
│   ├── id, symbol, side, size, avg_price
│   ├── unrealized_pnl, realized_pnl, status
│   ├── opened_at, closed_at
│   ├── stop_loss, take_profit, leverage
│   └── Indexes: symbol_status
│
├── market_data (9 columns)
│   ├── id, symbol, timestamp
│   ├── open_price, high_price, low_price, close_price
│   ├── volume, interval
│   └── Indexes: symbol_timestamp, interval
│
├── signals (8 columns)
│   ├── id, symbol, signal_type, strength
│   ├── price, timestamp, strategy
│   ├── indicators (JSONB), executed
│   ├── execution_id (FK to trades.id)
│   └── Indexes: symbol_timestamp, executed
│
├── account_balance (5 columns)
│   ├── id, total_balance, available_balance
│   ├── equity, margin_used, unrealized_pnl
│   ├── timestamp
│
├── risk_metrics (10 columns)
│   ├── id, date, total_pnl
│   ├── max_drawdown, win_rate, profit_factor
│   ├── sharpe_ratio, total_trades
│   ├── winning_trades, losing_trades
│   └── UNIQUE: date
│
└── Views:
    ├── active_positions (positions with trade count)
    └── daily_performance (daily aggregates)
```

**Health Check**: `pg_isready -U trading_user -d multiasset_trading`

---

### 2. SQLite (Momentum Only)

**Purpose**: Trade logging and performance tracking  
**Location**: `momentum/data/trading.db`  
**Size**: 49 KB  
**Schema Definition**: `momentum/database/trade_database.py`

#### Tables:

```sqlite
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE,
    mode TEXT NOT NULL,           -- 'demo' or 'live'
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,           -- 'long' or 'short'
    entry_time TIMESTAMP NOT NULL,
    entry_price REAL NOT NULL,
    exit_time TIMESTAMP,
    exit_price REAL,
    quantity REAL NOT NULL,
    position_size_usd REAL NOT NULL,
    stop_loss REAL,
    take_profit REAL,
    pnl_usd REAL,
    pnl_pct REAL,
    exit_reason TEXT,
    holding_time_seconds INTEGER,
    signal_strength REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

CREATE TABLE daily_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    mode TEXT NOT NULL,
    starting_equity REAL NOT NULL,
    ending_equity REAL NOT NULL,
    daily_pnl REAL NOT NULL,
    daily_pnl_pct REAL NOT NULL,
    trades_count INTEGER DEFAULT 0,
    wins_count INTEGER DEFAULT 0,
    losses_count INTEGER DEFAULT 0,
    open_positions INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

CREATE TABLE system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    event_level TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

CREATE TABLE risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TIMESTAMP NOT NULL,
    risk_type TEXT NOT NULL,
    current_value REAL NOT NULL,
    limit_value REAL NOT NULL,
    action_taken TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

INDEXES:
├── idx_trades_symbol ON trades(symbol)
├── idx_trades_entry_time ON trades(entry_time)
├── idx_trades_mode ON trades(mode)
└── idx_daily_date ON daily_snapshots(date)
```

**Access**: `sqlite3 momentum/data/trading.db`

---

### 3. Redis Cache (Shortseller Only)

**Purpose**: Caching & session management  
**Container**: `shortseller-redis` (redis:6-alpine)  
**Port**: 6379  
**Connection String**: `redis://shortseller-redis:6379/0`  
**Persistence**: RDB snapshots (`--appendonly yes`)

**Health Check**: `redis-cli ping` → PONG

---

## CONFIGURATION & ENVIRONMENT

### Master Environment File: `.env`

Located at: `/home/william/STRATEGIES/Alpha/.env`

```env
# ========== SHORTSELLER ==========
SHORTSELLER_BYBIT_API_KEY=REDACTED_API_KEY
SHORTSELLER_BYBIT_API_SECRET=REDACTED_API_SECRET
SHORTSELLER_TELEGRAM_BOT_TOKEN=REDACTED_TELEGRAM_BOT_TOKEN
SHORTSELLER_TELEGRAM_CHANNEL_ID=8133993135
SHORTSELLER_TELEGRAM_ADMIN_CHAT_ID=8133993135

# ========== TELEGRAM C2 ==========
C2_TELEGRAM_BOT_TOKEN=REDACTED_C2_BOT_TOKEN
C2_TELEGRAM_ADMIN_IDS=8133993135

# Database credentials in docker-compose.yml directly
# (See docker-compose.yml for PostgreSQL and Redis config)
```

### Individual Project .env Files:

#### `shortseller/.env`
```env
BYBIT_API_KEY=REDACTED_API_KEY
BYBIT_API_SECRET=REDACTED_API_SECRET
BYBIT_TESTNET=true
POSTGRES_HOST=localhost
POSTGRES_DB=multiasset_trading
REDIS_HOST=localhost
TELEGRAM_BOT_TOKEN=REDACTED_TELEGRAM_BOT_TOKEN
[Risk parameters, portfolio config, etc.]
```

#### `lxalgo/.env`
```env
BYBIT_API_KEY=REDACTED_LXALGO_API_KEY
BYBIT_API_SECRET=REDACTED_LXALGO_API_SECRET
BYBIT_USE_DEMO=True
TELEGRAM_BOT_TOKEN=REDACTED_LXALGO_BOT_TOKEN
TELEGRAM_CHAT_ID=8133993135
```

#### `momentum/.env`
```env
BYBIT_DEMO_API_KEY=REDACTED_MOMENTUM_API_KEY
BYBIT_DEMO_API_SECRET=REDACTED_MOMENTUM_API_SECRET
BYBIT_LIVE_API_KEY=[EMPTY - for live trading]
BYBIT_LIVE_API_SECRET=[EMPTY - for live trading]
TELEGRAM_BOT_TOKEN=REDACTED_MOMENTUM_BOT_TOKEN
TELEGRAM_CHAT_ID=8133993135
TELEGRAM_ENABLED=true
```

#### `telegram_manager/.env`
```env
TELEGRAM_BOT_TOKEN=REDACTED_C2_BOT_TOKEN
TELEGRAM_ADMIN_IDS=8133993135
```

### Configuration Files:

#### Shortseller: `shortseller/config/settings.py`
- Exchange configuration (API, testnet/demo flags)
- Database connection parameters
- Risk parameters (stop-loss, take-profit, leverage)
- Portfolio allocation

#### LXAlgo: `lxalgo/settings.py`
- API configuration & timeout settings
- Trading strategy parameters (position size, stops)
- Risk management thresholds
- Cooldown intervals
- Check intervals (balance, PnL, reconciliation)

#### Momentum: `momentum/config/trading_config.py`
- **Trading Mode Enum**: DEMO or LIVE
- **Exchange Config**: API key loading from environment
- **Risk Config**: Position sizing, loss limits, drawdown
- **Asset Configuration**: Trading universe definition
- Demo/Live switching mechanism (no code changes needed)

---

## DATA FLOW ARCHITECTURE

### SHORTSELLER Data Flow

```
Bybit V5 API (Real-time 5min bars)
    ↓
BybitClient (src/exchange/bybit_client.py)
    ├→ Fetch current prices
    ├→ Calculate EMAs (240, 600)
    └→ Submit orders
    ↓
MarketData Processing
    ├→ EMA calculations
    ├→ Market regime detection (ACTIVE/INACTIVE)
    └→ Cross detection
    ↓
MultiAssetStrategyEngine (src/core/strategy_engine.py)
    ├→ Signal generation (ENTER_SHORT, EXIT, NO_ACTION)
    ├→ Position state tracking
    ├→ Cooldown management
    └→ Daily cross limit tracking
    ↓
Order Manager (order_manager.py)
    ├→ Quantity validation & rounding
    ├→ Order submission to exchange
    ├→ Order tracking
    └→ Precision handling
    ↓
PostgreSQL (trading schema)
    ├→ trades table (entry, exit, pnl)
    ├→ positions table (current holdings)
    ├→ market_data table (historical)
    ├→ signals table (entry/exit signals)
    └→ account_balance table (equity snapshots)
    ↓
Risk Manager (risk_manager.py)
    ├→ Position sizing (7% allocation)
    ├→ Leverage calculation (10x)
    ├→ Drawdown monitoring
    └→ Stop-loss / Take-profit management
    ↓
Telegram Bot (src/notifications/telegram_bot.py)
    └→ Trade alerts, regime changes, cooldown status
```

### LXALGO Data Flow

```
Bybit Exchange (Live feeds)
    ↓
Market Data Manager (src/data/market_data.py)
    ├→ Symbol fetching with volume filter
    ├→ Historical kline data
    └→ Real-time price updates
    ↓
WebSocket Manager (src/data/websocket.py)
    └→ Real-time market stream
    ↓
Indicators (src/data/indicators.py)
    └→ Technical analysis calculations
    ↓
Trading Engine (src/core/trading_engine.py)
    ├→ Signal generation (8 rules)
    └→ Position management
    ↓
Trade Executor (src/trading/executor.py)
    ├→ Order placement
    ├→ Stop loss management
    ├→ Take profit execution
    └→ Breakeven moves
    ↓
Risk Management (settings.py)
    ├→ Equity drawdown tracking
    ├→ Daily circuit breakers
    ├→ Weekly progressive reduction
    └→ Trade age limits
    ↓
In-Memory State (no external DB)
    ├→ Active positions
    ├→ Trade history
    └→ Performance metrics
    ↓
Telegram Alerts
    └→ Real-time notifications
```

### MOMENTUM Data Flow

```
Data Sources:
├─→ /home/william/STRATEGIES/datawarehouse/bybit_data/ (CSV files)
│   └→ Format: {symbol}/{date}_1m.csv
│
└─→ Bybit Live API (real-time)

Data Loader (data/data_loader.py)
    ├→ Scans datawarehouse for available symbols
    ├→ Loads 1-minute CSV data
    ├→ Resamples to 4H (daily) timeframe
    └→ Handles date ranges (default: 90 days)
    ↓
Data Validator (data/data_validator.py)
    ├→ OHLCV integrity checks
    ├→ Gap detection
    ├→ Missing data validation
    └→ Data quality metrics
    ↓
Technical Indicators (indicators/)
    ├→ Bollinger Bands (bollinger_bands.py)
    │  └→ BBWidth percentile calculation
    ├→ Moving Averages (moving_averages.py)
    │  └→ 20, 50-period MAs
    ├→ Volume Analysis (volume.py)
    │  └→ Relative Volume Ratio (RVR)
    └─→ ADX (adx.py)
    ↓
Signal Generation (signals/)
    ├→ Entry Signals (entry_signals.py)
    │  ├→ BBWidth compression check
    │  ├→ Breakout confirmation
    │  ├→ RVR expansion check
    │  └→ MA trend confirmation
    ├→ Exit Signals (exit_signals.py)
    │  ├→ MA cross detection
    │  ├→ Stop-loss check
    │  ├→ Take-profit check
    │  └→ 10% trailing stop
    └─→ BTC Regime Filter (btc_regime_filter.py)
        └→ BTC > 50-day MA confirmation
    ↓
Trading System (trading_system.py)
    ├→ Position sizing (5% risk per trade)
    ├→ Max 3 concurrent positions
    ├→ Entry execution
    └─→ Exit management
    ↓
Exchange Wrapper (exchange/bybit_exchange.py)
    ├→ Order placement (long/short)
    ├→ Position updates
    └─→ Order cancellation
    ↓
SQLite Database (data/trading.db)
    ├→ trades table (full trade lifecycle)
    ├→ daily_snapshots table (daily performance)
    ├→ system_events table (system events)
    └─→ risk_events table (risk breaches)
    ↓
Risk Management
    ├→ Daily loss limit (-3%)
    ├→ Weekly loss limit (-8%)
    ├→ Max drawdown tracking
    └─→ Position reconciliation
    ↓
Telegram Bot (alerts/telegram_bot.py)
    ├→ Entry/exit notifications
    ├→ Daily performance reports
    └─→ Risk event alerts
```

---

## DEPENDENCIES & REQUIREMENTS

### SHORTSELLER: `shortseller/requirements.txt`

```
Core Dependencies:
├── pandas>=2.0.0          (Data manipulation)
├── numpy>=1.24.0          (Numerical computing)
├── websockets>=11.0.0     (Real-time feeds)
├── aiohttp>=3.8.0         (Async HTTP)
└── asyncio-mqtt>=0.13.0   (MQTT async)

Exchange Integration:
├── requests>=2.28.0       (HTTP client)
├── cryptography>=40.0.0   (Encryption)
└── ccxt>=4.0.0            (Multi-exchange)

Database:
├── psycopg2-binary>=2.9.0 (PostgreSQL adapter)
├── sqlalchemy>=2.0.0      (ORM)
└── alembic>=1.11.0        (DB migrations)

Cache:
└── redis>=4.5.0           (Redis client)

Notifications:
├── python-telegram-bot>=20.0.0
└── discord.py>=2.3.0

Configuration:
├── pyyaml>=6.0.0
└── python-dotenv>=1.0.0

Monitoring:
├── colorlog>=6.7.0
└── prometheus-client>=0.16.0

Web Interface:
├── fastapi>=0.100.0
├── uvicorn>=0.22.0
└── websockets>=11.0.0

Development:
├── pytest>=7.4.0
├── pytest-asyncio>=0.21.0
├── black>=23.0.0
├── flake8>=6.0.0
├── mypy>=1.4.0
└── bandit>=1.7.0

System Monitoring:
├── psutil>=5.9.0
└── memory-profiler>=0.61.0
```

### LXALGO: `lxalgo/requirements.txt`

```
Core Dependencies:
├── aiohttp>=3.8.0
├── asyncio-tools>=0.0.4
├── pandas>=2.0.0
├── websockets>=11.0.0
├── requests>=2.28.0
└── numpy>=1.24.0

Technical Analysis:
├── ta>=0.8.0              (Technical Analysis library)
├── reportlab>=4.0.0       (PDF generation)
└── matplotlib>=3.7.0      (Plotting)

Utilities:
├── python-dotenv>=1.0.0
└── nest-asyncio>=1.5.6

Optional (Commented out):
├── fastapi>=0.95.0
├── uvicorn[standard]>=0.22.0
├── prometheus_client>=0.16.0
├── pytest>=7.0.0
├── responses>=0.23.0
└── aioresponses>=0.7.2
```

### MOMENTUM: `momentum/requirements.txt`

```
Core Dependencies:
├── pandas>=1.5.0
├── numpy>=1.23.0
└── requests>=2.28.0

Exchange Integration:
└── pybit>=5.6.0           (Bybit Python wrapper)

Database:
└── sqlite3 (built-in)

Testing:
└── pytest>=7.4.0

Note: python-dotenv optional - custom .env loader in use
```

### TELEGRAM_MANAGER: `telegram_manager/requirements.txt`

```
├── python-telegram-bot==20.7
├── docker==7.0.0
├── psycopg2-binary==2.9.9
├── redis==5.0.1
├── requests==2.31.0
└── python-dotenv==1.0.0
```

---

## DEPLOYMENT ARCHITECTURE

### Docker Compose Services

**File**: `/home/william/STRATEGIES/Alpha/docker-compose.yml`

```yaml
SERVICES (5 total):

1. shortseller-postgres
   ├─ Image: postgres:14
   ├─ Container: shortseller_postgres
   ├─ Port: 5433:5432 (external:internal)
   ├─ Volume: shortseller_postgres_data:/var/lib/postgresql/data
   ├─ Init Script: ./shortseller/init-db.sql
   └─ Health Check: pg_isready

2. shortseller-redis
   ├─ Image: redis:6-alpine
   ├─ Container: shortseller_redis
   ├─ Port: 6379:6379
   ├─ Volume: shortseller_redis_data:/data
   ├─ Command: redis-server --appendonly yes
   └─ Health Check: redis-cli ping

3. shortseller
   ├─ Build Context: ./shortseller/
   ├─ Container: shortseller_trading
   ├─ Dependencies: DB and Redis (must be healthy)
   ├─ Env: API keys, DB credentials, portfolio config
   ├─ Command: python scripts/start_trading.py
   ├─ Volumes:
   │  ├─ ./shortseller/logs:/app/logs
   │  └─ ./shortseller/config:/app/config
   ├─ Health Check: pgrep -f start_trading.py
   ├─ Memory: 900m limit, 700m reservation
   └─ Network: trading-network

4. lxalgo
   ├─ Build Context: ./lxalgo/
   ├─ Container: lxalgo_trading
   ├─ Env File: ./lxalgo/.env
   ├─ Command: python main.py
   ├─ Volumes: ./lxalgo:/app, lxalgo_logs:/app/logs
   ├─ Health Check: pgrep -f main.py
   ├─ Memory: 900m limit, 700m reservation
   ├─ TCP Keep-alive: Configured
   └─ Network: trading-network

5. momentum
   ├─ Build Context: ./momentum/
   ├─ Container: momentum_trading
   ├─ Env File: ./momentum/.env
   ├─ Command: python trading_system.py
   ├─ Volumes:
   │  ├─ ./momentum/logs:/app/logs
   │  ├─ ./momentum/database:/app/database
   │  ├─ ./momentum/data/cache:/app/data/cache
   │  └─ momentum_data:/app/data
   ├─ Health Check: pgrep -f trading_system.py
   ├─ Memory: 900m limit, 700m reservation
   ├─ TCP Keep-alive: Configured
   └─ Network: trading-network

6. telegram_manager
   ├─ Build Context: ./telegram_manager/
   ├─ Container: telegram_c2
   ├─ Env: Bot token, admin IDs, Docker socket
   ├─ Volumes:
   │  ├─ /var/run/docker.sock:/var/run/docker.sock:ro
   │  ├─ ./telegram_manager/logs:/app/logs
   │  └─ ./telegram_manager/config:/app/config
   ├─ Memory: 256m limit, 128m reservation
   └─ Network: trading-network

VOLUMES (4 total):
├── shortseller_postgres_data    (PostgreSQL data)
├── shortseller_redis_data       (Redis persistence)
├── lxalgo_logs
└── momentum_data

NETWORKS:
└── trading-network (bridge driver)
```

### Startup Sequence

```
1. PostgreSQL starts → health check (30s interval, 5 retries)
2. Redis starts → health check (30s interval, 5 retries)
3. Shortseller depends on both → waits for healthy
4. LXAlgo → starts independently
5. Momentum → starts independently
6. Telegram Manager → starts independently
```

### Health Check Commands

```bash
# All services
docker compose -f docker-compose.yml ps

# PostgreSQL
docker compose -f docker-compose.yml exec shortseller-postgres pg_isready

# Redis
docker compose -f docker-compose.yml exec shortseller-redis redis-cli ping

# Trading bots
docker compose -f docker-compose.yml logs -f

# Individual service
docker compose -f docker-compose.yml logs -f [service-name]
```

---

## RISK MANAGEMENT & MONITORING

### SHORTSELLER Risk Controls

| Control | Setting | Purpose |
|---------|---------|---------|
| Leverage | 10x per asset | Position sizing |
| Portfolio Exposure | 21% max (3×7%) | Multi-asset limit |
| Stop Loss | 1.5% | Quick loss protection |
| Take Profit | 6% | Profit realization |
| Max Hold Time | 24 hours | Position aging |
| Daily Cross Limit | 12 per asset | Overtrading prevention |
| Quick Exit Cooldown | 1 hour | Prevents whipsaw |
| Regime-based Exit | ACTIVE→INACTIVE | Market condition exit |

### LXALGO Risk Controls

| Control | Setting | Purpose |
|---------|---------|---------|
| Daily Equity Drawdown | 2% | Circuit breaker |
| Weekly Drawdown L1 | 4% | Position size reduction |
| Weekly Drawdown L2 | 6% | Trading halt |
| Trade Max Age | 72 hours | Auto-expiry |
| Negative PnL | 8-hour rule | Automatic close |
| Symbol Cooldown | 4 hours | No repeat trading |
| Position Size | 200 USD base | Configurable |
| Max Active Trades | 20 | Concurrent limit |

### MOMENTUM Risk Controls

| Control | Setting | Purpose |
|---------|---------|---------|
| Daily Loss Limit | -3% | Stops new entries |
| Weekly Loss Limit | -8% | Reduces position 50% |
| Max Positions | 3 concurrent | Portfolio limit |
| Risk Per Trade | 5% | Position sizing |
| Stop Loss | Dynamic (chart-based) | Entry risk |
| Take Profit | Dynamic (RR based) | Exit target |
| Max Drawdown | 20% (historical) | System limit |
| Profit Factor | 2.18 (backtest) | Win/loss ratio |

### Monitoring & Logging

#### Shortseller Logs
- **Location**: `shortseller/logs/trading.log`
- **Rotation**: Daily with archival
- **Level**: INFO (configurable)
- **Content**:
  - Market regime changes
  - Entry/exit signals
  - Order execution
  - Position updates
  - Cooldown events

#### Momentum Logs
- **Location**: `momentum/logs/`
- **Database Logging**: SQLite (complete trade history)
- **Content**:
  - Trade entries/exits with full details
  - Daily snapshots (equity, PnL, trades)
  - System events (errors, warnings)
  - Risk events (limit breaches)

#### Real-time Monitoring
- **Telegram Alerts**: All three bots
- **Performance Reports**: Daily/weekly/monthly via Telegram
- **Exchange Position Reconciliation**: Periodic checks
- **Health Checks**: Container liveness probes

---

## INTEGRATION POINTS

### Cross-Bot Communication
- **Telegram**: Unified bot-to-user notifications
- **BTC Regime Filter**: Momentum uses BTC data for filtering
- **Shared Data Warehouse**: `datawarehouse/bybit_data/`

### Data Persistence
```
Shortseller → PostgreSQL
Momentum   → SQLite
LXAlgo     → In-memory (no external DB)
```

### API Integration
- **Bybit V5 API**: All bots
- **Telegram Bot API**: Notifications
- **Docker API**: Command center control

---

## QUICK REFERENCE

### Key Files

| Purpose | File | Lines |
|---------|------|-------|
| Main Compose | `docker-compose.yml` | 238 |
| Master Env | `.env` | 41 |
| Shortseller Schema | `shortseller/init-db.sql` | 148 |
| Shortseller Strategy | `shortseller/src/core/strategy_engine.py` | 726 |
| Momentum Main | `momentum/trading_system.py` | - |
| Momentum Config | `momentum/config/trading_config.py` | 100+ |
| Total Code | All Python files | ~16,644 |
| Documentation | All markdown files | 59+ KB |

### Command Reference

```bash
# Start all systems
docker compose -f docker-compose.yml up -d

# View logs
docker compose -f docker-compose.yml logs -f

# Stop all systems
docker compose -f docker-compose.yml down

# Access database
docker compose -f docker-compose.yml exec shortseller-postgres \
  psql -U trading_user -d multiasset_trading

# Rebuild a service
docker compose -f docker-compose.yml build --no-cache [service]
```

---

**End of System Architecture Map**

Generated: October 23, 2025  
Total Documentation: 59+ KB across 7 markdown files  
System Status: Production Ready
