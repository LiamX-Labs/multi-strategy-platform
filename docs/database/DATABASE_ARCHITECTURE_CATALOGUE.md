# DATABASE ARCHITECTURE CATALOGUE
## Unified Trading System Database Design

**Document Version:** 1.0
**Date:** 2025-10-24
**Author:** System Architect
**Purpose:** Comprehensive database design for the entire Alpha Trading System

---

## EXECUTIVE SUMMARY

This document provides a complete database architecture for the Alpha Trading System, consolidating all three trading bots (Shortseller, LXAlgo, Momentum) into a unified, scalable database infrastructure using PostgreSQL as the primary datastore with Redis for caching and InfluxDB for time-series market data.

### Key Design Principles

1. **Single Source of Truth**: One PostgreSQL database for all trading data
2. **Bot Isolation**: `bot_id` column in all tables for logical separation
3. **Scalability**: Designed to support unlimited bots without schema changes
4. **Performance**: Optimized indexes and partitioning strategies
5. **Auditability**: Complete audit trail with timestamps and user tracking
6. **Flexibility**: JSONB fields for strategy-specific data

---

## CURRENT STATE ANALYSIS

### Existing Database Systems

| Bot | Current Database | Tables | Issues |
|-----|-----------------|--------|--------|
| **Shortseller** | PostgreSQL (multiasset_trading) | 6 tables, 2 views | Single bot only, no multi-bot support |
| **Momentum** | SQLite (data/trading.db) | 4 tables | Isolated, no cross-bot analytics |
| **LXAlgo** | None (In-memory) | N/A | No persistence, data lost on restart |

### Identified Conflicts

#### 1. **Database Technology Fragmentation**
- **Conflict**: Three different storage approaches (PostgreSQL, SQLite, In-memory)
- **Impact**: No unified analytics, complex monitoring, data silos
- **Resolution**: Migrate all to PostgreSQL with bot_id segregation

#### 2. **Schema Inconsistencies**
- **Conflict**: Similar tables with different column names
  - Shortseller: `timestamp`, `pnl`, `qty`
  - Momentum: `entry_time`, `pnl_usd`, `quantity`
- **Impact**: Difficult to create unified reporting
- **Resolution**: Standardize column names across all tables

#### 3. **Missing Cross-Bot Features**
- **Conflict**: No system-wide risk monitoring or portfolio view
- **Impact**: Cannot see total exposure across all bots
- **Resolution**: Add aggregate views and cross-bot risk tables

#### 4. **Performance Data Storage**
- **Conflict**: Each bot calculates performance independently
- **Impact**: Inconsistent metrics, no unified performance tracking
- **Resolution**: Central performance_metrics table with bot_id

#### 5. **Market Data Duplication**
- **Conflict**: Each bot may fetch/store same market data
- **Impact**: Wasted storage and API calls
- **Resolution**: Shared market_data table with deduplication

---

## PROPOSED UNIFIED ARCHITECTURE

### Database Stack

```
┌─────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                      │
│  (Shortseller | LXAlgo | Momentum | Future Bots)       │
└──────────────────┬──────────────────────────────────────┘
                   │
       ┌───────────┼───────────┬──────────────┐
       │           │           │              │
       ▼           ▼           ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│PostgreSQL│ │  Redis   │ │ InfluxDB │ │ Grafana  │
│ (Primary)│ │ (Cache)  │ │(TimeSeries)│(Analytics)│
└──────────┘ └──────────┘ └──────────┘ └──────────┘
   Port 5432   Port 6379   Port 8086    Port 3000
```

### Technology Roles

| Technology | Purpose | Data Types | Retention |
|-----------|---------|------------|-----------|
| **PostgreSQL 15** | Primary transactional database | Trades, positions, orders, configuration | Permanent |
| **Redis 7** | Live state cache | Current positions, latest prices, locks | Ephemeral (with AOF backup) |
| **InfluxDB 2.7** | Time-series market data | OHLCV candles, tick data, indicators | 90 days rolling |
| **TimescaleDB** (Future) | Historical analytics | Archived market data, backtests | Years |

---

## UNIFIED DATABASE SCHEMA

### Schema Organization

```sql
-- Main trading schema
CREATE SCHEMA IF NOT EXISTS trading;

-- Analytics and reporting schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- System configuration schema
CREATE SCHEMA IF NOT EXISTS config;

-- Audit and logging schema
CREATE SCHEMA IF NOT EXISTS audit;
```

---

## CORE TABLES DESIGN

### 1. BOTS REGISTRY TABLE

**Purpose**: Central registry of all trading bots in the system

