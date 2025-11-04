# TELEGRAM ANALYTICS INTEGRATION GUIDE

## Overview

The Alpha Command Center now includes comprehensive database analytics integration, allowing you to monitor trading activity and performance metrics directly through Telegram. This integration connects to your PostgreSQL and Redis databases to provide real-time summaries of trading operations.

---

## Features

### Real-Time Analytics
- Portfolio overview across all bots
- Individual bot performance metrics
- Trading statistics and P&L tracking
- Active position monitoring
- Trade history analysis
- Daily performance breakdowns
- Redis cache statistics

### Summary-Focused Design
**IMPORTANT**: All analytics features are designed for **summary data only**. They do NOT allow:
- Direct trading operations
- Position modifications
- Order placement
- Strategy parameter changes

This is a read-only analytics layer for monitoring purposes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram User                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Telegram Command Center                    │
│                   (bot.py)                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│            Analytics Handlers Module                    │
│          (analytics_handlers.py)                        │
│                                                         │
│  • Format queries and responses                         │
│  • Handle user arguments                               │
│  • Generate formatted reports                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│          Database Analytics Module                      │
│            (db_analytics.py)                            │
│                                                         │
│  • PostgreSQL queries                                   │
│  • Redis statistics                                     │
│  • Data aggregation                                     │
└────────────┬────────────────┬────────────────────────────┘
             │                │
             ▼                ▼
    ┌────────────┐    ┌────────────┐
    │ PostgreSQL │    │   Redis    │
    │  Database  │    │   Cache    │
    └────────────┘    └────────────┘
```

---

## Available Commands

### 1. Quick Status - `/quick`

**Purpose**: Fast overview of portfolio and today's trading

**Usage**:
```
/quick
```

**Output**:
- Active bots count
- Total portfolio equity
- Today's trade count
- Today's P&L
- Open positions count

**Example**:
```
⚡ QUICK STATUS
━━━━━━━━━━━━━━━━━━━━━
⏰ 2025-10-25 14:30:00

PORTFOLIO
├─ Bots: 3/3 active
└─ Equity: $152,450.00

TODAY
├─ Trades: 8
├─ W/L: 5/3
🟢 P&L: $+1,245.50

POSITIONS
└─ Open: 2

━━━━━━━━━━━━━━━━━━━━━
Use /analytics for detailed report
```

---

### 2. Full Analytics - `/analytics [bot_id] [days]`

**Purpose**: Comprehensive trading performance report

**Usage**:
```
/analytics              # All bots, last 7 days
/analytics alpha        # Alpha bot, last 7 days
/analytics alpha 30     # Alpha bot, last 30 days
/analytics bravo 14     # Bravo bot, last 14 days
```

**Parameters**:
- `bot_id` (optional): `alpha`, `bravo`, or `charlie`
- `days` (optional): Number of days (1-90, default: 7)

**Output**:
- Bot information (capital, equity, return %)
- Trading statistics (total trades, win rate)
- P&L breakdown (total, average, max win/loss)
- Fee summary

**Example**:
```
📊 TRADING ANALYTICS REPORT
━━━━━━━━━━━━━━━━━━━━━
⏰ 2025-10-25 14:30:00 UTC
📅 Period: Last 7 days

BOT: ALPHA SYSTEM
├─ ID: shortseller_001
├─ Type: shortseller
├─ Status: ACTIVE
├─ Capital: $50,000.00
├─ Equity: $52,340.00
└─ Return: +4.68%

TRADING STATISTICS
├─ Total Trades: 42
├─ Closed: 38
├─ Open: 4
├─ Wins: 24
├─ Losses: 14
└─ Win Rate: 63.16%

PROFIT & LOSS
🟢 Total P&L: $+2,340.00
├─ Avg P&L: $+61.58
├─ Max Win: $+450.00
├─ Max Loss: $-180.00
└─ Total Fees: $85.20
```

---

### 3. Active Positions - `/positions [bot_id]`

**Purpose**: View all currently open positions

**Usage**:
```
/positions              # All positions
/positions alpha        # Alpha bot positions
/positions bravo        # Bravo bot positions
```

**Output**:
- Position details (symbol, side, size)
- Entry and current prices
- Unrealized P&L (USD and %)
- Stop loss and take profit levels
- Time opened

**Example**:
```
📍 ACTIVE POSITIONS
━━━━━━━━━━━━━━━━━━━━━
⏰ 2025-10-25 14:30:00

Total Positions: 3

