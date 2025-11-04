# Trade Sync Service - Deployment Guide

## Quick Start Deployment

### Step 1: Run Database Migration

```bash
# On your server (194.146.12.132)
ssh root@194.146.12.132

# Navigate to project directory
cd /root/projects

# Connect to database and run migration
docker exec -i postgres psql -U trading_user -d trading_db < Alpha/database/migrations/004_create_completed_trades_table.sql

# Verify tables created
docker exec -i postgres psql -U trading_user -d trading_db -c "\dt trading.*"
```

Expected output should include:
- `trading.completed_trades`
- `trading.sync_status`

### Step 2: Configure Environment

```bash
# Navigate to sync service directory
cd /root/projects/Alpha/trade_sync_service

# Copy and edit environment file
cp .env.example .env
nano .env
```

**Edit the following in `.env`:**

```bash
# Use your actual Bybit API credentials
BYBIT_API_KEY=your_actual_api_key
BYBIT_API_SECRET=your_actual_api_secret
BYBIT_TESTNET=false  # Set to true for testing

# Use your PostgreSQL password
POSTGRES_PASSWORD=your_actual_postgres_password

# Optional: Enable Telegram alerts
ENABLE_TELEGRAM_ALERTS=true
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### Step 3: Test Connections

```bash
# Build and test the service
docker-compose build

# Test database and API connections
docker-compose run --rm trade-sync-service python main.py test
```

Expected output:
```
✓ PostgreSQL connection established
✓ Bybit API connection successful
All connection tests passed
```

### Step 4: Run Initial Backfill

**IMPORTANT**: This will fetch the last 3 months of trades. Takes ~10-15 minutes per bot.

```bash
# Run 3-month backfill for all bots
docker-compose run --rm trade-sync-service python main.py backfill --months 3

# Or backfill specific bot
docker-compose run --rm trade-sync-service python main.py backfill --months 3 --bot shortseller_001
```

Watch the progress:
```
Starting backfill for all bots: ['shortseller_001', 'lxalgo_001', 'momentum_001']
Backfilling batch: 2025-08-01 to 2025-08-02
Fetched 45 executions
Matched 12 trades from 12 buys and 12 sells
Batch complete: 12 matched, 12 inserted
...
Backfill complete for shortseller_001: 234 total matched, 234 total inserted
```

### Step 5: Verify Backfill

```bash
# Check completed trades count
docker exec -i postgres psql -U trading_user -d trading_db -c "
SELECT bot_id, COUNT(*) as trades, MIN(exit_time), MAX(exit_time)
FROM trading.completed_trades
GROUP BY bot_id;"

# Check sync status
docker exec -i postgres psql -U trading_user -d trading_db -c "
SELECT * FROM trading.sync_status
ORDER BY sync_completed_at DESC
LIMIT 5;"
```

### Step 6: Start Continuous Service

```bash
# Start the service (runs hourly sync)
docker-compose up -d

# Verify it's running
docker-compose ps

# View logs
docker-compose logs -f trade-sync-service
```

Expected output:
```
Starting continuous sync loop
Running scheduled hourly sync
shortseller_001: 3 matched, 2 inserted
lxalgo_001: 1 matched, 1 inserted
momentum_001: 0 matched, 0 inserted
Waiting 3600s until next sync
```

## Production Deployment Checklist

- [ ] Database migration completed successfully
- [ ] Environment variables configured (`.env` file)
- [ ] Bybit API credentials are valid and have permissions
- [ ] Connection test passed (`python main.py test`)
- [ ] Initial backfill completed for all bots
- [ ] Verified trades exist in `trading.completed_trades` table
- [ ] Service started with `docker-compose up -d`
- [ ] Logs show successful hourly syncs
- [ ] Telegram alerts configured (if enabled)
- [ ] Monitoring dashboard updated (if applicable)

## Integration with Main Docker Compose

To integrate with your main `docker-compose.yml`:

```yaml
# In your main /root/projects/docker-compose.yml
services:
  # ... existing services ...

  trade-sync-service:
    build:
      context: ./Alpha/trade_sync_service
      dockerfile: Dockerfile
    container_name: trade-sync-service
    restart: unless-stopped
    env_file:
      - ./Alpha/trade_sync_service/.env
    volumes:
      - ./Alpha/trade_sync_service/logs:/var/log/trade_sync_service
    networks:
      - trading-network
    depends_on:
      - pgbouncer
      - redis
    healthcheck:
      test: ["CMD", "python", "main.py", "test"]
      interval: 5m
      timeout: 30s
      retries: 3
```

Then start with your main stack:

```bash
cd /root/projects
docker-compose up -d trade-sync-service
```

## Monitoring and Maintenance

### Daily Checks

```bash
# Check service status
docker-compose ps trade-sync-service

# Check recent logs
docker-compose logs --tail 50 trade-sync-service

# Check sync statistics
docker-compose run --rm trade-sync-service python main.py stats
```

### Weekly Checks

```bash
# Verify trade counts are increasing
docker exec -i postgres psql -U trading_user -d trading_db -c "
SELECT
    bot_id,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE exit_time >= CURRENT_DATE - INTERVAL '7 days') as last_7_days
FROM trading.completed_trades
GROUP BY bot_id;"

