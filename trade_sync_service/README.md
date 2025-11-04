# Trade Sync Service

Automated service for syncing completed trades from Bybit API to PostgreSQL database with execution reason tracking.

## Overview

This service:
- **Initial backfill**: Syncs last 3 months of completed trades on first run
- **Hourly sync**: Continuously syncs new completed trades every hour
- **Execution tracking**: Preserves entry and exit reasons from `client_order_id`
- **Rate limiting**: Respects Bybit API rate limits (10 req/sec)
- **Duplicate prevention**: Uses UPSERT to avoid duplicate entries
- **Monitoring**: Tracks sync status and statistics

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Bybit Exchange API                      │
│         (Source of Truth for Trades)                │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ REST API (Hourly Sync)
                   │ /v5/execution/list
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│            Trade Sync Service                        │
│  ┌─────────────────────────────────────────────┐   │
│  │  1. Fetch executions from Bybit              │   │
│  │  2. Parse orderLinkId for execution reasons  │   │
│  │  3. Match buy/sell pairs (FIFO)              │   │
│  │  4. Calculate PnL and metrics                │   │
│  │  5. Insert into completed_trades table       │   │
│  └─────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│          PostgreSQL Database                         │
│  ┌─────────────────────────────────────────────┐   │
│  │  trading.completed_trades                    │   │
│  │  - Entry/Exit prices and times               │   │
│  │  - Entry/Exit reasons (parsed from orderLinkId)│
│  │  - PnL calculations                          │   │
│  │  - Commission tracking                       │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │  trading.sync_status                         │   │
│  │  - Sync job tracking                         │   │
│  │  - Error monitoring                          │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Database Schema

### completed_trades Table

Stores completed trades with full execution details:

```sql
CREATE TABLE trading.completed_trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE,
    bot_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- Entry leg
    entry_order_id VARCHAR(100),
    entry_client_order_id VARCHAR(100),  -- Format: "bot_id:reason:timestamp"
    entry_side VARCHAR(10),
    entry_price DECIMAL(20, 8),
    entry_qty DECIMAL(20, 8),
    entry_time TIMESTAMP WITH TIME ZONE,
    entry_reason VARCHAR(50),  -- Parsed execution reason
    entry_commission DECIMAL(20, 8),

    -- Exit leg
    exit_order_id VARCHAR(100),
    exit_client_order_id VARCHAR(100),  -- Format: "bot_id:reason:timestamp"
    exit_side VARCHAR(10),
    exit_price DECIMAL(20, 8),
    exit_qty DECIMAL(20, 8),
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_reason VARCHAR(50),  -- KEY FIELD - stop_loss, take_profit, trailing_stop, etc.
    exit_commission DECIMAL(20, 8),

    -- Performance metrics
    gross_pnl DECIMAL(20, 8),
    net_pnl DECIMAL(20, 8),
    pnl_pct DECIMAL(10, 6),
    total_commission DECIMAL(20, 8),
    holding_duration_seconds INTEGER,

    -- Metadata
    source VARCHAR(20) DEFAULT 'bybit_api',
    synced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE
);
```

### Execution Reason Tracking

