-- =====================================================
-- UNIFIED TRADING SYSTEM DATABASE SCHEMA
-- Migration Script 001: Initial Schema Creation
-- =====================================================
-- Version: 1.0
-- Date: 2025-10-24
-- Description: Creates the unified database schema for all trading bots
-- Prerequisites: PostgreSQL 14+
-- =====================================================

-- Set client encoding and timezone
SET client_encoding = 'UTF8';
SET TIMEZONE='UTC';

-- =====================================================
-- PART 1: CREATE SCHEMAS
-- =====================================================

CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS audit;

-- Set default search path
SET search_path TO trading, public;

COMMENT ON SCHEMA trading IS 'Core trading operations schema';
COMMENT ON SCHEMA analytics IS 'Analytics and reporting schema';
COMMENT ON SCHEMA config IS 'Configuration management schema';
COMMENT ON SCHEMA audit IS 'Audit trail and logging schema';

-- =====================================================
-- PART 2: ENABLE EXTENSIONS
-- =====================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- =====================================================
-- PART 3: CREATE CORE TABLES
-- =====================================================

-- Table 1: Bots Registry
CREATE TABLE IF NOT EXISTS trading.bots (
    bot_id VARCHAR(50) PRIMARY KEY,
    bot_name VARCHAR(100) NOT NULL,
    bot_type VARCHAR(50) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    deployment_mode VARCHAR(20) NOT NULL,

    initial_capital DECIMAL(20, 8) NOT NULL,
    current_equity DECIMAL(20, 8),
    max_positions INTEGER DEFAULT 3,
    leverage_limit INTEGER DEFAULT 1,

    max_daily_loss_pct DECIMAL(5, 4),
    max_weekly_loss_pct DECIMAL(5, 4),
    max_drawdown_pct DECIMAL(5, 4),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'system',
    last_heartbeat TIMESTAMP WITH TIME ZONE,

    api_key_hash VARCHAR(255),
    exchange VARCHAR(50) DEFAULT 'bybit',

    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'stopped', 'archived')),
    CONSTRAINT valid_mode CHECK (deployment_mode IN ('live', 'demo', 'backtest'))
);

CREATE INDEX idx_bots_status ON trading.bots(status);
CREATE INDEX idx_bots_type ON trading.bots(bot_type);
CREATE INDEX idx_bots_mode ON trading.bots(deployment_mode);

-- Table 2: Trades (Unified)
CREATE TABLE IF NOT EXISTS trading.trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    symbol VARCHAR(20) NOT NULL,
    exchange_order_id VARCHAR(100),

    side VARCHAR(10) NOT NULL,
    trade_type VARCHAR(20) DEFAULT 'market',

    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    avg_fill_price DECIMAL(20, 8),

    position_size_usd DECIMAL(20, 8) NOT NULL,
    leverage INTEGER DEFAULT 1,

    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    trailing_stop_pct DECIMAL(5, 4),

    status VARCHAR(20) DEFAULT 'pending',

    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    holding_time_seconds INTEGER,

    pnl_usd DECIMAL(20, 8) DEFAULT 0,
    pnl_pct DECIMAL(10, 6) DEFAULT 0,
    fees DECIMAL(20, 8) DEFAULT 0,
    commission DECIMAL(20, 8) DEFAULT 0,
    slippage DECIMAL(20, 8) DEFAULT 0,

    exit_reason VARCHAR(50),

    strategy VARCHAR(50) NOT NULL,
    signal_strength DECIMAL(5, 4),
    confidence_score DECIMAL(5, 4),
    strategy_params JSONB,

    market_regime VARCHAR(30),
    entry_conditions JSONB,
    exit_conditions JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT valid_side CHECK (side IN ('buy', 'sell', 'long', 'short')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired')),
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT positive_price CHECK (entry_price > 0)
);

CREATE INDEX idx_trades_bot_id ON trading.trades(bot_id);
CREATE INDEX idx_trades_symbol ON trading.trades(symbol);
CREATE INDEX idx_trades_entry_time ON trading.trades(entry_time);
CREATE INDEX idx_trades_status ON trading.trades(status);
CREATE INDEX idx_trades_bot_symbol ON trading.trades(bot_id, symbol);
CREATE INDEX idx_trades_bot_time ON trading.trades(bot_id, entry_time DESC);
CREATE INDEX idx_trades_exit_time ON trading.trades(exit_time) WHERE exit_time IS NOT NULL;
CREATE INDEX idx_trades_open ON trading.trades(bot_id, symbol) WHERE exit_time IS NULL;
CREATE INDEX idx_trades_strategy_params ON trading.trades USING GIN(strategy_params);
CREATE INDEX idx_trades_entry_conditions ON trading.trades USING GIN(entry_conditions);