🟢 BTCUSDT (LONG)
├─ Bot: shortseller_001
├─ Size: 0.5000
├─ Entry: $45,230.00
├─ Current: $45,890.00
├─ P&L: $+330.00 (+1.46%)
├─ SL: $44,500.00
├─ TP: $46,500.00
└─ Opened: 2025-10-25 12:15

🔴 ETHUSDT (SHORT)
├─ Bot: lxalgo_001
├─ Size: 5.2000
├─ Entry: $2,450.00
├─ Current: $2,475.00
├─ P&L: $-130.00 (-1.02%)
└─ Opened: 2025-10-25 13:45
```

---

### 4. Recent Trades - `/trades [bot_id] [limit]`

**Purpose**: View recent trade history

**Usage**:
```
/trades                 # Last 10 trades (all bots)
/trades alpha           # Last 10 trades (alpha)
/trades alpha 20        # Last 20 trades (alpha)
/trades bravo 50        # Last 50 trades (bravo, max)
```

**Parameters**:
- `bot_id` (optional): Bot identifier
- `limit` (optional): Number of trades (1-50, default: 10)

**Output**:
- Trade identification
- Symbol and side
- Entry/exit prices
- P&L and exit reason
- Timestamps

**Example**:
```
📋 RECENT TRADES
━━━━━━━━━━━━━━━━━━━━━
Showing last 10 trades

🟢 BTCUSDT - LONG
├─ ID: trade_abc123...
├─ Bot: shortseller_001
├─ Entry: $45,100.00
├─ Exit: $45,650.00
├─ P&L: $+275.00 (+1.22%)
├─ Reason: take_profit
├─ Status: filled
└─ Time: 10-25 14:15

🔴 ETHUSDT - SHORT
├─ ID: trade_def456...
├─ Bot: lxalgo_001
├─ Entry: $2,480.00
├─ Exit: $2,510.00
├─ P&L: $-156.00 (-1.21%)
├─ Reason: stop_loss
├─ Status: filled
└─ Time: 10-25 13:50
```

---

### 5. Daily Performance - `/daily [bot_id] [days]`

**Purpose**: Daily breakdown of trading performance

**Usage**:
```
/daily                  # Last 7 days (all bots)
/daily alpha            # Last 7 days (alpha)
/daily alpha 14         # Last 14 days (alpha)
```

**Parameters**:
- `bot_id` (optional): Bot identifier
- `days` (optional): Number of days (1-30, default: 7)

**Output**:
- Daily trade counts
- Win/loss breakdown per day
- Daily P&L
- Period summary

**Example**:
```
📅 DAILY PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━
Period: Last 7 days

🟢 2025-10-25
├─ Trades: 8
├─ W/L: 5/3
├─ P&L: $+450.00
└─ Avg: $+56.25

🔴 2025-10-24
├─ Trades: 6
├─ W/L: 2/4
├─ P&L: $-180.00
└─ Avg: $-30.00

🟢 2025-10-23
├─ Trades: 10
├─ W/L: 7/3
├─ P&L: $+620.00
└─ Avg: $+62.00

━━━━━━━━━━━━━━━━━━━━━
PERIOD SUMMARY
├─ Total Trades: 54
└─ Total P&L: $+2,340.00
```

---

### 6. Cache Statistics - `/cache`

**Purpose**: Redis cache performance metrics

**Usage**:
```
/cache
```

**Output**:
- Total keys stored
- Memory usage
- Connected clients
- Uptime
- Cache hit rate

**Example**:
```
💾 CACHE STATISTICS
━━━━━━━━━━━━━━━━━━━━━
⏰ 2025-10-25 14:30:00

Redis Cache Status
├─ Total Keys: 1,247
├─ Memory Used: 2.5MB
├─ Clients: 3
├─ Uptime: 15 days
└─ Hit Rate: 94.50%
```

---

## Bot Identifiers

The analytics commands use simple bot identifiers that map to the actual bot IDs:

| Identifier | Bot Name | Actual Bot ID | Strategy |
|------------|----------|---------------|----------|
| `alpha` | ALPHA SYSTEM | `shortseller_001` | Multi-Asset Short Seller |
| `bravo` | BRAVO SYSTEM | `lxalgo_001` | LX Algorithm Executor |
| `charlie` | CHARLIE SYSTEM | `momentum_001` | Momentum Strategy Engine |

You can use either the simple identifier or the full bot ID in commands.

---

## Database Schema

The analytics module queries the following tables:

### PostgreSQL Tables

**trading.bots**
- Bot registry and configuration
- Equity tracking
- Status monitoring

**trading.trades**
- All executed trades
- Entry/exit data
- P&L calculations
- Strategy metadata

**trading.positions**
- Active positions
- Unrealized P&L
- Risk parameters

**trading.risk_metrics**
- Daily performance metrics
- Win rates and ratios
- Drawdown tracking

**analytics.portfolio_snapshots**
- Portfolio-wide aggregates
- Cross-bot exposure

### Redis Keys
- Live position data
- Latest market prices
- Cache performance stats

---

## Setup & Configuration

### Environment Variables

The analytics module requires these environment variables (set in [telegram_manager/.env](../../telegram_manager/.env)):

```bash
# PostgreSQL Connection
POSTGRES_HOST=shortseller_postgres
POSTGRES_PORT=5433
POSTGRES_DB=trading_db
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=your_password_here

