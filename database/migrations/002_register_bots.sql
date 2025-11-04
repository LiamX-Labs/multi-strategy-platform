-- =====================================================
-- REGISTER ALL THREE TRADING BOTS
-- =====================================================
-- This migration registers the three trading bots
-- in the unified system
-- =====================================================

BEGIN;

-- =====================================================
-- REGISTER SHORTSELLER BOT
-- =====================================================

INSERT INTO trading.bots (
    bot_id,
    bot_name,
    bot_type,
    strategy_name,
    status,
    deployment_mode,
    initial_capital,
    current_equity
)
VALUES (
    'shortseller_001',
    'Multi-Asset EMA Crossover Bot',
    'shortseller',
    'EMA 240/600 Crossover',
    'active',
    'demo',
    10000.00,
    10000.00
)
ON CONFLICT (bot_id) DO UPDATE
SET updated_at = CURRENT_TIMESTAMP;

-- =====================================================
-- REGISTER LXALGO BOT
-- =====================================================

INSERT INTO trading.bots (
    bot_id,
    bot_name,
    bot_type,
    strategy_name,
    status,
    deployment_mode,
    initial_capital,
    current_equity
)
VALUES (
    'lxalgo_001',
    'LX Technical Analysis Bot',
    'lxalgo',
    'LX Multi-Indicator Strategy',
    'active',
    'demo',
    10000.00,
    10000.00
)
ON CONFLICT (bot_id) DO UPDATE
SET updated_at = CURRENT_TIMESTAMP;

-- =====================================================
-- REGISTER MOMENTUM BOT
-- =====================================================

INSERT INTO trading.bots (
    bot_id,
    bot_name,
    bot_type,
    strategy_name,
    status,
    deployment_mode,
    initial_capital,
    current_equity
)
VALUES (
    'momentum_001',
    'Volatility Breakout Momentum Bot',
    'momentum',
    '4H Volatility Breakout',
    'active',
    'demo',
    10000.00,
    10000.00
)
ON CONFLICT (bot_id) DO UPDATE
SET updated_at = CURRENT_TIMESTAMP;

COMMIT;

-- =====================================================
-- VERIFY REGISTRATION
-- =====================================================

SELECT
    bot_id,
    bot_name,
    bot_type,
    status,
    deployment_mode
FROM trading.bots
ORDER BY bot_id;
