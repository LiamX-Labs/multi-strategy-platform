-- =====================================================
-- FILLS-BASED SCHEMA FOR ALPHA TRADING SYSTEM
-- Based on data.md specifications
-- =====================================================
-- Version: 1.0
-- Date: 2025-10-24
-- Description: Creates PostgreSQL + Redis architecture
--              PostgreSQL: Permanent fills history
--              Redis: Live position state
-- =====================================================

SET client_encoding = 'UTF8';
SET TIMEZONE='UTC';

-- =====================================================
-- CREATE SCHEMAS
-- =====================================================

CREATE SCHEMA IF NOT EXISTS trading;
COMMENT ON SCHEMA trading IS 'Core trading operations schema';

-- =====================================================
-- ENABLE EXTENSIONS
-- =====================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- =====================================================
-- TABLE 1: BOTS REGISTRY
-- =====================================================

CREATE TABLE IF NOT EXISTS trading.bots (
    bot_id VARCHAR(50) PRIMARY KEY,
    bot_name VARCHAR(100) NOT NULL,
    bot_type VARCHAR(50) NOT NULL, -- 'shortseller', 'lxalgo', 'momentum'
    strategy_name VARCHAR(100) NOT NULL,

    status VARCHAR(20) DEFAULT 'active',
    deployment_mode VARCHAR(20) NOT NULL, -- 'live', 'demo'

    initial_capital DECIMAL(20, 8) NOT NULL,
    current_equity DECIMAL(20, 8),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat TIMESTAMP WITH TIME ZONE,

    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'stopped')),
    CONSTRAINT valid_mode CHECK (deployment_mode IN ('live', 'demo'))
);

CREATE INDEX idx_bots_status ON trading.bots(status);
CREATE INDEX idx_bots_type ON trading.bots(bot_type);

COMMENT ON TABLE trading.bots IS 'Registry of all trading bots';

-- =====================================================
-- TABLE 2: FILLS (THE MOST IMPORTANT TABLE)
-- =====================================================
-- This is the "book of record" for performance
-- Every execution from Bybit WebSocket goes here
-- From data.md: "This is the only place you get the exact
--                execPrice, execQty, and commission"

CREATE TABLE IF NOT EXISTS trading.fills (
    id BIGSERIAL PRIMARY KEY,

    -- Bot identification
    bot_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- Order identification
    order_id VARCHAR(100) NOT NULL,           -- Bybit's order ID
    client_order_id VARCHAR(100) NOT NULL,    -- Our custom ID (bot_id:reason:timestamp)

    -- Execution details (from execution stream)
    side VARCHAR(10) NOT NULL,                -- 'Buy' or 'Sell'
    exec_price DECIMAL(20, 8) NOT NULL,       -- Fill price
    exec_qty DECIMAL(20, 8) NOT NULL,         -- Fill quantity
    exec_time TIMESTAMP WITH TIME ZONE NOT NULL,  -- Execution time

    -- Performance tracking
    close_reason VARCHAR(50),                 -- Parsed from client_order_id
                                             -- 'entry', 'trailing_stop', 'take_profit', etc.
    commission DECIMAL(20, 8) NOT NULL,      -- Fee paid

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_side CHECK (side IN ('Buy', 'Sell')),
    CONSTRAINT positive_qty CHECK (exec_qty > 0),
    CONSTRAINT positive_price CHECK (exec_price > 0)
);

-- Critical indexes for performance
CREATE INDEX idx_fills_bot_symbol ON trading.fills(bot_id, symbol, exec_time DESC);
CREATE INDEX idx_fills_close_reason ON trading.fills(close_reason);
CREATE INDEX idx_fills_order_id ON trading.fills(order_id);
CREATE INDEX idx_fills_client_id ON trading.fills(client_order_id);
CREATE INDEX idx_fills_exec_time ON trading.fills(exec_time DESC);

-- Partial index for recent fills (most common query)
CREATE INDEX idx_fills_recent ON trading.fills(bot_id, exec_time DESC)
    WHERE exec_time > NOW() - INTERVAL '30 days';

COMMENT ON TABLE trading.fills IS 'All executed fills from Bybit - THE book of record for performance';
COMMENT ON COLUMN trading.fills.close_reason IS 'Parsed from client_order_id - why the trade was executed';

-- =====================================================
-- TABLE 3: POSITIONS (EXCHANGE RECONCILIATION)
-- =====================================================
-- Updated from position WebSocket stream
-- This is the "source of truth" from the exchange

CREATE TABLE IF NOT EXISTS trading.positions (
    id SERIAL PRIMARY KEY,

    bot_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- From position stream
    size DECIMAL(20, 8) NOT NULL,            -- Current size
    side VARCHAR(10),                         -- 'Buy', 'Sell', or 'None'
    avg_entry_price DECIMAL(20, 8),          -- Exchange-calculated average

    -- Timestamps
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_bot_symbol UNIQUE(bot_id, symbol)
);