# Redis Connection
REDIS_HOST=shortseller_redis
REDIS_PORT=6379
REDIS_PASSWORD=your_password_here
```

### Python Dependencies

Add to [telegram_manager/requirements.txt](../../telegram_manager/requirements.txt):

```
psycopg2-binary>=2.9.9
redis>=5.0.0
```

### Docker Configuration

The telegram_manager container needs network access to the database:

```yaml
telegram_manager:
  networks:
    - trading-network
  depends_on:
    - shortseller_postgres
    - shortseller_redis
```

---

## Installation Steps

### 1. Update Requirements

```bash
cd /home/william/STRATEGIES/Alpha/telegram_manager
pip install psycopg2-binary redis
```

Or rebuild the Docker container:

```bash
cd /home/william/STRATEGIES/Alpha
docker-compose build telegram_manager
```

### 2. Configure Environment

Update [telegram_manager/.env](../../telegram_manager/.env) with database credentials:

```bash
# Add these lines
POSTGRES_HOST=shortseller_postgres
POSTGRES_PORT=5433
POSTGRES_DB=trading_db
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=your_actual_password

REDIS_HOST=shortseller_redis
REDIS_PORT=6379
REDIS_PASSWORD=your_actual_password
```

### 3. Restart Command Center

```bash
docker-compose restart telegram_manager

# Verify analytics are enabled
docker-compose logs telegram_manager | grep "Analytics features enabled"
```

### 4. Test Commands

In Telegram:
```
/quick
/analytics alpha 7
/positions
```

---

## Security Considerations

### 1. Read-Only Access

The analytics module uses:
- `SELECT` queries only (no INSERT, UPDATE, DELETE)
- Parameterized queries to prevent SQL injection
- Connection pooling with timeouts

### 2. Authorization

All analytics commands require:
- Telegram user authentication
- Authorized user ID in `C2_TELEGRAM_ADMIN_IDS`
- Decorator-based access control

### 3. Data Privacy

The analytics:
- Do NOT expose API keys or passwords
- Do NOT show full trade IDs (truncated to 12 chars)
- Do NOT include sensitive strategy parameters

### 4. Error Handling

- Database connection errors are logged but not exposed to users
- Failed queries return empty results gracefully
- Analytics unavailable message shown if database unreachable

---

## Troubleshooting

### Analytics Not Available

**Symptom**: "Analytics features are currently unavailable"

**Causes**:
1. Missing Python dependencies
2. Database connection failure
3. Incorrect environment variables

**Solutions**:
```bash
# Check if psycopg2 is installed
docker exec telegram_c2 python -c "import psycopg2; print('OK')"

# Check if redis is installed
docker exec telegram_c2 python -c "import redis; print('OK')"

# Verify environment variables
docker exec telegram_c2 printenv | grep -E "(POSTGRES|REDIS)"

# Check database connectivity
docker exec telegram_c2 ping -c 3 shortseller_postgres
docker exec telegram_c2 ping -c 3 shortseller_redis
```

### Empty Results

**Symptom**: Commands return "No data" or "No trades found"

**Causes**:
1. No trading activity in specified period
2. Bot ID doesn't exist
3. Database tables not populated

**Solutions**:
```bash
# Check if bots are registered
docker exec shortseller_postgres psql -U trading_user -d trading_db \
  -c "SELECT bot_id, bot_name, status FROM trading.bots;"

# Check if trades exist
docker exec shortseller_postgres psql -U trading_user -d trading_db \
  -c "SELECT COUNT(*) FROM trading.trades;"
