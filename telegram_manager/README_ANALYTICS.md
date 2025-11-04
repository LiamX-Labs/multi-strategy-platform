# Telegram Analytics - Quick Reference

## Quick Start

### 1. Install Dependencies

```bash
cd /home/william/STRATEGIES/Alpha/telegram_manager
pip install psycopg2-binary redis
```

Or use Docker:

```bash
docker-compose build telegram_manager
```

### 2. Configure Environment

Edit `telegram_manager/.env`:

```bash
POSTGRES_HOST=shortseller_postgres
POSTGRES_PORT=5433
POSTGRES_DB=trading_db
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=your_password

REDIS_HOST=shortseller_redis
REDIS_PORT=6379
REDIS_PASSWORD=your_password
```

### 3. Restart

```bash
docker-compose restart telegram_manager
```

---

## Command Cheat Sheet

| Command | Purpose | Example |
|---------|---------|---------|
| `/quick` | Fast status overview | `/quick` |
| `/analytics [bot] [days]` | Full performance report | `/analytics alpha 7` |
| `/positions [bot]` | Active positions | `/positions bravo` |
| `/trades [bot] [limit]` | Recent trades | `/trades charlie 20` |
| `/daily [bot] [days]` | Daily breakdown | `/daily alpha 14` |
| `/cache` | Redis cache stats | `/cache` |

---

## Bot Identifiers

- `alpha` = Shortseller (shortseller_001)
- `bravo` = LXAlgo (lxalgo_001)
- `charlie` = Momentum (momentum_001)

---

## File Structure

```
telegram_manager/
├── bot.py                     # Main bot (updated with analytics)
├── db_analytics.py            # Database query module (NEW)
├── analytics_handlers.py      # Command handlers (NEW)
├── requirements.txt           # Add: psycopg2-binary, redis
└── .env                       # Database credentials
```

---

## Key Features

✅ **Read-Only**: No trading operations, summaries only
✅ **Secure**: Requires Telegram authorization
✅ **Real-Time**: Direct database queries
✅ **Multi-Bot**: Portfolio-wide or per-bot analytics
✅ **Flexible**: Customizable time periods

---

## Troubleshooting

### Analytics Not Working?

```bash
# Check if modules loaded
docker-compose logs telegram_manager | grep "Analytics"

# Should see: "✓ Analytics features enabled"
```

### Can't Connect to Database?

```bash
# Test PostgreSQL
docker exec telegram_c2 ping shortseller_postgres

# Test Redis
docker exec telegram_c2 ping shortseller_redis
```

### Dependencies Missing?

```bash
# Check if installed
docker exec telegram_c2 python -c "import psycopg2, redis; print('OK')"
```

---

## Full Documentation

See [docs/telegram/ANALYTICS_INTEGRATION_GUIDE.md](../docs/telegram/ANALYTICS_INTEGRATION_GUIDE.md) for complete documentation.

---

**Status**: ✅ Production Ready
