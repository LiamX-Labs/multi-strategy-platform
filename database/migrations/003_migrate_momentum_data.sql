-- =====================================================
-- MIGRATION 003: Migrate Momentum Bot Data
-- =====================================================
-- Description: Migrates Momentum bot data from SQLite to unified PostgreSQL schema
-- Prerequisites: Migration 001 completed
-- Source: SQLite database (data/trading.db)
-- Note: This is a template. Actual migration should use a Python script
--       to read from SQLite and insert into PostgreSQL
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: Register Momentum Bot
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
    'momentum_001',
    'Volatility Breakout Momentum Bot',
    'momentum',
    '4H Volatility Breakout',
    'Altcoin momentum strategy trading volatility breakouts on 4H timeframe. Proven +252% return over 27 months.',
    'active',
    'demo', -- Change based on actual mode
    10000.00,
    10000.00, -- Will be updated after data migration
    3, -- Max 3 positions
    1, -- No leverage (spot trading)
    0.03, -- 3% max daily loss
    0.08, -- 8% max weekly loss
    0.15, -- 15% max drawdown
    'bybit',
    CURRENT_TIMESTAMP
)
ON CONFLICT (bot_id) DO NOTHING;

-- =====================================================
-- STEP 2: Python Migration Script Reference
-- =====================================================

-- NOTE: The actual data migration from SQLite to PostgreSQL
-- should be done using a Python script. See:
-- database/migrations/migrate_momentum_sqlite_to_postgres.py

-- The script will:
-- 1. Connect to SQLite: data/trading.db
-- 2. Read from tables: trades, daily_snapshots, system_events, risk_events
-- 3. Transform data to unified schema format
-- 4. Insert into PostgreSQL with bot_id = 'momentum_001'

-- =====================================================
-- STEP 3: Placeholder for Migrated Data Verification
-- =====================================================

-- After running Python migration script, verify with these queries:

-- COMMENT: Check trades migrated
-- SELECT COUNT(*) FROM trading.trades WHERE bot_id = 'momentum_001';

-- COMMENT: Check performance snapshots
-- SELECT COUNT(*) FROM trading.risk_metrics WHERE bot_id = 'momentum_001';

-- COMMENT: Check system events
-- SELECT COUNT(*) FROM audit.system_events WHERE bot_id = 'momentum_001';

-- =====================================================
-- STEP 4: Update Bot Configuration
-- =====================================================

-- Insert Momentum-specific configuration
INSERT INTO config.bot_configurations (
    bot_id,
    config_key,
    config_value,
    config_type,
    is_active
)
VALUES
(
    'momentum_001',
    'strategy_params',
    '{
        "strategy": "volatility_breakout",
        "timeframe": "4h",
        "min_volume": 1000000,
        "breakout_threshold": 1.5,
        "atr_multiplier": 1.5,
        "trailing_stop_activation_pct": 0.02,
        "trailing_stop_distance_pct": 0.01,
        "max_trades_per_day": 5,
        "position_size_pct": 0.05
    }'::jsonb,
    'strategy_params',
    true
),
(
    'momentum_001',
    'risk_params',
    '{
        "max_position_size_pct": 0.05,
        "max_total_exposure_pct": 0.15,
        "daily_loss_limit_pct": 0.03,
        "weekly_loss_limit_pct": 0.08,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
        "max_positions": 3,
        "reduce_size_at_weekly_loss_pct": 0.04,
        "halt_trading_at_weekly_loss_pct": 0.06
    }'::jsonb,
    'risk_params',
    true
),
(
    'momentum_001',
    'symbols',
    '{
        "watchlist": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "MATICUSDT"],
        "excluded": [],
        "min_market_cap": 1000000000
    }'::jsonb,
    'trading_params',
    true
)
ON CONFLICT (bot_id, config_key, version) DO NOTHING;

-- =====================================================
-- STEP 5: Create System Event for Migration
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
    'momentum_001',
    'migration_script',
    'Momentum bot registered in unified system (data migration pending)',
    jsonb_build_object(
        'migration_script', '003_migrate_momentum_data.sql',
        'python_script_required', 'migrate_momentum_sqlite_to_postgres.py',
        'source_database', 'SQLite (data/trading.db)',
        'destination_database', 'PostgreSQL (unified schema)',
        'registration_timestamp', CURRENT_TIMESTAMP
    )
);

COMMIT;

-- =====================================================
-- POST-MIGRATION VERIFICATION QUERIES
-- =====================================================

-- After Python migration script completes, run these:

/*
-- 1. Verify bot registration
SELECT * FROM trading.bots WHERE bot_id = 'momentum_001';

-- 2. Check configuration
SELECT * FROM config.bot_configurations WHERE bot_id = 'momentum_001';

-- 3. Verify trades migrated
SELECT
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE exit_time IS NOT NULL) as closed_trades,
    COUNT(*) FILTER (WHERE exit_time IS NULL) as open_trades,
    SUM(pnl_usd) FILTER (WHERE exit_time IS NOT NULL) as total_pnl
FROM trading.trades
WHERE bot_id = 'momentum_001';

-- 4. Check daily performance
SELECT
    date,
    total_trades,
    win_rate,
    daily_pnl
FROM trading.risk_metrics
WHERE bot_id = 'momentum_001'
ORDER BY date DESC
LIMIT 30;

-- 5. Verify system events
SELECT
    event_type,
    event_level,
    COUNT(*) as event_count
FROM audit.system_events
WHERE bot_id = 'momentum_001'
GROUP BY event_type, event_level
ORDER BY event_count DESC;

-- 6. Update bot equity from latest balance
UPDATE trading.bots
SET current_equity = (
    SELECT ending_equity
    FROM trading.risk_metrics
    WHERE bot_id = 'momentum_001'
    ORDER BY date DESC
    LIMIT 1
),
last_heartbeat = CURRENT_TIMESTAMP
WHERE bot_id = 'momentum_001';
*/