The `client_order_id` (Bybit's `orderLinkId`) contains execution reasons:

**Format:** `"bot_id:reason:timestamp"`

**Examples:**
- `"shortseller_001:entry:1678886400"` → Entry trade
- `"momentum_001:trailing_stop:1678886600"` → Closed by trailing stop
- `"lxalgo_001:take_profit:1678886700"` → Closed at take profit

This allows analysis of:
- Which exit strategies are most profitable
- How long trades stay open by exit reason
- Win rates by exit reason

## Installation

### 1. Database Setup

Run the migration to create tables:

```bash
# Connect to PostgreSQL
psql -h pgbouncer -p 6432 -U trading_user -d trading_db

# Run migration
\i /path/to/database/migrations/004_create_completed_trades_table.sql
```

### 2. Environment Setup

Copy and configure environment variables:

```bash
cd trade_sync_service
cp .env.example .env
# Edit .env with your credentials
```

**Required environment variables:**
- `BYBIT_API_KEY` - Your Bybit API key
- `BYBIT_API_SECRET` - Your Bybit API secret
- `POSTGRES_PASSWORD` - PostgreSQL password

### 3. Install Dependencies

**Option A: Using Docker (Recommended)**

```bash
docker-compose up -d
```

**Option B: Local Installation**

```bash
pip install -r requirements.txt
```

## Usage

### Command-Line Interface

```bash
# Test connections
python main.py test

# Initial 3-month backfill (all bots)
python main.py backfill --months 3

# Backfill specific bot
python main.py backfill --months 3 --bot shortseller_001

# Single hourly sync (all bots)
python main.py sync

# Sync specific bot
python main.py sync --bot lxalgo_001

# Run continuous service (syncs every hour)
python main.py run

# Show statistics
python main.py stats

# Show statistics for specific bot
python main.py stats --bot momentum_001
```

### Docker Usage

```bash
# Start service (runs continuous sync)
docker-compose up -d

# View logs
docker-compose logs -f trade-sync-service

# Run one-time backfill
docker-compose run --rm trade-sync-service python main.py backfill --months 3

# Run single sync
docker-compose run --rm trade-sync-service python main.py sync

# View statistics
docker-compose run --rm trade-sync-service python main.py stats

# Stop service
docker-compose down
```

## Configuration

### Rate Limiting

The service respects Bybit's API rate limits:

```python
BYBIT_RATE_LIMIT_PER_SECOND = 10  # 10 requests/second
RATE_LIMIT_DELAY = 0.12  # 120ms between requests
```

### Backfill Configuration

```python
BACKFILL_MONTHS = 3  # Initial backfill period
BACKFILL_BATCH_DAYS = 1  # Process in 1-day chunks
```

### Sync Configuration

```python
HOURLY_SYNC_OVERLAP_HOURS = 2  # Fetch last 2 hours (safety overlap)
SYNC_INTERVAL_SECONDS = 3600  # 1 hour between syncs
```

### Registered Bots

Edit `config.py` to add/remove bots:

```python
REGISTERED_BOTS = [
    'shortseller_001',
    'lxalgo_001',
    'momentum_001'
]
```

## Monitoring

### Sync Status Table

Track sync job execution:

```sql
SELECT * FROM trading.sync_status
ORDER BY sync_started_at DESC
LIMIT 10;
```

Fields:
- `sync_type`: 'backfill', 'hourly', 'manual'
- `status`: 'running', 'completed', 'failed', 'partial'
- `trades_synced`: Number of trades synced
- `duration_seconds`: Job duration
- `error_message`: Error details if failed

### Statistics Queries

```sql
-- Completed trades count by bot
SELECT bot_id, COUNT(*) as total_trades
FROM trading.completed_trades
GROUP BY bot_id;

-- Exit reason breakdown
SELECT
    exit_reason,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE net_pnl > 0) as wins,
    ROUND(AVG(net_pnl), 2) as avg_pnl
FROM trading.completed_trades
WHERE bot_id = 'shortseller_001'
GROUP BY exit_reason
ORDER BY count DESC;

-- Recent sync jobs
SELECT
    bot_id,
    sync_type,
    status,
    trades_synced,
    duration_seconds,
    sync_completed_at
FROM trading.sync_status
WHERE status = 'completed'
ORDER BY sync_completed_at DESC
LIMIT 20;
```

### Using the Summary View

```sql
-- Daily trade summary (pre-aggregated)
SELECT * FROM trading.completed_trades_summary
WHERE bot_id = 'momentum_001'
  AND trade_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY trade_date DESC;
```

## Analytics Integration

The `telegram_manager/db_analytics.py` module has been updated to use the `completed_trades` table:

```python
from telegram_manager.db_analytics import get_analytics

analytics = get_analytics()

# Get trading summary (uses completed_trades)
summary = analytics.get_trading_summary('shortseller_001', days=7)

# Get recent trades (uses completed_trades)
trades = analytics.get_recent_trades('lxalgo_001', limit=10)

# Get exit reason breakdown (NEW)
reasons = analytics.get_exit_reason_breakdown('momentum_001', days=30)
```

## Troubleshooting

### Connection Test Failed

```bash
# Test database connection
psql -h pgbouncer -p 6432 -U trading_user -d trading_db -c "SELECT 1"

# Test Bybit API
curl -X GET "https://api.bybit.com/v5/market/time"
```

### No Trades Synced

1. Check if executions exist on Bybit:
   - Log into Bybit web interface
   - Go to Orders → Trade History
   - Verify trades exist in the time range

2. Check `client_order_id` format:
   - Ensure your bots set `orderLinkId` in format: `"bot_id:reason:timestamp"`

3. Check logs:
   ```bash
   tail -f logs/sync.log
   ```

### Duplicate Trades

The service uses UPSERT to prevent duplicates:
- `trade_id` is unique (primary key)
- Duplicate inserts update `synced_at` timestamp only

### Rate Limiting Errors

If you see `429 Too Many Requests`:
- Increase `RATE_LIMIT_DELAY` in `config.py`
- Reduce `BACKFILL_BATCH_DAYS` for slower backfill

## Performance

### Backfill Performance

- **3-month backfill**: ~10-15 minutes per bot (depending on trade count)
- **Daily batch**: ~1-2 seconds
- **Rate**: ~8-10 requests/second (under limit of 10)

### Hourly Sync Performance

- **2-hour window**: ~1-2 seconds
- **Typical trades**: 0-10 trades per hour per bot
- **Resource usage**: ~50-100 MB RAM, minimal CPU

### Database Performance

Indexes optimize queries:
- `idx_completed_trades_bot` - Bot + time queries
- `idx_completed_trades_recent` - Last 90 days (partial index)
- `idx_completed_trades_exit_reason` - Exit reason analysis

## Development

### Project Structure

```
trade_sync_service/
├── main.py              # Entry point with CLI
├── sync_service.py      # Main sync service logic
├── bybit_client.py      # Bybit API client
├── trade_matcher.py     # Buy/sell matching logic
├── database.py          # PostgreSQL operations
├── config.py            # Configuration
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container image
├── docker-compose.yml   # Docker orchestration
└── README.md            # This file
```

### Running Tests

```bash
# Test database connection
python main.py test

# Test sync on single day
python -c "
from sync_service import TradeSyncService
import asyncio
from datetime import datetime, timedelta, timezone

service = TradeSyncService()
end = datetime.now(timezone.utc)
start = end - timedelta(days=1)
asyncio.run(service.sync_time_range('shortseller_001', start, end, 'manual'))
"
```

### Adding New Bots

1. Register in database:
   ```sql
   INSERT INTO trading.bots (bot_id, bot_name, bot_type, status, deployment_mode)
   VALUES ('newbot_001', 'New Bot', 'strategy_type', 'active', 'live');
   ```

2. Add to `config.py`:
   ```python
   REGISTERED_BOTS = [
       'shortseller_001',
       'lxalgo_001',
       'momentum_001',
       'newbot_001'  # Add here
   ]
   ```

3. Run backfill:
   ```bash
   python main.py backfill --months 3 --bot newbot_001
   ```

## License

Internal use only.

## Support

For issues or questions, contact the development team or check logs at:
- Local: `./logs/sync.log`
- Docker: `docker-compose logs -f trade-sync-service`