```sql
CREATE TABLE IF NOT EXISTS trading.bots (
    bot_id VARCHAR(50) PRIMARY KEY,
    bot_name VARCHAR(100) NOT NULL,
    bot_type VARCHAR(50) NOT NULL, -- 'shortseller', 'lxalgo', 'momentum', 'custom'
    strategy_name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'paused', 'stopped', 'archived'
    deployment_mode VARCHAR(20) NOT NULL, -- 'live', 'demo', 'backtest'

    -- Configuration
    initial_capital DECIMAL(20, 8) NOT NULL,
    current_equity DECIMAL(20, 8),
    max_positions INTEGER DEFAULT 3,
    leverage_limit INTEGER DEFAULT 1,

    -- Risk limits
    max_daily_loss_pct DECIMAL(5, 4),
    max_weekly_loss_pct DECIMAL(5, 4),
    max_drawdown_pct DECIMAL(5, 4),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'system',
    last_heartbeat TIMESTAMP WITH TIME ZONE,

    -- API Configuration (encrypted in production)
    api_key_hash VARCHAR(255),
    exchange VARCHAR(50) DEFAULT 'bybit',

    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'stopped', 'archived')),
    CONSTRAINT valid_mode CHECK (deployment_mode IN ('live', 'demo', 'backtest'))
);

CREATE INDEX idx_bots_status ON trading.bots(status);
CREATE INDEX idx_bots_type ON trading.bots(bot_type);
CREATE INDEX idx_bots_mode ON trading.bots(deployment_mode);

COMMENT ON TABLE trading.bots IS 'Central registry of all trading bots';
```

### 2. TRADES TABLE (Unified)

**Purpose**: All executed trades across all bots

```sql
CREATE TABLE IF NOT EXISTS trading.trades (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,

    -- Bot Association
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Trade Identification
    symbol VARCHAR(20) NOT NULL,
    exchange_order_id VARCHAR(100),

    -- Trade Details
    side VARCHAR(10) NOT NULL, -- 'buy', 'sell', 'long', 'short'
    trade_type VARCHAR(20) DEFAULT 'market', -- 'market', 'limit', 'stop_market'

    -- Quantities and Prices
    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    avg_fill_price DECIMAL(20, 8),

    -- Position Sizing
    position_size_usd DECIMAL(20, 8) NOT NULL,
    leverage INTEGER DEFAULT 1,

    -- Risk Management
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    trailing_stop_pct DECIMAL(5, 4),

    -- Trade Status
    status VARCHAR(20) DEFAULT 'pending',
    -- 'pending', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired'

    -- Timing
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    holding_time_seconds INTEGER,

    -- Performance
    pnl_usd DECIMAL(20, 8) DEFAULT 0,
    pnl_pct DECIMAL(10, 6) DEFAULT 0,
    fees DECIMAL(20, 8) DEFAULT 0,
    commission DECIMAL(20, 8) DEFAULT 0,
    slippage DECIMAL(20, 8) DEFAULT 0,

    -- Exit Information
    exit_reason VARCHAR(50),
    -- 'take_profit', 'stop_loss', 'trailing_stop', 'manual', 'time_exit',
    -- 'risk_limit', 'signal_reversal', 'market_close'

    -- Strategy Context
    strategy VARCHAR(50) NOT NULL,
    signal_strength DECIMAL(5, 4),
    confidence_score DECIMAL(5, 4),
    strategy_params JSONB, -- Strategy-specific parameters

    -- Market Context
    market_regime VARCHAR(30), -- 'trending_up', 'trending_down', 'ranging', 'volatile'
    entry_conditions JSONB, -- Indicators at entry
    exit_conditions JSONB, -- Indicators at exit

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT valid_side CHECK (side IN ('buy', 'sell', 'long', 'short')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired')),
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT positive_price CHECK (entry_price > 0)
);

-- Indexes for performance
CREATE INDEX idx_trades_bot_id ON trading.trades(bot_id);
CREATE INDEX idx_trades_symbol ON trading.trades(symbol);
CREATE INDEX idx_trades_entry_time ON trading.trades(entry_time);
CREATE INDEX idx_trades_status ON trading.trades(status);
CREATE INDEX idx_trades_bot_symbol ON trading.trades(bot_id, symbol);
CREATE INDEX idx_trades_bot_time ON trading.trades(bot_id, entry_time DESC);
CREATE INDEX idx_trades_exit_time ON trading.trades(exit_time) WHERE exit_time IS NOT NULL;

-- Partial index for open trades
CREATE INDEX idx_trades_open ON trading.trades(bot_id, symbol) WHERE exit_time IS NULL;

-- GIN index for JSONB columns
CREATE INDEX idx_trades_strategy_params ON trading.trades USING GIN(strategy_params);
CREATE INDEX idx_trades_entry_conditions ON trading.trades USING GIN(entry_conditions);

COMMENT ON TABLE trading.trades IS 'All executed trades across all bots with unified schema';
```

### 3. POSITIONS TABLE (Unified)

**Purpose**: Current and historical positions for all bots