```

### Connection Timeouts

**Symptom**: Long delays or timeout errors

**Causes**:
1. Database under heavy load
2. Network issues
3. Slow queries

**Solutions**:
- Increase query timeout in db_analytics.py
- Add database indexes (see migration scripts)
- Check database resource usage

---

## Performance Optimization

### Query Limits

All commands have built-in limits:
- `/analytics`: Max 90 days
- `/trades`: Max 50 trades
- `/daily`: Max 30 days
- `/positions`: All open positions (usually < 100)

### Caching Strategy

Consider implementing:
- Result caching for frequently requested data
- Redis cache for active positions
- Materialized views for daily aggregates

### Database Indexes

Ensure these indexes exist (from migration scripts):
```sql
CREATE INDEX idx_trades_bot_time ON trading.trades(bot_id, entry_time DESC);
CREATE INDEX idx_trades_open ON trading.trades(bot_id, symbol) WHERE exit_time IS NULL;
CREATE INDEX idx_positions_bot_status ON trading.positions(bot_id, status);
```

---

## Future Enhancements

### Planned Features

1. **Automated Reports**
   - Daily summary notifications
   - Weekly performance digest
   - Risk limit breach alerts

2. **Charts & Visualizations**
   - Equity curves
   - P&L charts
   - Win rate trends

3. **Advanced Analytics**
   - Risk-adjusted returns (Sharpe, Sortino)
   - Correlation analysis
   - Strategy comparison

4. **Custom Queries**
   - User-defined date ranges
   - Symbol-specific analytics
   - Strategy-level breakdowns

---

## API Reference

### DatabaseAnalytics Class

Located in [db_analytics.py](../../telegram_manager/db_analytics.py)

#### Methods

**get_portfolio_summary() → Dict**
- Returns: Total equity, bot counts, capital allocation

**get_bot_summary(bot_id: str = None) → List[Dict]**
- Parameters: Optional bot_id
- Returns: Bot configuration and performance

**get_trading_summary(bot_id: str = None, days: int = 7) → Dict**
- Parameters: Optional bot_id, number of days
- Returns: Trade counts, win rate, P&L totals

**get_active_positions(bot_id: str = None) → List[Dict]**
- Parameters: Optional bot_id
- Returns: All open positions with P&L

**get_recent_trades(bot_id: str = None, limit: int = 10) → List[Dict]**
- Parameters: Optional bot_id, result limit
- Returns: Recent trade history

**get_daily_performance(bot_id: str = None, days: int = 7) → List[Dict]**
- Parameters: Optional bot_id, number of days
- Returns: Daily aggregated performance

**get_redis_stats() → Dict**
- Returns: Redis cache statistics

---

## Examples & Use Cases

### Daily Morning Routine

```
/quick                    # Quick overview
/positions               # Check open positions
/daily alpha 1           # Yesterday's alpha performance
```

### End of Week Review

```
/analytics 7             # Weekly performance all bots
/analytics alpha 7       # Weekly alpha details
/analytics bravo 7       # Weekly bravo details
/analytics charlie 7     # Weekly charlie details
```

### Real-Time Monitoring

```
/positions              # Current positions
/trades 5               # Last 5 trades
/quick                  # Quick status refresh
```

### Monthly Analysis

```
/analytics 30           # Month performance
/daily 30               # Daily breakdown
/cache                  # Cache health check
```

---

## Support & Documentation

### Related Documentation

- [Command Center Guide](COMMAND_CENTER_GUIDE.md) - Main C2 documentation
- [Database Architecture](../database/DATABASE_ARCHITECTURE_CATALOGUE.md) - Database schema
- [Implementation Guide](../database/DATABASE_IMPLEMENTATION_GUIDE.md) - Database setup

### Getting Help

1. Check logs: `docker-compose logs telegram_manager`
2. Verify database: `docker-compose logs shortseller_postgres`
3. Test connectivity: `docker exec telegram_c2 ping shortseller_postgres`
4. Review configuration: Check `.env` files

---

## Conclusion

The Telegram Analytics Integration provides a powerful, secure, and user-friendly way to monitor trading operations from anywhere. By keeping the interface summary-focused and read-only, it ensures safe monitoring without risking accidental trade modifications.

**Key Benefits**:
- ✅ Real-time portfolio monitoring
- ✅ Comprehensive performance analytics
- ✅ Secure read-only access
- ✅ Mobile-friendly Telegram interface
- ✅ Multi-bot support
- ✅ Historical analysis capabilities

**Remember**: This is a monitoring tool. All trading operations should be handled by the trading bots themselves, not through the command center.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-25
**Status**: ✅ Complete and Ready for Use
