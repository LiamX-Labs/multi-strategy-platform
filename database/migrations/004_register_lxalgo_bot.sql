-- =====================================================
-- MIGRATION 004: Register LXAlgo Bot
-- =====================================================
-- Description: Registers LXAlgo bot in the unified system
-- Prerequisites: Migration 001 completed
-- Note: LXAlgo currently has no persistence, so this just
--       sets up the bot registration and configuration
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: Register LXAlgo Bot
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
    'lxalgo_001',
    'LX Technical Analysis Bot',
    'lxalgo',
    'LX Multi-Indicator Strategy',
    'Prop trading bot using 8-rule technical analysis system with breakeven management. Max 20 trades, 2% daily circuit breaker.',
    'active',
    'demo', -- Change to 'live' when running live
    10000.00, -- Initial capital
    10000.00, -- Current equity (will be updated by bot)
    20, -- Max 20 positions (trades)
    1, -- No leverage (spot trading)
    0.02, -- 2% daily circuit breaker
    0.04, -- 4% weekly size reduction trigger
    0.15, -- 15% max drawdown
    'bybit',
    CURRENT_TIMESTAMP
)
ON CONFLICT (bot_id) DO NOTHING;

-- =====================================================
-- STEP 2: Insert LXAlgo Configuration
-- =====================================================

INSERT INTO config.bot_configurations (
    bot_id,
    config_key,
    config_value,
    config_type,
    is_active
)
VALUES
-- Strategy Parameters
(
    'lxalgo_001',
    'strategy_params',
    '{
        "strategy_name": "lx_multi_indicator",
        "rules": {
            "rule_1": "Price above 200 EMA",
            "rule_2": "RSI confirmation",
            "rule_3": "Volume spike",
            "rule_4": "MACD alignment",
            "rule_5": "Support/Resistance levels",
            "rule_6": "Trend confirmation",
            "rule_7": "Momentum indicators",
            "rule_8": "Market structure"
        },
        "min_rules_required": 5,
        "timeframes": ["1h", "4h"],
        "confirmation_required": true,
        "breakeven_management": {
            "enabled": true,
            "trigger_pnl_pct": 0.01,
            "move_stop_to_entry": true
        }
    }'::jsonb,
    'strategy_params',
    true
),
-- Risk Parameters
(
    'lxalgo_001',
    'risk_params',
    '{
        "max_trades": 20,
        "position_size_pct": 0.05,
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.10,
        "circuit_breaker": {
            "daily_loss_pct": 0.02,
            "action": "halt_trading"
        },
        "weekly_limits": {
            "reduce_size_at_loss_pct": 0.04,
            "halt_at_loss_pct": 0.06
        },
        "auto_close": {
            "enabled": true,
            "hours_in_negative": 8,
            "action": "close_position"
        }
    }'::jsonb,
    'risk_params',
    true
),
-- Trading Parameters
(
    'lxalgo_001',
    'trading_params',
    '{
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"],
        "order_type": "market",
        "slippage_tolerance_pct": 0.001,
        "retry_failed_orders": true,
        "max_retries": 3
    }'::jsonb,
    'trading_params',
    true
),
-- Execution Parameters
(
    'lxalgo_001',
    'execution_params',
    '{
        "update_interval_seconds": 60,
        "signal_validation_timeout_seconds": 300,
        "order_timeout_seconds": 30,
        "position_sync_interval_seconds": 300,
        "enable_telegram_notifications": true
    }'::jsonb,
    'execution_params',
    true
)
ON CONFLICT (bot_id, config_key, version) DO NOTHING;

-- =====================================================
-- STEP 3: Initialize Account Balance
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
    data_source
)
VALUES (
    'lxalgo_001',
    10000.00,
    10000.00,
    10000.00,
    0.00,
    0.00,
    0.00,
    CURRENT_TIMESTAMP,
    'initial',
    'system'
);

-- =====================================================
-- STEP 4: Create System Event
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
    'BOT_REGISTRATION',
    'INFO',
    'lxalgo_001',
    'migration_script',
    'LXAlgo bot registered in unified system',
    jsonb_build_object(
        'migration_script', '004_register_lxalgo_bot.sql',
        'bot_type', 'lxalgo',
        'strategy', 'lx_multi_indicator',
        'max_trades', 20,
        'initial_capital', 10000.00,
        'registration_timestamp', CURRENT_TIMESTAMP,
        'note', 'Bot registered with fresh state - no historical data to migrate'
    )
);

COMMIT;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify bot registration
SELECT
    bot_id,
    bot_name,
    strategy_name,
    status,
    deployment_mode,
    initial_capital,
    max_positions,
    max_daily_loss_pct
FROM trading.bots
WHERE bot_id = 'lxalgo_001';

-- Verify configuration
SELECT
    config_key,
    config_type,
    is_active,
    created_at
FROM config.bot_configurations
WHERE bot_id = 'lxalgo_001'
ORDER BY config_key;

-- Verify initial balance
SELECT
    total_balance,
    equity,
    timestamp,
    snapshot_type
FROM trading.account_balance
WHERE bot_id = 'lxalgo_001'
ORDER BY timestamp DESC
LIMIT 1;

-- =====================================================
-- NOTES FOR DEVELOPERS
-- =====================================================

/*
Next Steps for LXAlgo Integration:

1. Update LXAlgo Bot Code:
   - Add database connection to PostgreSQL
   - Implement trade logging to trading.trades table
   - Implement position tracking to trading.positions table
   - Log signals to trading.signals table
   - Update account balance periodically
   - Log all system events

2. Database Connection Example:
   ```python
   import psycopg2
   from psycopg2.extras import RealDictCursor

   conn = psycopg2.connect(
       host="localhost",
       database="trading_db",
       user="trading_user",
       password="secure_password"
   )

   BOT_ID = "lxalgo_001"
   ```

3. Trade Logging Example:
   ```python
   def log_trade_entry(symbol, side, quantity, price):
       trade_id = f"{BOT_ID}_{symbol}_{int(time.time())}"
       cursor.execute('''
           INSERT INTO trading.trades (
               trade_id, bot_id, symbol, side, quantity,
               entry_price, position_size_usd, entry_time,
               strategy, status
           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
       ''', (
           trade_id, BOT_ID, symbol, side, quantity,
           price, quantity * price, datetime.now(),
           'lx_multi_indicator', 'filled'
       ))
       conn.commit()
       return trade_id
   ```

4. Testing Checklist:
   - ✓ Bot can connect to database
   - ✓ Trade entries are logged correctly
   - ✓ Position updates work properly
   - ✓ Signals are recorded
   - ✓ Account balance updates
   - ✓ Risk events trigger properly
   - ✓ Circuit breakers function correctly
*/