```sql
CREATE TABLE IF NOT EXISTS trading.positions (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    position_id VARCHAR(100) UNIQUE NOT NULL,

    -- Bot Association
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Position Details
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL, -- 'long', 'short'

    -- Quantities
    size DECIMAL(20, 8) NOT NULL,
    avg_entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    leverage INTEGER DEFAULT 1,

    -- P&L
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_pnl DECIMAL(20, 8) DEFAULT 0,
    unrealized_pnl_pct DECIMAL(10, 6) DEFAULT 0,

    -- Risk Management
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    trailing_stop_pct DECIMAL(5, 4),
    highest_price DECIMAL(20, 8), -- For trailing stops
    lowest_price DECIMAL(20, 8), -- For trailing stops

    -- Position Status
    status VARCHAR(20) DEFAULT 'open',
    -- 'open', 'partially_closed', 'closed', 'liquidated'

    -- Timing
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Associated Trades
    entry_trade_ids TEXT[], -- Array of trade IDs that opened this position
    exit_trade_ids TEXT[], -- Array of trade IDs that closed this position

    -- Strategy Context
    strategy VARCHAR(50) NOT NULL,
    entry_signal JSONB,
    position_metadata JSONB,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT valid_side CHECK (side IN ('long', 'short')),
    CONSTRAINT valid_status CHECK (status IN ('open', 'partially_closed', 'closed', 'liquidated')),
    CONSTRAINT positive_size CHECK (size > 0)
);

-- Indexes
CREATE INDEX idx_positions_bot_id ON trading.positions(bot_id);
CREATE INDEX idx_positions_symbol ON trading.positions(symbol);
CREATE INDEX idx_positions_status ON trading.positions(status);
CREATE INDEX idx_positions_bot_symbol ON trading.positions(bot_id, symbol);
CREATE INDEX idx_positions_opened_at ON trading.positions(opened_at);

-- Partial index for open positions (most frequently queried)
CREATE INDEX idx_positions_open ON trading.positions(bot_id, symbol, status) WHERE status = 'open';

-- GIN index for arrays
CREATE INDEX idx_positions_entry_trades ON trading.positions USING GIN(entry_trade_ids);

COMMENT ON TABLE trading.positions IS 'Current and historical positions for all bots';
```

### 4. ORDERS TABLE

**Purpose**: All order submissions (whether filled or not)

```sql
CREATE TABLE IF NOT EXISTS trading.orders (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,

    -- Bot Association
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Order Details
    symbol VARCHAR(20) NOT NULL,
    exchange_order_id VARCHAR(100),
    client_order_id VARCHAR(100),

    -- Order Type
    order_type VARCHAR(20) NOT NULL,
    -- 'market', 'limit', 'stop_market', 'stop_limit', 'trailing_stop'
    side VARCHAR(10) NOT NULL, -- 'buy', 'sell'

    -- Quantities and Prices
    quantity DECIMAL(20, 8) NOT NULL,
    filled_quantity DECIMAL(20, 8) DEFAULT 0,
    remaining_quantity DECIMAL(20, 8),
    price DECIMAL(20, 8), -- Limit price (NULL for market orders)
    avg_fill_price DECIMAL(20, 8),
    stop_price DECIMAL(20, 8), -- For stop orders

    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    -- 'pending', 'submitted', 'partially_filled', 'filled', 'cancelled',
    -- 'rejected', 'expired', 'failed'

    -- Timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE,
    filled_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Fees
    fees DECIMAL(20, 8) DEFAULT 0,
    commission DECIMAL(20, 8) DEFAULT 0,

    -- Order Purpose
    order_purpose VARCHAR(30),
    -- 'entry', 'exit', 'stop_loss', 'take_profit', 'reduce_only', 'scale_in', 'scale_out'

    -- Associated Entities
    position_id VARCHAR(100), -- Link to position if applicable
    trade_id VARCHAR(100), -- Link to resulting trade

    -- Error Handling
    rejection_reason TEXT,
    error_code VARCHAR(50),
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    order_metadata JSONB,

    CONSTRAINT valid_order_type CHECK (order_type IN ('market', 'limit', 'stop_market', 'stop_limit', 'trailing_stop')),
    CONSTRAINT valid_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'submitted', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired', 'failed')),
    CONSTRAINT positive_quantity CHECK (quantity > 0)
);

-- Indexes
CREATE INDEX idx_orders_bot_id ON trading.orders(bot_id);
CREATE INDEX idx_orders_symbol ON trading.orders(symbol);
CREATE INDEX idx_orders_status ON trading.orders(status);
CREATE INDEX idx_orders_exchange_id ON trading.orders(exchange_order_id);
CREATE INDEX idx_orders_created_at ON trading.orders(created_at DESC);
CREATE INDEX idx_orders_position_id ON trading.orders(position_id) WHERE position_id IS NOT NULL;

-- Partial index for active orders
CREATE INDEX idx_orders_active ON trading.orders(bot_id, symbol)
    WHERE status IN ('pending', 'submitted', 'partially_filled');

COMMENT ON TABLE trading.orders IS 'All order submissions across all bots';
```

### 5. MARKET DATA TABLE

**Purpose**: Shared OHLCV candle data for all symbols