-- Table 3: Positions (Unified)
CREATE TABLE IF NOT EXISTS trading.positions (
    id BIGSERIAL PRIMARY KEY,
    position_id VARCHAR(100) UNIQUE NOT NULL,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,

    size DECIMAL(20, 8) NOT NULL,
    avg_entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    leverage INTEGER DEFAULT 1,

    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_pnl DECIMAL(20, 8) DEFAULT 0,
    unrealized_pnl_pct DECIMAL(10, 6) DEFAULT 0,

    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    trailing_stop_pct DECIMAL(5, 4),
    highest_price DECIMAL(20, 8),
    lowest_price DECIMAL(20, 8),

    status VARCHAR(20) DEFAULT 'open',

    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    entry_trade_ids TEXT[],
    exit_trade_ids TEXT[],

    strategy VARCHAR(50) NOT NULL,
    entry_signal JSONB,
    position_metadata JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT valid_side CHECK (side IN ('long', 'short')),
    CONSTRAINT valid_status CHECK (status IN ('open', 'partially_closed', 'closed', 'liquidated')),
    CONSTRAINT positive_size CHECK (size > 0)
);

CREATE INDEX idx_positions_bot_id ON trading.positions(bot_id);
CREATE INDEX idx_positions_symbol ON trading.positions(symbol);
CREATE INDEX idx_positions_status ON trading.positions(status);
CREATE INDEX idx_positions_bot_symbol ON trading.positions(bot_id, symbol);
CREATE INDEX idx_positions_opened_at ON trading.positions(opened_at);
CREATE INDEX idx_positions_open ON trading.positions(bot_id, symbol, status) WHERE status = 'open';
CREATE INDEX idx_positions_entry_trades ON trading.positions USING GIN(entry_trade_ids);

-- Table 4: Orders
CREATE TABLE IF NOT EXISTS trading.orders (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    symbol VARCHAR(20) NOT NULL,
    exchange_order_id VARCHAR(100),
    client_order_id VARCHAR(100),

    order_type VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,

    quantity DECIMAL(20, 8) NOT NULL,
    filled_quantity DECIMAL(20, 8) DEFAULT 0,
    remaining_quantity DECIMAL(20, 8),
    price DECIMAL(20, 8),
    avg_fill_price DECIMAL(20, 8),
    stop_price DECIMAL(20, 8),

    status VARCHAR(20) DEFAULT 'pending',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE,
    filled_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    fees DECIMAL(20, 8) DEFAULT 0,
    commission DECIMAL(20, 8) DEFAULT 0,

    order_purpose VARCHAR(30),
    position_id VARCHAR(100),
    trade_id VARCHAR(100),

    rejection_reason TEXT,
    error_code VARCHAR(50),
    retry_count INTEGER DEFAULT 0,

    order_metadata JSONB,

    CONSTRAINT valid_order_type CHECK (order_type IN ('market', 'limit', 'stop_market', 'stop_limit', 'trailing_stop')),
    CONSTRAINT valid_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'submitted', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired', 'failed')),
    CONSTRAINT positive_quantity CHECK (quantity > 0)
);

CREATE INDEX idx_orders_bot_id ON trading.orders(bot_id);
CREATE INDEX idx_orders_symbol ON trading.orders(symbol);
CREATE INDEX idx_orders_status ON trading.orders(status);
CREATE INDEX idx_orders_exchange_id ON trading.orders(exchange_order_id);
CREATE INDEX idx_orders_created_at ON trading.orders(created_at DESC);
CREATE INDEX idx_orders_position_id ON trading.orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_orders_active ON trading.orders(bot_id, symbol) WHERE status IN ('pending', 'submitted', 'partially_filled');

