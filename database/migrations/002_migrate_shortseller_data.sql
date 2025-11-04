-- =====================================================
-- MIGRATION 002: Migrate Shortseller Data
-- =====================================================
-- Description: Migrates existing Shortseller data to unified schema
-- Prerequisites: Migration 001 completed
-- Source: trading.* tables (old schema)
-- Destination: trading.* tables (unified schema with bot_id)
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: Register Shortseller Bot
-- =====================================================

INSERT INTO trading.bots (
    bot_id,
    bot_name,
    bot_type,
    strategy_name,
    description,
    status,
    deployment_mode,
    initial_capital,
    current_equity,
    max_positions,
    leverage_limit,
    max_daily_loss_pct,
    max_weekly_loss_pct,
    max_drawdown_pct,
    exchange,
    created_at
)
VALUES (
    'shortseller_001',
    'Multi-Asset EMA Crossover Bot',
    'shortseller',
    'EMA 240/600 Crossover',
    'Multi-asset short trading strategy using EMA crossovers on BTC, ETH, SOL',
    'active',
    'demo', -- Change to 'live' if running on live
    10000.00, -- Initial capital
    (SELECT equity FROM account_balance ORDER BY timestamp DESC LIMIT 1), -- Current equity from latest balance
    3, -- Max 3 positions (BTC, ETH, SOL)
    10, -- Leverage per asset
    0.05, -- 5% max daily loss
    0.10, -- 10% max weekly loss
    0.20, -- 20% max drawdown
    'bybit',
    CURRENT_TIMESTAMP
)
ON CONFLICT (bot_id) DO NOTHING;

-- =====================================================
-- STEP 2: Migrate Trades Data
-- =====================================================

INSERT INTO trading.trades (
    trade_id,
    bot_id,
    symbol,
    exchange_order_id,
    side,
    trade_type,
    quantity,
    entry_price,
    exit_price,
    avg_fill_price,
    position_size_usd,
    leverage,
    stop_loss,
    take_profit,
    status,
    entry_time,
    exit_time,
    holding_time_seconds,
    pnl_usd,
    pnl_pct,
    fees,
    exit_reason,
    strategy,
    strategy_params,
    created_at,
    updated_at,
    notes
)
SELECT
    CONCAT('shortseller_001_', order_id) as trade_id,
    'shortseller_001' as bot_id,
    symbol,
    exchange_order_id,
    side,
    'market' as trade_type, -- Default to market orders
    quantity,
    price as entry_price,
    NULL as exit_price, -- Will be updated on position close
    price as avg_fill_price,
    (quantity * price) as position_size_usd,
    1 as leverage, -- Default leverage
    NULL as stop_loss, -- Will get from positions table
    NULL as take_profit,
    status,
    timestamp as entry_time,
    executed_at as exit_time,
    CASE
        WHEN executed_at IS NOT NULL THEN EXTRACT(EPOCH FROM (executed_at - timestamp))::INTEGER
        ELSE NULL
    END as holding_time_seconds,
    pnl as pnl_usd,
    CASE
        WHEN price > 0 THEN (pnl / (quantity * price))
        ELSE 0
    END as pnl_pct,
    fees,
    NULL as exit_reason,
    strategy,
    NULL as strategy_params,
    timestamp as created_at,
    COALESCE(executed_at, timestamp) as updated_at,
    notes
FROM trading.trades -- Old trades table
ON CONFLICT (trade_id) DO NOTHING;

-- =====================================================
-- STEP 3: Migrate Positions Data
-- =====================================================

INSERT INTO trading.positions (
    position_id,
    bot_id,
    symbol,
    side,
    size,
    avg_entry_price,
    current_price,
    leverage,
    unrealized_pnl,
    realized_pnl,
    total_pnl,
    unrealized_pnl_pct,
    stop_loss,
    take_profit,
    status,
    opened_at,
    closed_at,
    last_updated,
    strategy,
    created_at,
    updated_at,
    notes
)
SELECT
    CONCAT('shortseller_001_pos_', id) as position_id,
    'shortseller_001' as bot_id,
    symbol,
    side,
    size,
    avg_price as avg_entry_price,
    avg_price as current_price, -- Will be updated by bot
    leverage,
    unrealized_pnl,
    realized_pnl,
    (unrealized_pnl + realized_pnl) as total_pnl,
    CASE
        WHEN avg_price > 0 THEN (unrealized_pnl / (size * avg_price))
        ELSE 0
    END as unrealized_pnl_pct,
    stop_loss,
    take_profit,
    status,
    opened_at,
    closed_at,
    COALESCE(closed_at, opened_at) as last_updated,
    'ema_crossover' as strategy,
    opened_at as created_at,
    COALESCE(closed_at, opened_at) as updated_at,
    NULL as notes
FROM trading.positions -- Old positions table
ON CONFLICT (position_id) DO NOTHING;

-- =====================================================
-- STEP 4: Migrate Signals Data
-- =====================================================

INSERT INTO trading.signals (
    signal_id,
    bot_id,
    symbol,
    signal_type,
    strength,
    price,
    timestamp,
    strategy,
    indicators,
    executed,
    execution_trade_id,
    created_at
)
SELECT
    CONCAT('shortseller_001_sig_', id) as signal_id,
    'shortseller_001' as bot_id,
    symbol,
    signal_type,
    strength,
    price,
    timestamp,
    strategy,
    indicators,
    executed,
    CASE
        WHEN execution_id IS NOT NULL THEN CONCAT('shortseller_001_', execution_id::TEXT)
        ELSE NULL
    END as execution_trade_id,
    timestamp as created_at