```sql
CREATE TABLE IF NOT EXISTS trading.market_data (
    -- Composite primary key (symbol, interval, timestamp)
    id BIGSERIAL PRIMARY KEY,

    -- Market Identification
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(50) DEFAULT 'bybit',
    interval VARCHAR(10) NOT NULL, -- '1m', '5m', '15m', '1h', '4h', '1d'

    -- OHLCV Data
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    quote_volume DECIMAL(20, 8),

    -- Additional Metrics
    trades_count INTEGER,
    taker_buy_volume DECIMAL(20, 8),
    taker_sell_volume DECIMAL(20, 8),

    -- Derived Indicators (commonly used)
    ema_20 DECIMAL(20, 8),
    ema_50 DECIMAL(20, 8),
    ema_200 DECIMAL(20, 8),
    rsi_14 DECIMAL(10, 6),
    atr_14 DECIMAL(20, 8),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'exchange', -- 'exchange', 'calculated', 'backfill'

    CONSTRAINT unique_candle UNIQUE(symbol, interval, timestamp),
    CONSTRAINT valid_ohlc CHECK (
        high_price >= low_price AND
        high_price >= open_price AND
        high_price >= close_price AND
        low_price <= open_price AND
        low_price <= close_price
    )
);

-- Indexes for time-series queries
CREATE INDEX idx_market_data_symbol_interval ON trading.market_data(symbol, interval, timestamp DESC);
CREATE INDEX idx_market_data_timestamp ON trading.market_data(timestamp DESC);
CREATE INDEX idx_market_data_symbol ON trading.market_data(symbol);

-- Partial indexes for common intervals
CREATE INDEX idx_market_data_1h ON trading.market_data(symbol, timestamp DESC) WHERE interval = '1h';
CREATE INDEX idx_market_data_4h ON trading.market_data(symbol, timestamp DESC) WHERE interval = '4h';
CREATE INDEX idx_market_data_1d ON trading.market_data(symbol, timestamp DESC) WHERE interval = '1d';

COMMENT ON TABLE trading.market_data IS 'Shared market data (OHLCV) for all symbols and timeframes';
```

### 6. SIGNALS TABLE

**Purpose**: All generated trading signals before execution

```sql
CREATE TABLE IF NOT EXISTS trading.signals (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(100) UNIQUE NOT NULL,

    -- Bot Association
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Signal Details
    symbol VARCHAR(20) NOT NULL,
    signal_type VARCHAR(20) NOT NULL, -- 'long', 'short', 'close_long', 'close_short', 'hold'
    strength DECIMAL(5, 4) DEFAULT 1.0, -- Signal strength 0-1
    confidence DECIMAL(5, 4), -- Confidence level 0-1

    -- Pricing
    price DECIMAL(20, 8) NOT NULL,
    suggested_stop_loss DECIMAL(20, 8),
    suggested_take_profit DECIMAL(20, 8),
    suggested_position_size DECIMAL(20, 8),

    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP WITH TIME ZONE, -- Signal expiry

    -- Strategy Context
    strategy VARCHAR(50) NOT NULL,
    indicators JSONB, -- All indicator values at signal time
    market_conditions JSONB,

    -- Execution Status
    executed BOOLEAN DEFAULT FALSE,
    execution_time TIMESTAMP WITH TIME ZONE,
    execution_order_id VARCHAR(100),
    execution_trade_id VARCHAR(100),

    -- Signal Rejection/Filtering
    rejected BOOLEAN DEFAULT FALSE,
    rejection_reason VARCHAR(100),
    passed_filters JSONB, -- Which filters passed/failed

    -- Performance Tracking
    outcome VARCHAR(20), -- 'winner', 'loser', 'breakeven', 'not_executed'
    outcome_pnl DECIMAL(20, 8),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT valid_signal_type CHECK (signal_type IN ('long', 'short', 'close_long', 'close_short', 'hold')),
    CONSTRAINT valid_strength CHECK (strength >= 0 AND strength <= 1),
    CONSTRAINT valid_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

-- Indexes
CREATE INDEX idx_signals_bot_id ON trading.signals(bot_id);
CREATE INDEX idx_signals_symbol ON trading.signals(symbol);
CREATE INDEX idx_signals_timestamp ON trading.signals(timestamp DESC);
CREATE INDEX idx_signals_executed ON trading.signals(executed);
CREATE INDEX idx_signals_bot_symbol ON trading.signals(bot_id, symbol, timestamp DESC);

-- GIN index for JSONB
CREATE INDEX idx_signals_indicators ON trading.signals USING GIN(indicators);

COMMENT ON TABLE trading.signals IS 'All generated trading signals before execution';
```

### 7. ACCOUNT BALANCE TABLE

**Purpose**: Track account balance history for all bots

```sql
CREATE TABLE IF NOT EXISTS trading.account_balance (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,

    -- Bot Association
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Balance Information
    total_balance DECIMAL(20, 8) NOT NULL,
    available_balance DECIMAL(20, 8) NOT NULL,
    locked_balance DECIMAL(20, 8) DEFAULT 0,
    equity DECIMAL(20, 8) NOT NULL,

    -- Margin Information
    margin_used DECIMAL(20, 8) DEFAULT 0,
    margin_available DECIMAL(20, 8),
    margin_level DECIMAL(10, 6), -- Margin ratio

    -- P&L
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    daily_pnl DECIMAL(20, 8) DEFAULT 0,

    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    snapshot_type VARCHAR(20) DEFAULT 'periodic',
    -- 'periodic', 'trade_open', 'trade_close', 'deposit', 'withdrawal', 'manual'

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'exchange',

    CONSTRAINT positive_total_balance CHECK (total_balance >= 0),
    CONSTRAINT valid_available_balance CHECK (available_balance >= 0)
);

-- Indexes
CREATE INDEX idx_balance_bot_id ON trading.account_balance(bot_id);
CREATE INDEX idx_balance_timestamp ON trading.account_balance(timestamp DESC);
CREATE INDEX idx_balance_bot_time ON trading.account_balance(bot_id, timestamp DESC);

COMMENT ON TABLE trading.account_balance IS 'Account balance history for all bots';
```