-- Table 5: Market Data
CREATE TABLE IF NOT EXISTS trading.market_data (
    id BIGSERIAL PRIMARY KEY,

    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(50) DEFAULT 'bybit',
    interval VARCHAR(10) NOT NULL,

    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    quote_volume DECIMAL(20, 8),

    trades_count INTEGER,
    taker_buy_volume DECIMAL(20, 8),
    taker_sell_volume DECIMAL(20, 8),

    ema_20 DECIMAL(20, 8),
    ema_50 DECIMAL(20, 8),
    ema_200 DECIMAL(20, 8),
    rsi_14 DECIMAL(10, 6),
    atr_14 DECIMAL(20, 8),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'exchange',

    CONSTRAINT unique_candle UNIQUE(symbol, interval, timestamp),
    CONSTRAINT valid_ohlc CHECK (
        high_price >= low_price AND
        high_price >= open_price AND
        high_price >= close_price AND
        low_price <= open_price AND
        low_price <= close_price
    )
);

CREATE INDEX idx_market_data_symbol_interval ON trading.market_data(symbol, interval, timestamp DESC);
CREATE INDEX idx_market_data_timestamp ON trading.market_data(timestamp DESC);
CREATE INDEX idx_market_data_symbol ON trading.market_data(symbol);
CREATE INDEX idx_market_data_1h ON trading.market_data(symbol, timestamp DESC) WHERE interval = '1h';
CREATE INDEX idx_market_data_4h ON trading.market_data(symbol, timestamp DESC) WHERE interval = '4h';
CREATE INDEX idx_market_data_1d ON trading.market_data(symbol, timestamp DESC) WHERE interval = '1d';

-- Table 6: Signals
CREATE TABLE IF NOT EXISTS trading.signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(100) UNIQUE NOT NULL,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    symbol VARCHAR(20) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    strength DECIMAL(5, 4) DEFAULT 1.0,
    confidence DECIMAL(5, 4),

    price DECIMAL(20, 8) NOT NULL,
    suggested_stop_loss DECIMAL(20, 8),
    suggested_take_profit DECIMAL(20, 8),
    suggested_position_size DECIMAL(20, 8),

    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP WITH TIME ZONE,

    strategy VARCHAR(50) NOT NULL,
    indicators JSONB,
    market_conditions JSONB,

    executed BOOLEAN DEFAULT FALSE,
    execution_time TIMESTAMP WITH TIME ZONE,
    execution_order_id VARCHAR(100),
    execution_trade_id VARCHAR(100),

    rejected BOOLEAN DEFAULT FALSE,
    rejection_reason VARCHAR(100),
    passed_filters JSONB,

    outcome VARCHAR(20),
    outcome_pnl DECIMAL(20, 8),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT valid_signal_type CHECK (signal_type IN ('long', 'short', 'close_long', 'close_short', 'hold')),
    CONSTRAINT valid_strength CHECK (strength >= 0 AND strength <= 1),
    CONSTRAINT valid_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE INDEX idx_signals_bot_id ON trading.signals(bot_id);
CREATE INDEX idx_signals_symbol ON trading.signals(symbol);
CREATE INDEX idx_signals_timestamp ON trading.signals(timestamp DESC);
CREATE INDEX idx_signals_executed ON trading.signals(executed);
CREATE INDEX idx_signals_bot_symbol ON trading.signals(bot_id, symbol, timestamp DESC);
CREATE INDEX idx_signals_indicators ON trading.signals USING GIN(indicators);

-- Table 7: Account Balance
CREATE TABLE IF NOT EXISTS trading.account_balance (
    id BIGSERIAL PRIMARY KEY,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    total_balance DECIMAL(20, 8) NOT NULL,
    available_balance DECIMAL(20, 8) NOT NULL,
    locked_balance DECIMAL(20, 8) DEFAULT 0,
    equity DECIMAL(20, 8) NOT NULL,

    margin_used DECIMAL(20, 8) DEFAULT 0,
    margin_available DECIMAL(20, 8),
    margin_level DECIMAL(10, 6),

    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    daily_pnl DECIMAL(20, 8) DEFAULT 0,

    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    snapshot_type VARCHAR(20) DEFAULT 'periodic',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'exchange',

    CONSTRAINT positive_total_balance CHECK (total_balance >= 0),
    CONSTRAINT valid_available_balance CHECK (available_balance >= 0)
);

CREATE INDEX idx_balance_bot_id ON trading.account_balance(bot_id);
CREATE INDEX idx_balance_timestamp ON trading.account_balance(timestamp DESC);
CREATE INDEX idx_balance_bot_time ON trading.account_balance(bot_id, timestamp DESC);

