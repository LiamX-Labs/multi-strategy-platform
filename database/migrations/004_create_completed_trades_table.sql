-- Migration: Create completed_trades table for hourly Bybit sync
-- Description: Stores closed trades fetched from Bybit API with execution reasons
-- Author: System
-- Date: 2025-11-01

-- Create completed_trades table
CREATE TABLE IF NOT EXISTS trading.completed_trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),
    symbol VARCHAR(20) NOT NULL,

    -- Entry leg (Buy side)
    entry_order_id VARCHAR(100),
    entry_client_order_id VARCHAR(100),  -- Contains entry reason (format: bot_id:reason:timestamp)
    entry_side VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    entry_qty DECIMAL(20, 8) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_reason VARCHAR(50),  -- Parsed from entry_client_order_id
    entry_commission DECIMAL(20, 8) DEFAULT 0,

    -- Exit leg (Sell side)
    exit_order_id VARCHAR(100),
    exit_client_order_id VARCHAR(100),  -- Contains exit/close reason
    exit_side VARCHAR(10) NOT NULL,
    exit_price DECIMAL(20, 8) NOT NULL,
    exit_qty DECIMAL(20, 8) NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_reason VARCHAR(50),  -- Parsed from exit_client_order_id (KEY FIELD!)
    exit_commission DECIMAL(20, 8) DEFAULT 0,

    -- Performance metrics (calculated)
    gross_pnl DECIMAL(20, 8),
    net_pnl DECIMAL(20, 8),
    pnl_pct DECIMAL(10, 6),
    total_commission DECIMAL(20, 8),
    holding_duration_seconds INTEGER,

    -- Metadata
    source VARCHAR(20) DEFAULT 'bybit_api' CHECK (source IN ('bybit_api', 'websocket', 'manual')),
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT unique_trade UNIQUE(bot_id, symbol, entry_time, exit_time),
    CONSTRAINT valid_sides CHECK (
        (entry_side = 'Buy' AND exit_side = 'Sell') OR
        (entry_side = 'Sell' AND exit_side = 'Buy')
    ),
    CONSTRAINT valid_times CHECK (exit_time > entry_time),
    CONSTRAINT matching_quantities CHECK (entry_qty = exit_qty)
);

-- Create indexes for performance
CREATE INDEX idx_completed_trades_bot ON trading.completed_trades(bot_id, exit_time DESC);
CREATE INDEX idx_completed_trades_symbol ON trading.completed_trades(symbol, exit_time DESC);
CREATE INDEX idx_completed_trades_exit_reason ON trading.completed_trades(exit_reason) WHERE exit_reason IS NOT NULL;
CREATE INDEX idx_completed_trades_entry_reason ON trading.completed_trades(entry_reason) WHERE entry_reason IS NOT NULL;
CREATE INDEX idx_completed_trades_pnl ON trading.completed_trades(bot_id, net_pnl DESC);
CREATE INDEX idx_completed_trades_trade_id ON trading.completed_trades(trade_id);

-- Partial index for recent trades (90 days) - most frequently queried
CREATE INDEX idx_completed_trades_recent ON trading.completed_trades(bot_id, exit_time DESC)
    WHERE exit_time > NOW() - INTERVAL '90 days';

-- Index for sync monitoring
CREATE INDEX idx_completed_trades_sync ON trading.completed_trades(synced_at DESC);

-- Create a view for quick analytics
CREATE OR REPLACE VIEW trading.completed_trades_summary AS
SELECT
    bot_id,
    symbol,
    DATE_TRUNC('day', exit_time) as trade_date,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE net_pnl > 0) as winning_trades,
    COUNT(*) FILTER (WHERE net_pnl < 0) as losing_trades,
    COUNT(*) FILTER (WHERE net_pnl = 0) as breakeven_trades,
    SUM(net_pnl) as total_pnl,
    AVG(net_pnl) as avg_pnl,
    MAX(net_pnl) as max_win,
    MIN(net_pnl) as max_loss,
    SUM(total_commission) as total_fees,
    AVG(holding_duration_seconds) as avg_holding_seconds,
    AVG(pnl_pct) as avg_pnl_pct
FROM trading.completed_trades
GROUP BY bot_id, symbol, DATE_TRUNC('day', exit_time);

-- Create sync status tracking table
CREATE TABLE IF NOT EXISTS trading.sync_status (
    id SERIAL PRIMARY KEY,
    bot_id VARCHAR(50) NOT NULL REFERENCES trading.bots(bot_id),
    sync_type VARCHAR(20) NOT NULL CHECK (sync_type IN ('backfill', 'hourly', 'manual')),
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    trades_synced INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'partial')),
    error_message TEXT,
    sync_started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sync_completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    CONSTRAINT unique_sync_window UNIQUE(bot_id, sync_type, start_time, end_time)
);

CREATE INDEX idx_sync_status_bot ON trading.sync_status(bot_id, sync_started_at DESC);
CREATE INDEX idx_sync_status_type ON trading.sync_status(sync_type, status);

-- Add comments for documentation
COMMENT ON TABLE trading.completed_trades IS 'Stores completed trades synced from Bybit API every hour with execution reasons preserved';
COMMENT ON COLUMN trading.completed_trades.entry_client_order_id IS 'Format: bot_id:reason:timestamp - contains entry execution reason';
COMMENT ON COLUMN trading.completed_trades.exit_client_order_id IS 'Format: bot_id:reason:timestamp - contains exit/close reason (e.g., take_profit, stop_loss, trailing_stop)';
COMMENT ON COLUMN trading.completed_trades.source IS 'Data source: bybit_api (hourly sync), websocket (real-time), manual (admin)';
COMMENT ON TABLE trading.sync_status IS 'Tracks sync job execution for monitoring and debugging';

-- Grant permissions (adjust based on your user setup)
GRANT SELECT, INSERT, UPDATE ON trading.completed_trades TO trading_user;
GRANT SELECT, INSERT, UPDATE ON trading.sync_status TO trading_user;
GRANT USAGE, SELECT ON SEQUENCE trading.completed_trades_id_seq TO trading_user;
GRANT USAGE, SELECT ON SEQUENCE trading.sync_status_id_seq TO trading_user;
GRANT SELECT ON trading.completed_trades_summary TO trading_user;