### 8. RISK METRICS TABLE

**Purpose**: Daily risk and performance metrics per bot

```sql
CREATE TABLE IF NOT EXISTS trading.risk_metrics (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,

    -- Bot Association
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Date
    date DATE NOT NULL,

    -- Daily Performance
    starting_equity DECIMAL(20, 8) NOT NULL,
    ending_equity DECIMAL(20, 8) NOT NULL,
    daily_pnl DECIMAL(20, 8) DEFAULT 0,
    daily_pnl_pct DECIMAL(10, 6) DEFAULT 0,
    daily_return DECIMAL(10, 6) DEFAULT 0,

    -- Trade Statistics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    breakeven_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0,

    -- P&L Statistics
    gross_profit DECIMAL(20, 8) DEFAULT 0,
    gross_loss DECIMAL(20, 8) DEFAULT 0,
    net_profit DECIMAL(20, 8) DEFAULT 0,
    profit_factor DECIMAL(10, 4) DEFAULT 0,
    avg_win DECIMAL(20, 8) DEFAULT 0,
    avg_loss DECIMAL(20, 8) DEFAULT 0,
    largest_win DECIMAL(20, 8) DEFAULT 0,
    largest_loss DECIMAL(20, 8) DEFAULT 0,

    -- Risk Metrics
    max_drawdown DECIMAL(10, 4) DEFAULT 0,
    max_drawdown_pct DECIMAL(10, 6) DEFAULT 0,
    current_drawdown DECIMAL(10, 4) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    calmar_ratio DECIMAL(10, 4),

    -- Exposure
    avg_leverage DECIMAL(10, 4),
    max_leverage DECIMAL(10, 4),
    avg_position_size DECIMAL(20, 8),
    max_exposure DECIMAL(20, 8),

    -- Holding Times
    avg_holding_time_hours DECIMAL(10, 2),
    shortest_trade_hours DECIMAL(10, 2),
    longest_trade_hours DECIMAL(10, 2),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_bot_date UNIQUE(bot_id, date)
);

-- Indexes
CREATE INDEX idx_risk_metrics_bot_id ON trading.risk_metrics(bot_id);
CREATE INDEX idx_risk_metrics_date ON trading.risk_metrics(date DESC);
CREATE INDEX idx_risk_metrics_bot_date ON trading.risk_metrics(bot_id, date DESC);

COMMENT ON TABLE trading.risk_metrics IS 'Daily risk and performance metrics for each bot';
```

---

## ANALYTICS SCHEMA TABLES

### 9. PORTFOLIO AGGREGATE VIEW

**Purpose**: Real-time portfolio view across all bots

```sql
CREATE TABLE IF NOT EXISTS analytics.portfolio_snapshots (
    id BIGSERIAL PRIMARY KEY,

    -- Snapshot Time
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Total Portfolio Metrics
    total_equity DECIMAL(20, 8) NOT NULL,
    total_balance DECIMAL(20, 8) NOT NULL,
    total_unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_realized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_margin_used DECIMAL(20, 8) DEFAULT 0,

    -- Portfolio-Level Risk
    portfolio_leverage DECIMAL(10, 4),
    portfolio_exposure DECIMAL(20, 8),
    portfolio_var_95 DECIMAL(20, 8), -- Value at Risk 95%

    -- Bot Count
    active_bots INTEGER DEFAULT 0,
    bots_in_trade INTEGER DEFAULT 0,
    total_open_positions INTEGER DEFAULT 0,

    -- Performance
    daily_pnl DECIMAL(20, 8) DEFAULT 0,
    weekly_pnl DECIMAL(20, 8) DEFAULT 0,
    monthly_pnl DECIMAL(20, 8) DEFAULT 0,

    -- Per-Bot Breakdown
    bot_metrics JSONB, -- {"bot_1": {...}, "bot_2": {...}}

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolio_timestamp ON analytics.portfolio_snapshots(timestamp DESC);
```

### 10. SYSTEM EVENTS TABLE

**Purpose**: Audit trail and system logging

```sql
CREATE TABLE IF NOT EXISTS audit.system_events (
    id BIGSERIAL PRIMARY KEY,

    -- Event Details
    event_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50) NOT NULL,
    -- 'SYSTEM_START', 'SYSTEM_STOP', 'BOT_START', 'BOT_STOP', 'CONFIG_CHANGE',
    -- 'RISK_BREACH', 'ERROR', 'WARNING', 'INFO', 'TRADE', 'ORDER'
    event_level VARCHAR(20) NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'

    -- Source
    bot_id VARCHAR(50),
    component VARCHAR(50), -- 'trading_engine', 'risk_manager', 'order_executor', etc.

    -- Message
    message TEXT NOT NULL,
    details JSONB,

    -- Context
    symbol VARCHAR(20),
    order_id VARCHAR(100),
    trade_id VARCHAR(100),

    -- Error Tracking
    error_code VARCHAR(50),
    stack_trace TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_event_level CHECK (event_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

-- Indexes
CREATE INDEX idx_events_time ON audit.system_events(event_time DESC);
CREATE INDEX idx_events_level ON audit.system_events(event_level);
CREATE INDEX idx_events_bot_id ON audit.system_events(bot_id);
CREATE INDEX idx_events_type ON audit.system_events(event_type);
CREATE INDEX idx_events_bot_time ON audit.system_events(bot_id, event_time DESC);

-- GIN index for details JSONB
CREATE INDEX idx_events_details ON audit.system_events USING GIN(details);
```