CREATE INDEX idx_positions_bot_id ON trading.positions(bot_id);
CREATE INDEX idx_positions_symbol ON trading.positions(symbol);

COMMENT ON TABLE trading.positions IS 'Current positions from exchange - reconciliation truth';

-- =====================================================
-- TABLE 4: ORDERS (LIFECYCLE TRACKING)
-- =====================================================
-- Updated from order WebSocket stream

CREATE TABLE IF NOT EXISTS trading.orders (
    id BIGSERIAL PRIMARY KEY,

    bot_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- Order identification
    order_id VARCHAR(100) UNIQUE NOT NULL,
    client_order_id VARCHAR(100) NOT NULL,

    -- Order details
    order_type VARCHAR(20) NOT NULL,         -- 'Market', 'Limit', etc.
    side VARCHAR(10) NOT NULL,               -- 'Buy' or 'Sell'
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8),

    -- Status (from order stream)
    status VARCHAR(20) NOT NULL,             -- 'New', 'PartiallyFilled', 'Filled', 'Cancelled', 'Rejected'

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_order_side CHECK (side IN ('Buy', 'Sell')),
    CONSTRAINT positive_qty CHECK (quantity > 0)
);

CREATE INDEX idx_orders_bot_id ON trading.orders(bot_id);
CREATE INDEX idx_orders_status ON trading.orders(status);
CREATE INDEX idx_orders_client_id ON trading.orders(client_order_id);
CREATE INDEX idx_orders_created ON trading.orders(created_at DESC);

-- Partial index for active orders
CREATE INDEX idx_orders_active ON trading.orders(bot_id, symbol)
    WHERE status IN ('New', 'PartiallyFilled');

COMMENT ON TABLE trading.orders IS 'Order lifecycle tracking from order stream';

-- =====================================================
-- VIEWS FOR ANALYSIS
-- =====================================================

-- View 1: Calculate PnL by pairing Buy/Sell fills
CREATE OR REPLACE VIEW trading.trades_pnl AS
WITH fills_numbered AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY bot_id, symbol ORDER BY exec_time) as fill_num
    FROM trading.fills
),
buy_fills AS (
    SELECT * FROM fills_numbered WHERE side = 'Buy'
),
sell_fills AS (
    SELECT * FROM fills_numbered WHERE side = 'Sell'
)
SELECT
    b.bot_id,
    b.symbol,
    b.exec_time as entry_time,
    s.exec_time as exit_time,
    b.exec_price as entry_price,
    s.exec_price as exit_price,
    b.exec_qty as quantity,
    (s.exec_price - b.exec_price) * b.exec_qty as gross_pnl,
    (b.commission + s.commission) as total_fees,
    ((s.exec_price - b.exec_price) * b.exec_qty) - (b.commission + s.commission) as net_pnl,
    s.close_reason,
    EXTRACT(EPOCH FROM (s.exec_time - b.exec_time)) as holding_seconds
FROM buy_fills b
JOIN sell_fills s ON
    b.bot_id = s.bot_id AND
    b.symbol = s.symbol AND
    s.fill_num = b.fill_num + 1;

COMMENT ON VIEW trading.trades_pnl IS 'Calculated PnL by pairing buy and sell fills';

-- View 2: Daily performance by bot
CREATE OR REPLACE VIEW trading.daily_performance AS
SELECT
    DATE(exec_time) as trade_date,
    bot_id,
    COUNT(*) as total_fills,
    SUM(CASE WHEN side = 'Buy' THEN 1 ELSE 0 END) as buy_fills,
    SUM(CASE WHEN side = 'Sell' THEN 1 ELSE 0 END) as sell_fills,
    SUM(commission) as total_fees,
    COUNT(DISTINCT symbol) as symbols_traded
FROM trading.fills
GROUP BY DATE(exec_time), bot_id
ORDER BY trade_date DESC;

COMMENT ON VIEW trading.daily_performance IS 'Daily fill activity by bot';

-- =====================================================
-- FUNCTIONS & TRIGGERS
-- =====================================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for bots table
CREATE TRIGGER update_bots_updated_at BEFORE UPDATE ON trading.bots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for orders table
CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON trading.orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- GRANT PERMISSIONS
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
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA trading TO trading_user;

-- =====================================================
-- INITIALIZATION COMPLETE
-- =====================================================

-- Log successful migration
DO
$$
BEGIN
    RAISE NOTICE 'Schema created successfully';
    RAISE NOTICE 'Tables: bots, fills, positions, orders';
    RAISE NOTICE 'Views: trades_pnl, daily_performance';
    RAISE NOTICE 'Ready for WebSocket listener connection';
END
$$;