-- Table 8: Risk Metrics
CREATE TABLE IF NOT EXISTS trading.risk_metrics (
    id BIGSERIAL PRIMARY KEY,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),
    date DATE NOT NULL,

    starting_equity DECIMAL(20, 8) NOT NULL,
    ending_equity DECIMAL(20, 8) NOT NULL,
    daily_pnl DECIMAL(20, 8) DEFAULT 0,
    daily_pnl_pct DECIMAL(10, 6) DEFAULT 0,
    daily_return DECIMAL(10, 6) DEFAULT 0,

    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    breakeven_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0,

    gross_profit DECIMAL(20, 8) DEFAULT 0,
    gross_loss DECIMAL(20, 8) DEFAULT 0,
    net_profit DECIMAL(20, 8) DEFAULT 0,
    profit_factor DECIMAL(10, 4) DEFAULT 0,
    avg_win DECIMAL(20, 8) DEFAULT 0,
    avg_loss DECIMAL(20, 8) DEFAULT 0,
    largest_win DECIMAL(20, 8) DEFAULT 0,
    largest_loss DECIMAL(20, 8) DEFAULT 0,

    max_drawdown DECIMAL(10, 4) DEFAULT 0,
    max_drawdown_pct DECIMAL(10, 6) DEFAULT 0,
    current_drawdown DECIMAL(10, 4) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    calmar_ratio DECIMAL(10, 4),

    avg_leverage DECIMAL(10, 4),
    max_leverage DECIMAL(10, 4),
    avg_position_size DECIMAL(20, 8),
    max_exposure DECIMAL(20, 8),

    avg_holding_time_hours DECIMAL(10, 2),
    shortest_trade_hours DECIMAL(10, 2),
    longest_trade_hours DECIMAL(10, 2),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_bot_date UNIQUE(bot_id, date)
);

CREATE INDEX idx_risk_metrics_bot_id ON trading.risk_metrics(bot_id);
CREATE INDEX idx_risk_metrics_date ON trading.risk_metrics(date DESC);
CREATE INDEX idx_risk_metrics_bot_date ON trading.risk_metrics(bot_id, date DESC);