### 11. RISK EVENTS TABLE

**Purpose**: Track all risk limit breaches

```sql
CREATE TABLE IF NOT EXISTS audit.risk_events (
    id BIGSERIAL PRIMARY KEY,

    -- Event Details
    event_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Risk Type
    risk_type VARCHAR(50) NOT NULL,
    -- 'daily_loss_limit', 'weekly_loss_limit', 'max_drawdown', 'position_limit',
    -- 'leverage_limit', 'exposure_limit', 'concentration_limit'

    -- Values
    current_value DECIMAL(20, 8) NOT NULL,
    limit_value DECIMAL(20, 8) NOT NULL,
    threshold_pct DECIMAL(5, 2), -- How close to limit (e.g., 95%)

    -- Action Taken
    action_taken VARCHAR(100) NOT NULL,
    -- 'position_reduced', 'trading_halted', 'new_trades_blocked',
    -- 'leverage_reduced', 'alert_sent', 'manual_review_required'

    -- Impact
    positions_affected INTEGER DEFAULT 0,
    trades_cancelled INTEGER DEFAULT 0,

    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_risk_events_bot_id ON audit.risk_events(bot_id);
CREATE INDEX idx_risk_events_time ON audit.risk_events(event_time DESC);
CREATE INDEX idx_risk_events_type ON audit.risk_events(risk_type);
CREATE INDEX idx_risk_events_resolved ON audit.risk_events(resolved);
```

---

## CONFIGURATION TABLES

### 12. BOT CONFIGURATIONS TABLE

**Purpose**: Store strategy-specific configurations

```sql
CREATE TABLE IF NOT EXISTS config.bot_configurations (
    id BIGSERIAL PRIMARY KEY,

    -- Bot Association
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    -- Configuration
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    config_type VARCHAR(50), -- 'strategy_params', 'risk_params', 'execution_params'

    -- Versioning
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,

    -- Timing
    effective_from TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    effective_until TIMESTAMP WITH TIME ZONE,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'system',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(50),

    CONSTRAINT unique_bot_config UNIQUE(bot_id, config_key, version)
);

CREATE INDEX idx_config_bot_id ON config.bot_configurations(bot_id);
CREATE INDEX idx_config_active ON config.bot_configurations(bot_id, is_active);
```

---

## MATERIALIZED VIEWS FOR PERFORMANCE

### View 1: Active Positions Across All Bots

```sql
CREATE MATERIALIZED VIEW analytics.active_positions_summary AS
SELECT
    p.bot_id,
    b.bot_name,
    p.symbol,
    p.side,
    p.size,
    p.avg_entry_price,
    p.current_price,
    p.unrealized_pnl,
    p.unrealized_pnl_pct,
    p.leverage,
    (p.size * p.current_price) as position_value_usd,
    p.opened_at,
    EXTRACT(EPOCH FROM (NOW() - p.opened_at))/3600 as hours_held,
    p.strategy,
    p.stop_loss,
    p.take_profit
FROM trading.positions p
JOIN trading.bots b ON p.bot_id = b.bot_id
WHERE p.status = 'open'
ORDER BY p.opened_at DESC;

CREATE UNIQUE INDEX idx_active_pos_summary_id ON analytics.active_positions_summary(bot_id, symbol);
CREATE INDEX idx_active_pos_summary_bot ON analytics.active_positions_summary(bot_id);

-- Refresh strategy (run every minute via cron or trigger)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.active_positions_summary;
```

### View 2: Daily Performance Summary

```sql
CREATE MATERIALIZED VIEW analytics.daily_performance_summary AS
SELECT
    DATE(t.entry_time) as trade_date,
    t.bot_id,
    b.bot_name,
    b.strategy_name,
    COUNT(*) as total_trades,
    SUM(CASE WHEN t.pnl_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN t.pnl_usd < 0 THEN 1 ELSE 0 END) as losing_trades,
    SUM(t.pnl_usd) as total_pnl,
    AVG(t.pnl_usd) as avg_pnl,
    AVG(t.pnl_pct) as avg_pnl_pct,
    MAX(t.pnl_usd) as max_win,
    MIN(t.pnl_usd) as max_loss,
    SUM(t.fees) as total_fees,
    AVG(t.holding_time_seconds)/3600 as avg_holding_hours,
    CAST(SUM(CASE WHEN t.pnl_usd > 0 THEN 1 ELSE 0 END) AS FLOAT) /
        NULLIF(COUNT(*), 0) as win_rate
FROM trading.trades t
JOIN trading.bots b ON t.bot_id = b.bot_id
WHERE t.status = 'filled' AND t.exit_time IS NOT NULL
GROUP BY DATE(t.entry_time), t.bot_id, b.bot_name, b.strategy_name
ORDER BY trade_date DESC, t.bot_id;

CREATE UNIQUE INDEX idx_daily_perf_summary ON analytics.daily_performance_summary(trade_date, bot_id);
```