FROM trading.signals -- Old signals table
ON CONFLICT (signal_id) DO NOTHING;

-- =====================================================
-- STEP 5: Migrate Account Balance Data
-- =====================================================

INSERT INTO trading.account_balance (
    bot_id,
    total_balance,
    available_balance,
    equity,
    margin_used,
    unrealized_pnl,
    realized_pnl,
    timestamp,
    snapshot_type,
    created_at
)
SELECT
    'shortseller_001' as bot_id,
    total_balance,
    available_balance,
    equity,
    margin_used,
    unrealized_pnl,
    0 as realized_pnl, -- Calculate from trades if available
    timestamp,
    'periodic' as snapshot_type,
    timestamp as created_at
FROM trading.account_balance -- Old account_balance table
ON CONFLICT DO NOTHING;

-- =====================================================
-- STEP 6: Migrate Risk Metrics Data
-- =====================================================

INSERT INTO trading.risk_metrics (
    bot_id,
    date,
    starting_equity,
    ending_equity,
    daily_pnl,
    daily_pnl_pct,
    total_trades,
    winning_trades,
    losing_trades,
    win_rate,
    gross_profit,
    gross_loss,
    net_profit,
    profit_factor,
    max_drawdown,
    sharpe_ratio,
    created_at
)
SELECT
    'shortseller_001' as bot_id,
    date,
    -- Estimate starting equity from ending equity - daily pnl
    COALESCE(ending_equity - total_pnl, 10000.00) as starting_equity,
    COALESCE(ending_equity, 10000.00) as ending_equity,
    total_pnl as daily_pnl,
    CASE
        WHEN ending_equity > 0 THEN (total_pnl / ending_equity) * 100
        ELSE 0
    END as daily_pnl_pct,
    total_trades,
    winning_trades,
    losing_trades,
    win_rate,
    -- Calculate gross profit/loss from trades if available
    (SELECT COALESCE(SUM(pnl), 0) FROM trading.trades WHERE DATE(timestamp) = rm.date AND pnl > 0) as gross_profit,
    (SELECT COALESCE(SUM(ABS(pnl)), 0) FROM trading.trades WHERE DATE(timestamp) = rm.date AND pnl < 0) as gross_loss,
    total_pnl as net_profit,
    profit_factor,
    max_drawdown,
    sharpe_ratio,
    CURRENT_TIMESTAMP as created_at
FROM trading.risk_metrics rm -- Old risk_metrics table
ON CONFLICT (bot_id, date) DO NOTHING;

-- =====================================================
-- STEP 7: Create System Event for Migration
-- =====================================================

INSERT INTO audit.system_events (
    event_type,
    event_level,
    bot_id,
    component,
    message,
    details
)
VALUES (
    'DATA_MIGRATION',
    'INFO',
    'shortseller_001',
    'migration_script',
    'Shortseller data migrated to unified schema',
    jsonb_build_object(
        'migration_script', '002_migrate_shortseller_data.sql',
        'trades_migrated', (SELECT COUNT(*) FROM trading.trades WHERE bot_id = 'shortseller_001'),
        'positions_migrated', (SELECT COUNT(*) FROM trading.positions WHERE bot_id = 'shortseller_001'),
        'signals_migrated', (SELECT COUNT(*) FROM trading.signals WHERE bot_id = 'shortseller_001'),
        'migration_timestamp', CURRENT_TIMESTAMP
    )
);

-- =====================================================
-- STEP 8: Update Statistics
-- =====================================================

-- Update bot current equity
UPDATE trading.bots
SET current_equity = (
    SELECT equity
    FROM trading.account_balance
    WHERE bot_id = 'shortseller_001'
    ORDER BY timestamp DESC
    LIMIT 1
),
last_heartbeat = CURRENT_TIMESTAMP
WHERE bot_id = 'shortseller_001';

COMMIT;

-- =====================================================
-- VERIFICATION QUERIES (Run manually)
-- =====================================================

-- Verify migration counts
/*
SELECT
    'Trades' as table_name,
    COUNT(*) as migrated_count
FROM trading.trades WHERE bot_id = 'shortseller_001'
UNION ALL
SELECT
    'Positions',
    COUNT(*)
FROM trading.positions WHERE bot_id = 'shortseller_001'
UNION ALL
SELECT
    'Signals',
    COUNT(*)
FROM trading.signals WHERE bot_id = 'shortseller_001'
UNION ALL
SELECT
    'Account Balance',
    COUNT(*)
FROM trading.account_balance WHERE bot_id = 'shortseller_001'
UNION ALL
SELECT
    'Risk Metrics',
    COUNT(*)
FROM trading.risk_metrics WHERE bot_id = 'shortseller_001';
*/

-- Verify bot registration
/*
SELECT * FROM trading.bots WHERE bot_id = 'shortseller_001';
*/

-- Verify recent trades
/*
SELECT * FROM trading.trades
WHERE bot_id = 'shortseller_001'
ORDER BY entry_time DESC
LIMIT 10;
*/