-- =====================================================
-- PART 4: CREATE ANALYTICS TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS analytics.portfolio_snapshots (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    total_equity DECIMAL(20, 8) NOT NULL,
    total_balance DECIMAL(20, 8) NOT NULL,
    total_unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_realized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_margin_used DECIMAL(20, 8) DEFAULT 0,

    portfolio_leverage DECIMAL(10, 4),
    portfolio_exposure DECIMAL(20, 8),
    portfolio_var_95 DECIMAL(20, 8),

    active_bots INTEGER DEFAULT 0,
    bots_in_trade INTEGER DEFAULT 0,
    total_open_positions INTEGER DEFAULT 0,

    daily_pnl DECIMAL(20, 8) DEFAULT 0,
    weekly_pnl DECIMAL(20, 8) DEFAULT 0,
    monthly_pnl DECIMAL(20, 8) DEFAULT 0,

    bot_metrics JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolio_timestamp ON analytics.portfolio_snapshots(timestamp DESC);

-- =====================================================
-- PART 5: CREATE AUDIT TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS audit.system_events (
    id BIGSERIAL PRIMARY KEY,

    event_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50) NOT NULL,
    event_level VARCHAR(20) NOT NULL,

    bot_id VARCHAR(50),
    component VARCHAR(50),

    message TEXT NOT NULL,
    details JSONB,

    symbol VARCHAR(20),
    order_id VARCHAR(100),
    trade_id VARCHAR(100),

    error_code VARCHAR(50),
    stack_trace TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_event_level CHECK (event_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

CREATE INDEX idx_events_time ON audit.system_events(event_time DESC);
CREATE INDEX idx_events_level ON audit.system_events(event_level);
CREATE INDEX idx_events_bot_id ON audit.system_events(bot_id);
CREATE INDEX idx_events_type ON audit.system_events(event_type);
CREATE INDEX idx_events_bot_time ON audit.system_events(bot_id, event_time DESC);
CREATE INDEX idx_events_details ON audit.system_events USING GIN(details);

CREATE TABLE IF NOT EXISTS audit.risk_events (
    id BIGSERIAL PRIMARY KEY,

    event_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    risk_type VARCHAR(50) NOT NULL,
    current_value DECIMAL(20, 8) NOT NULL,
    limit_value DECIMAL(20, 8) NOT NULL,
    threshold_pct DECIMAL(5, 2),

    action_taken VARCHAR(100) NOT NULL,
    positions_affected INTEGER DEFAULT 0,
    trades_cancelled INTEGER DEFAULT 0,

    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_risk_events_bot_id ON audit.risk_events(bot_id);
CREATE INDEX idx_risk_events_time ON audit.risk_events(event_time DESC);
CREATE INDEX idx_risk_events_type ON audit.risk_events(risk_type);
CREATE INDEX idx_risk_events_resolved ON audit.risk_events(resolved);

-- =====================================================
-- PART 6: CREATE CONFIG TABLES
-- =====================================================

CREATE TABLE IF NOT EXISTS config.bot_configurations (
    id BIGSERIAL PRIMARY KEY,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),

    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    config_type VARCHAR(50),

    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,

    effective_from TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    effective_until TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'system',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(50),

    CONSTRAINT unique_bot_config UNIQUE(bot_id, config_key, version)
);

CREATE INDEX idx_config_bot_id ON config.bot_configurations(bot_id);
CREATE INDEX idx_config_active ON config.bot_configurations(bot_id, is_active);

-- =====================================================
-- PART 7: CREATE VIEWS
-- =====================================================

-- View: Active Positions Summary
CREATE OR REPLACE VIEW analytics.active_positions_view AS
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

-- View: Daily Performance Summary
CREATE OR REPLACE VIEW analytics.daily_performance_view AS
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
    CAST(SUM(CASE WHEN t.pnl_usd > 0 THEN 1 ELSE 0 END) AS FLOAT) / NULLIF(COUNT(*), 0) as win_rate
FROM trading.trades t
JOIN trading.bots b ON t.bot_id = b.bot_id
WHERE t.status = 'filled' AND t.exit_time IS NOT NULL
GROUP BY DATE(t.entry_time), t.bot_id, b.bot_name, b.strategy_name
ORDER BY trade_date DESC, t.bot_id;

-- =====================================================
-- PART 8: CREATE FUNCTIONS & TRIGGERS
-- =====================================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_bots_updated_at BEFORE UPDATE ON trading.bots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trading.trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON trading.positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON trading.orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- PART 9: GRANT PERMISSIONS
-- =====================================================

-- Create trading user if not exists
DO
$do$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'trading_user') THEN
      CREATE USER trading_user WITH PASSWORD 'secure_password';
   END IF;
END
$do$;

-- Grant schema permissions
GRANT ALL PRIVILEGES ON SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON SCHEMA analytics TO trading_user;
GRANT ALL PRIVILEGES ON SCHEMA config TO trading_user;
GRANT ALL PRIVILEGES ON SCHEMA audit TO trading_user;

-- Grant table permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO trading_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA config TO trading_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA audit TO trading_user;

-- Grant sequence permissions
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA analytics TO trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA config TO trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA audit TO trading_user;

-- =====================================================
-- PART 10: ADD COMMENTS
-- =====================================================

COMMENT ON TABLE trading.bots IS 'Central registry of all trading bots';
COMMENT ON TABLE trading.trades IS 'All executed trades across all bots with unified schema';
COMMENT ON TABLE trading.positions IS 'Current and historical positions for all bots';
COMMENT ON TABLE trading.orders IS 'All order submissions across all bots';
COMMENT ON TABLE trading.market_data IS 'Shared market data (OHLCV) for all symbols and timeframes';
COMMENT ON TABLE trading.signals IS 'All generated trading signals before execution';
COMMENT ON TABLE trading.account_balance IS 'Account balance history for all bots';
COMMENT ON TABLE trading.risk_metrics IS 'Daily risk and performance metrics for each bot';
COMMENT ON TABLE analytics.portfolio_snapshots IS 'Portfolio-wide snapshots across all bots';
COMMENT ON TABLE audit.system_events IS 'System-wide event logging and audit trail';
COMMENT ON TABLE audit.risk_events IS 'Risk limit breaches and actions taken';
COMMENT ON TABLE config.bot_configurations IS 'Bot-specific configuration versioning';

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================

-- Log migration completion
INSERT INTO audit.system_events (event_type, event_level, message, details)
VALUES (
    'MIGRATION',
    'INFO',
    'Migration 001_unified_schema.sql completed successfully',
    jsonb_build_object(
        'migration_version', '001',
        'migration_date', CURRENT_TIMESTAMP,
        'tables_created', 12
    )
);

COMMIT;