### View 3: System Health Dashboard

```sql
CREATE MATERIALIZED VIEW analytics.system_health_dashboard AS
SELECT
    NOW() as snapshot_time,

    -- Bot Status
    COUNT(*) FILTER (WHERE b.status = 'active') as active_bots,
    COUNT(*) FILTER (WHERE b.status = 'paused') as paused_bots,
    COUNT(*) FILTER (WHERE b.status = 'stopped') as stopped_bots,

    -- Positions
    (SELECT COUNT(*) FROM trading.positions WHERE status = 'open') as total_open_positions,

    -- Today's Performance
    (SELECT COALESCE(SUM(pnl_usd), 0)
     FROM trading.trades
     WHERE DATE(entry_time) = CURRENT_DATE AND status = 'filled') as today_pnl,

    (SELECT COUNT(*)
     FROM trading.trades
     WHERE DATE(entry_time) = CURRENT_DATE AND status = 'filled') as today_trades,

    -- Active Orders
    (SELECT COUNT(*) FROM trading.orders
     WHERE status IN ('pending', 'submitted', 'partially_filled')) as active_orders,

    -- Recent Errors
    (SELECT COUNT(*) FROM audit.system_events
     WHERE event_level IN ('ERROR', 'CRITICAL')
     AND event_time > NOW() - INTERVAL '1 hour') as errors_last_hour,

    -- Portfolio Equity
    (SELECT SUM(current_equity) FROM trading.bots WHERE status = 'active') as total_portfolio_equity,

    -- Recent Risk Events
    (SELECT COUNT(*) FROM audit.risk_events
     WHERE event_time > NOW() - INTERVAL '24 hours'
     AND resolved = FALSE) as unresolved_risk_events

FROM trading.bots b;

CREATE UNIQUE INDEX idx_system_health ON analytics.system_health_dashboard(snapshot_time);
```

---

## REDIS CACHE SCHEMA

### Key Patterns

```
# Current Prices (TTL: 60 seconds)
price:{symbol} → {"price": 45000.50, "timestamp": "2025-10-24T10:30:00Z"}

# Bot State (TTL: None - persistent with AOF)
bot:{bot_id}:state → {"status": "running", "last_heartbeat": "..."}
bot:{bot_id}:position:{symbol} → {"size": 0.5, "entry_price": 45000, ...}
bot:{bot_id}:metrics → {"daily_pnl": 150.50, "open_positions": 2, ...}

# Locks (TTL: 60 seconds)
lock:order:{symbol}:{bot_id} → "locked"
lock:position:{symbol}:{bot_id} → "locked"

# Rate Limiting
ratelimit:api:{bot_id} → counter (TTL: 60 seconds)

# Session Data
session:{bot_id}:last_signal → {signal_data}
session:{bot_id}:pending_orders → [order_id_1, order_id_2, ...]
```

---

## INFLUXDB SCHEMA

### Measurements

```
# Candle Data (Retention: 90 days)
Measurement: candles
Tags: symbol, interval, exchange
Fields: open, high, low, close, volume
Time: timestamp

# Tick Data (Retention: 7 days)
Measurement: ticks
Tags: symbol, exchange
Fields: price, quantity, side
Time: timestamp

# Indicators (Retention: 90 days)
Measurement: indicators
Tags: symbol, indicator_name, timeframe
Fields: value
Time: timestamp

# Portfolio Metrics (Retention: 1 year)
Measurement: portfolio_metrics
Tags: bot_id
Fields: equity, pnl, drawdown, positions_count
Time: timestamp

# System Metrics (Retention: 30 days)
Measurement: system_metrics
Tags: bot_id, metric_name
Fields: value
Time: timestamp
```

---

## MIGRATION STRATEGY

### Phase 1: Database Setup (Week 1)

1. **Create Unified PostgreSQL Database**
   - Execute unified schema SQL scripts
   - Set up proper users and permissions
   - Configure connection pooling (PgBouncer)

2. **Set Up Redis**
   - Deploy Redis with AOF persistence
   - Configure eviction policies
   - Set up replication (if needed)

3. **Set Up InfluxDB**
   - Create organization and buckets
   - Set retention policies
   - Create downsampling tasks

### Phase 2: Data Migration (Week 2)

1. **Migrate Shortseller Data**
   - Export from existing PostgreSQL
   - Transform to unified schema (add bot_id)
   - Import into new database
   - Validate data integrity

2. **Migrate Momentum Data**
   - Export from SQLite
   - Transform to unified schema
   - Import into PostgreSQL
   - Update application to use PostgreSQL

3. **Handle LXAlgo**
   - Start fresh (no historical data)
   - Implement database persistence
   - Add logging to all tables

### Phase 3: Application Updates (Week 3)

1. **Update Connection Strings**
   - Point all bots to unified database
   - Update environment variables
   - Test connections

2. **Add bot_id to All Queries**
   - Update INSERT statements
   - Update SELECT statements with bot_id filters
   - Ensure proper isolation

3. **Implement Shared Services**
   - Market data service (shared across bots)
   - Risk monitoring service
   - Performance analytics service

### Phase 4: Testing & Validation (Week 4)

1. **Integration Testing**
   - Test each bot independently
   - Test concurrent bot operations
   - Verify data isolation