# Check for failed syncs
docker exec -i postgres psql -U trading_user -d trading_db -c "
SELECT * FROM trading.sync_status
WHERE status = 'failed'
ORDER BY sync_started_at DESC
LIMIT 10;"
```

### Log Rotation

Add to `/etc/logrotate.d/trade-sync-service`:

```
/root/projects/Alpha/trade_sync_service/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
```

## Troubleshooting Production Issues

### Issue: Service Not Starting

```bash
# Check logs
docker-compose logs trade-sync-service

# Check environment variables
docker-compose run --rm trade-sync-service env | grep -E "(BYBIT|POSTGRES)"

# Test connections manually
docker-compose run --rm trade-sync-service python main.py test
```

### Issue: No New Trades Being Synced

```bash
# Check if trades exist on Bybit
# Log into Bybit web interface → Orders → Trade History

# Run manual sync with verbose logging
docker-compose run --rm -e LOG_LEVEL=DEBUG trade-sync-service python main.py sync

# Check last sync time
docker exec -i postgres psql -U trading_user -d trading_db -c "
SELECT * FROM trading.sync_status
WHERE sync_type = 'hourly'
ORDER BY sync_completed_at DESC
LIMIT 5;"
```

### Issue: Duplicate Trades

```bash
# Check for duplicates
docker exec -i postgres psql -U trading_user -d trading_db -c "
SELECT trade_id, COUNT(*)
FROM trading.completed_trades
GROUP BY trade_id
HAVING COUNT(*) > 1;"
```

Note: Duplicates should be impossible due to `UNIQUE(trade_id)` constraint.

### Issue: Rate Limiting

If you see `429 Too Many Requests` errors:

1. Edit `config.py`:
   ```python
   RATE_LIMIT_DELAY = 0.15  # Increase from 0.12 to 0.15
   ```

2. Restart service:
   ```bash
   docker-compose restart trade-sync-service
   ```

## Manual Operations

### Backfill Specific Date Range

```bash
# Use Python script for custom range
docker-compose run --rm trade-sync-service python -c "
from sync_service import TradeSyncService
from datetime import datetime, timezone
import asyncio

service = TradeSyncService()
start = datetime(2025, 8, 1, tzinfo=timezone.utc)
end = datetime(2025, 8, 31, tzinfo=timezone.utc)

asyncio.run(service.sync_time_range('shortseller_001', start, end, 'manual'))
"
```

### Resync Specific Day

```bash
# Delete trades for specific day
docker exec -i postgres psql -U trading_user -d trading_db -c "
DELETE FROM trading.completed_trades
WHERE bot_id = 'shortseller_001'
  AND DATE(exit_time) = '2025-10-15';"

# Resync that day
docker-compose run --rm trade-sync-service python -c "
from sync_service import TradeSyncService
from datetime import datetime, timezone
import asyncio

service = TradeSyncService()
start = datetime(2025, 10, 15, tzinfo=timezone.utc)
end = datetime(2025, 10, 16, tzinfo=timezone.utc)

asyncio.run(service.sync_time_range('shortseller_001', start, end, 'manual'))
"
```

### Export Trades to CSV

```bash
# Export all completed trades
docker exec -i postgres psql -U trading_user -d trading_db -c "
COPY (
    SELECT * FROM trading.completed_trades
    ORDER BY exit_time DESC
) TO STDOUT WITH CSV HEADER;" > completed_trades_export.csv
```

## Updating the Service

```bash
# Pull latest code
cd /root/projects/Alpha
git pull

# Rebuild and restart
cd trade_sync_service
docker-compose build
docker-compose down
docker-compose up -d

# Verify
docker-compose logs -f trade-sync-service
```

## Backup and Recovery

### Backup Completed Trades

```bash
# Backup completed_trades table
docker exec postgres pg_dump -U trading_user -d trading_db \
    -t trading.completed_trades \
    -t trading.sync_status \
    > trade_sync_backup_$(date +%Y%m%d).sql
```

### Restore from Backup

```bash
# Restore from backup
docker exec -i postgres psql -U trading_user -d trading_db < trade_sync_backup_20251101.sql
```

## Performance Tuning

### Increase Backfill Speed

Edit `config.py`:

```python
BACKFILL_BATCH_DAYS = 7  # Process in 7-day chunks instead of 1-day
RATE_LIMIT_DELAY = 0.10  # Slightly faster (but watch for 429 errors)
```

### Reduce Sync Interval

Edit `config.py`:

```python
SYNC_INTERVAL_SECONDS = 1800  # 30 minutes instead of 1 hour
```

### Database Optimization

```sql
-- Vacuum and analyze
VACUUM ANALYZE trading.completed_trades;
VACUUM ANALYZE trading.sync_status;

-- Rebuild indexes
REINDEX TABLE trading.completed_trades;
```

## Security Considerations

1. **Protect API credentials**: Never commit `.env` file
2. **Use read-only API keys** if possible (Bybit allows read-only keys)
3. **Restrict database user**: Grant only required permissions
4. **Network isolation**: Use Docker networks to isolate services
5. **Log rotation**: Prevent logs from filling disk space

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f trade-sync-service`
2. Run diagnostics: `python main.py test` and `python main.py stats`
3. Review sync_status table for error messages
4. Contact development team with error details
