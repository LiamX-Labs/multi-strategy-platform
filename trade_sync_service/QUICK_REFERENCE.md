# Trade Sync Service - Quick Reference

## Essential Commands

### Deployment

```bash
# 1. Run database migration
docker exec -i postgres psql -U trading_user -d trading_db < ../database/migrations/004_create_completed_trades_table.sql

# 2. Setup environment
cp .env.example .env && nano .env

# 3. Test connections
docker-compose run --rm trade-sync-service python main.py test

# 4. Initial 3-month backfill
docker-compose run --rm trade-sync-service python main.py backfill --months 3

# 5. Start service
docker-compose up -d
```

### Common Operations

```bash
# View logs
docker-compose logs -f trade-sync-service

# Run hourly sync manually
docker-compose run --rm trade-sync-service python main.py sync

# View statistics
docker-compose run --rm trade-sync-service python main.py stats

# Restart service
docker-compose restart trade-sync-service

# Stop service
docker-compose down
```

### Monitoring Queries

```sql
-- Completed trades count
SELECT bot_id, COUNT(*) FROM trading.completed_trades GROUP BY bot_id;

-- Recent syncs
SELECT * FROM trading.sync_status ORDER BY sync_started_at DESC LIMIT 5;

-- Exit reasons
SELECT exit_reason, COUNT(*), AVG(net_pnl)
FROM trading.completed_trades
WHERE bot_id = 'shortseller_001'
GROUP BY exit_reason;

-- Failed syncs
SELECT * FROM trading.sync_status WHERE status = 'failed';

-- Today's trades
SELECT COUNT(*) FROM trading.completed_trades
WHERE DATE(exit_time) = CURRENT_DATE;
```

## File Structure

```
trade_sync_service/
├── main.py                  # CLI: python main.py [command]
├── sync_service.py          # Core sync logic
├── bybit_client.py          # API client with rate limiting
├── trade_matcher.py         # Buy/sell FIFO matching
├── database.py              # PostgreSQL operations
├── config.py                # Configuration variables
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container image
├── docker-compose.yml       # Service orchestration
├── .env                     # Secrets (not in git)
├── .env.example             # Template
├── README.md                # Full documentation
├── DEPLOYMENT.md            # Deployment guide
└── logs/                    # Log files (created at runtime)
```

## Key Environment Variables

```bash
BYBIT_API_KEY=<your_api_key>
BYBIT_API_SECRET=<your_api_secret>
POSTGRES_PASSWORD=<db_password>
LOG_LEVEL=INFO
```

## Database Tables

### trading.completed_trades
- Stores all closed trades from Bybit
- Includes entry/exit reasons
- Pre-calculated PnL
- Updated hourly

### trading.sync_status
- Tracks sync job execution
- Status: 'running', 'completed', 'failed'
- Error logging for debugging

## Rate Limits

- Bybit API: 10 requests/second
- Service delay: 120ms between requests
- Backfill: 1-day batches with 1s delay
- Hourly sync: Last 2 hours of trades

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Service won't start | Check logs: `docker-compose logs` |
| No trades synced | Verify Bybit credentials and `orderLinkId` format |
| Rate limit errors | Increase `RATE_LIMIT_DELAY` in config.py |
| Duplicate trades | Should be prevented by UNIQUE constraint |
| Connection failed | Run `python main.py test` |

## Exit Reason Analysis

Your bots use `orderLinkId` format: `"bot_id:reason:timestamp"`

Common exit reasons:
- `take_profit` - TP hit
- `stop_loss` - SL hit
- `trailing_stop` - Trailing stop triggered
- `timeout` - Time-based exit
- `signal_reverse` - Opposite signal

Query example:
```sql
SELECT
    exit_reason,
    COUNT(*) as trades,
    COUNT(*) FILTER (WHERE net_pnl > 0) as wins,
    ROUND(AVG(net_pnl), 2) as avg_pnl
FROM trading.completed_trades
WHERE bot_id = 'shortseller_001'
  AND exit_time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY exit_reason
ORDER BY trades DESC;
```

## Performance

| Operation | Duration |
|-----------|----------|
| 3-month backfill | ~10-15 min/bot |
| Daily batch | ~1-2 seconds |
| Hourly sync | ~1-2 seconds |
| 100 trades | <1 second insert |

## Support

1. Check [README.md](README.md) for full documentation
2. Check [DEPLOYMENT.md](DEPLOYMENT.md) for deployment steps
3. Check logs: `docker-compose logs -f`
4. Run diagnostics: `python main.py test` and `python main.py stats`
5. Check sync_status table for error messages

## Quick Health Check

```bash
# 1. Is service running?
docker-compose ps

# 2. Recent logs OK?
docker-compose logs --tail 20 trade-sync-service

# 3. Trades increasing?
docker exec -i postgres psql -U trading_user -d trading_db -c \
  "SELECT COUNT(*) FROM trading.completed_trades;"

# 4. Recent sync successful?
docker exec -i postgres psql -U trading_user -d trading_db -c \
  "SELECT * FROM trading.sync_status ORDER BY sync_started_at DESC LIMIT 1;"
```

All good? ✅ Service is healthy!