2. **Performance Testing**
   - Load testing with multiple bots
   - Query optimization
   - Index tuning

3. **Failover Testing**
   - Database connection failures
   - Redis failures
   - Recovery procedures

---

## CONFLICT RESOLUTIONS

### Resolution 1: Column Name Standardization

| Old (Shortseller) | Old (Momentum) | New (Unified) |
|------------------|----------------|---------------|
| `timestamp` | `entry_time` | `entry_time` |
| `qty` | `quantity` | `quantity` |
| `pnl` | `pnl_usd` | `pnl_usd` |
| - | `pnl_pct` | `pnl_pct` (add to both) |
| `executed_at` | `exit_time` | `exit_time` |

### Resolution 2: Status Values Standardization

```sql
-- Unified status values
Trade Status: 'pending', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired'
Position Status: 'open', 'partially_closed', 'closed', 'liquidated'
Bot Status: 'active', 'paused', 'stopped', 'archived'
```

### Resolution 3: ID Generation Strategy

```python
# Unified ID generation
trade_id = f"{bot_id}_{symbol}_{timestamp}_{random_suffix}"
position_id = f"{bot_id}_{symbol}_{opened_at_unix}"
order_id = f"{bot_id}_{client_order_id}"
```

### Resolution 4: Timezone Handling

```sql
-- All timestamps stored as UTC
-- Application layer converts to local time for display
SET TIMEZONE='UTC';
```

---

## DATABASE SIZING & PERFORMANCE

### Estimated Storage (1 Year)

| Table | Rows/Day (3 Bots) | Row Size | Daily Storage | Yearly Storage |
|-------|-------------------|----------|---------------|----------------|
| trades | 30 | 500 bytes | 15 KB | 5.5 MB |
| positions | 30 | 400 bytes | 12 KB | 4.4 MB |
| orders | 60 | 350 bytes | 21 KB | 7.7 MB |
| market_data | 8,640 | 200 bytes | 1.7 MB | 630 MB |
| signals | 100 | 300 bytes | 30 KB | 11 MB |
| account_balance | 288 | 150 bytes | 43 KB | 16 MB |
| system_events | 500 | 250 bytes | 125 KB | 46 MB |
| **TOTAL** | | | **~2 MB/day** | **~720 MB/year** |

**With indexes and overhead: ~1.5 GB/year**

### Performance Targets

- Trade insertion: < 10ms
- Position query: < 5ms
- Daily performance calculation: < 100ms
- Market data query (1000 rows): < 20ms
- Real-time dashboard refresh: < 200ms

---

## BACKUP & DISASTER RECOVERY

### Backup Strategy

```bash
# PostgreSQL - Daily full backup, hourly incremental
pg_dump -Fc trading_db > backup_$(date +%Y%m%d).dump

# Redis - AOF persistence + daily snapshot
redis-cli BGSAVE

# InfluxDB - Daily backup
influx backup /backup/influxdb_$(date +%Y%m%d)
```

### Retention Policy

- Daily backups: 30 days
- Weekly backups: 12 weeks
- Monthly backups: 12 months
- Yearly backups: 5 years

---

## MONITORING & ALERTING

### Key Metrics to Monitor

1. **Database Health**
   - Connection pool usage
   - Query latency (p50, p95, p99)
   - Slow query count
   - Deadlock count
   - Database size growth

2. **Data Quality**
   - Missing candles (gaps in market_data)
   - Orphaned records (trades without positions)
   - Null values in critical fields
   - Duplicate records

3. **Business Metrics**
   - Trades per hour
   - Average trade latency (signal → execution)
   - Failed order rate
   - Position reconciliation errors

### Alert Thresholds

```yaml
alerts:
  - name: database_connection_pool_exhausted
    condition: active_connections > 90% of max_connections
    severity: critical

  - name: slow_queries
    condition: query_time > 1000ms
    severity: warning

  - name: data_gap_detected
    condition: missing_candles > 5
    severity: warning

  - name: trade_reconciliation_error
    condition: position_mismatch == true
    severity: critical
```

---

## NEXT STEPS

1. ✅ Review and approve this architecture
2. ⏳ Create SQL migration scripts
3. ⏳ Update docker-compose.yml with unified services
4. ⏳ Implement database connection pooling
5. ⏳ Create data migration scripts
6. ⏳ Update bot applications to use unified schema
7. ⏳ Set up monitoring and alerting
8. ⏳ Test in staging environment
9. ⏳ Deploy to production

---

## APPENDIX

### A. Connection String Examples

```python
# PostgreSQL
POSTGRES_URI = "postgresql://trading_user:secure_password@localhost:5432/trading_db"

# Redis
REDIS_URI = "redis://:password@localhost:6379/0"

# InfluxDB
INFLUX_URI = "http://localhost:8086"
INFLUX_TOKEN = "your-secret-token"
INFLUX_ORG = "trading_org"
INFLUX_BUCKET = "market_data"
```

### B. Required Database Extensions

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
```

### C. Index Maintenance

```sql
-- Rebuild indexes monthly
REINDEX DATABASE trading_db;

-- Analyze tables weekly
ANALYZE;

-- Vacuum full quarterly
VACUUM FULL;
```

---

**End of Database Architecture Catalogue**
