# Production Configuration for Telegram Command Center

## Overview

The Telegram Command Center has been updated to work with **docker-compose.production.yml** infrastructure. This document explains the production-specific configuration.

---

## Production Infrastructure

### Container Names

| Component | Container Name | Purpose | Port |
|-----------|---------------|---------|------|
| **PostgreSQL** | `trading_postgres` | Primary database | 5433 → 5432 |
| **PgBouncer** | `trading_pgbouncer` | Connection pooler | 6432 |
| **Redis** | `trading_redis` | Live state cache | 6379 |
| **WebSocket** | `trading_websocket_listener` | Bybit stream handler | - |
| **Shortseller** | `shortseller_trading` | Alpha trading bot | - |
| **LXAlgo** | `lxalgo_trading` | Bravo trading bot | - |
| **Momentum** | `momentum_trading` | Charlie trading bot | - |
| **Command Center** | `telegram_c2` | Telegram bot | - |

### Database Architecture

```
Trading Bots (Alpha, Bravo, Charlie)
         │
         ├──> PgBouncer (port 6432) ──> PostgreSQL (trading_postgres)
         │
         └──> Redis (trading_redis)
                  ↑
                  │
         WebSocket Listener
         (Bybit streams → fills/positions)
```

### Key Differences from Development

| Feature | Development | Production |
|---------|-------------|------------|
| **PostgreSQL Container** | `shortseller_postgres` | `trading_postgres` |
| **Database Name** | `multiasset_trading` | `trading_db` |
| **Redis Container** | `shortseller_redis` | `trading_redis` |
| **Connection Pooling** | None | PgBouncer on port 6432 |
| **WebSocket Listener** | Not present | `trading_websocket_listener` |
| **Postgres Port** | 5433 | 5433 (external), 5432 (internal) |

---

## Environment Configuration

### Required Variables

In `/home/william/STRATEGIES/Alpha/.env`:

```bash
# Database Credentials
POSTGRES_PASSWORD=your_secure_password_here
REDIS_PASSWORD=your_secure_password_here

# Telegram Command Center
C2_TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
C2_TELEGRAM_ADMIN_IDS=your_telegram_user_id

# Bybit API (for bots)
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_DEMO=true
BYBIT_TESTNET=false

# Individual bot API keys (optional, override above)
SHORTSELLER_BYBIT_API_KEY=...
LXALGO_BYBIT_API_KEY=...
MOMENTUM_BYBIT_API_KEY=...
```

### Automatic Environment Injection

The `docker-compose.production.yml` automatically sets these for telegram_manager:

```yaml
environment:
  # Database - Uses PgBouncer for connection pooling
  - POSTGRES_HOST=pgbouncer
  - POSTGRES_PORT=6432
  - POSTGRES_DB=trading_db
  - POSTGRES_USER=trading_user
  - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

  # Redis
  - REDIS_HOST=redis
  - REDIS_PORT=6379
  - REDIS_PASSWORD=${REDIS_PASSWORD}

  # Telegram
  - TELEGRAM_BOT_TOKEN=${C2_TELEGRAM_BOT_TOKEN}
  - TELEGRAM_ADMIN_IDS=${C2_TELEGRAM_ADMIN_IDS}
```

---

## Updated Analytics Configuration

### db_analytics.py Defaults

The analytics module now uses production defaults:

```python
# PostgreSQL via PgBouncer
POSTGRES_HOST=pgbouncer     # Connection pooler
POSTGRES_PORT=6432          # PgBouncer port
POSTGRES_DB=trading_db      # Production database name

# Redis
REDIS_HOST=redis            # Production Redis container
REDIS_PORT=6379
```

### Bot ID Mapping

Analytics commands map to production bot IDs:

```python
'alpha' → 'shortseller_001'
'bravo' → 'lxalgo_001'
'charlie' → 'momentum_001'
```

---

## System Identifiers

The command center recognizes these systems:

### Trading Systems

| ID | Container | Name | Bot ID |
|----|-----------|------|--------|
| `alpha` | `shortseller_trading` | ALPHA SYSTEM | shortseller_001 |
| `bravo` | `lxalgo_trading` | BRAVO SYSTEM | lxalgo_001 |
| `charlie` | `momentum_trading` | CHARLIE SYSTEM | momentum_001 |

### Infrastructure Systems

| ID | Container | Name | Purpose |
|----|-----------|------|---------|
| `database` | `trading_postgres` | DATABASE CORE | PostgreSQL 15 |
| `pgbouncer` | `trading_pgbouncer` | PGBOUNCER | Connection Pooler |
| `cache` | `trading_redis` | CACHE CORE | Redis 7 |
| `websocket` | `trading_websocket_listener` | WEBSOCKET LISTENER | Bybit Streams |

---

## Deployment

### Quick Deployment

```bash
cd /home/william/STRATEGIES/Alpha
./deploy_analytics_production.sh
```

### Manual Deployment

```bash
# 1. Verify .env is configured
cat .env | grep -E "(POSTGRES_PASSWORD|REDIS_PASSWORD|C2_TELEGRAM)"

# 2. Stop current telegram manager
docker-compose -f docker-compose.production.yml stop telegram_manager

# 3. Rebuild with analytics
docker-compose -f docker-compose.production.yml build telegram_manager

# 4. Start
docker-compose -f docker-compose.production.yml up -d telegram_manager

# 5. Verify
docker-compose -f docker-compose.production.yml logs telegram_manager | grep "Analytics"
```

### Verify All Systems

```bash
# Check all production containers
docker-compose -f docker-compose.production.yml ps

# Should show:
# - trading_postgres (healthy)
# - trading_pgbouncer (running)
# - trading_redis (healthy)
# - trading_websocket_listener (running)
# - shortseller_trading (running)
# - lxalgo_trading (running)
# - momentum_trading (running)
# - telegram_c2 (running)
```

---

## Testing

### 1. Basic Connectivity

```bash
# From telegram container, test connections
docker exec telegram_c2 ping -c 1 pgbouncer
docker exec telegram_c2 ping -c 1 postgres
docker exec telegram_c2 ping -c 1 redis
```

### 2. Database Connectivity

```bash
# Test PostgreSQL via PgBouncer
docker exec telegram_c2 python3 -c "
import psycopg2
conn = psycopg2.connect(
    host='pgbouncer',
    port=6432,
    database='trading_db',
    user='trading_user',
    password='your_password'
)
print('PostgreSQL OK')
conn.close()
"

# Test Redis
docker exec telegram_c2 python3 -c "
import redis
r = redis.Redis(
    host='redis',
    port=6379,
    password='your_password',
    decode_responses=True
)
r.ping()
print('Redis OK')
"
```

### 3. Telegram Commands

In Telegram:

```
/help          # Should show analytics commands
/quick         # Quick status
/sitrep        # Full system status (should show all 7 systems)
/analytics     # Trading analytics
/positions     # Active positions
/cache         # Redis stats
```

### 4. System Control

```
/deploy database      # Should control trading_postgres
/deploy pgbouncer     # Should control trading_pgbouncer
/deploy cache         # Should control trading_redis
/deploy websocket     # Should control trading_websocket_listener
```

---

## Troubleshooting

### Analytics Not Available

**Symptom**: "Analytics features are currently unavailable"

**Check**:
```bash
# 1. Verify dependencies installed
docker exec telegram_c2 python -c "import psycopg2, redis; print('OK')"

# 2. Check environment variables
docker exec telegram_c2 printenv | grep -E "(POSTGRES|REDIS)"

# 3. View logs
docker-compose -f docker-compose.production.yml logs telegram_manager | grep -i analytics
```

**Expected Environment**:
```
POSTGRES_HOST=pgbouncer
POSTGRES_PORT=6432
POSTGRES_DB=trading_db
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=********
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=********
```

### Empty Analytics Results

**Symptom**: Commands return "No data" or empty results

**Check**:
```bash
# 1. Verify database has data
docker exec trading_postgres psql -U trading_user -d trading_db -c "
SELECT COUNT(*) FROM trading.bots;
SELECT COUNT(*) FROM trading.trades;
SELECT COUNT(*) FROM trading.positions;
"

# 2. Check WebSocket listener is running
docker ps | grep trading_websocket_listener

# 3. Verify bot IDs are registered
docker exec trading_postgres psql -U trading_user -d trading_db -c "
SELECT bot_id, bot_name, status FROM trading.bots;
"
```

**Expected Output**:
- At least 3 bots registered (shortseller_001, lxalgo_001, momentum_001)
- Some trades in trading.trades table
- WebSocket listener container running

### Connection Timeouts

**Symptom**: Slow responses or "Connection timeout" errors

**Check**:
```bash
# 1. PgBouncer health
docker exec trading_pgbouncer pgbouncer -V

# 2. PostgreSQL connections
docker exec trading_postgres psql -U trading_user -d trading_db -c "
SELECT count(*) FROM pg_stat_activity;
"

# 3. Check pgbouncer pool
docker logs trading_pgbouncer | tail -20
```

**Fix**:
- Increase PgBouncer pool size if needed
- Check PostgreSQL max_connections
- Verify query performance with EXPLAIN

### Container Name Mismatches

**Symptom**: "System not found" errors in Telegram

**Verify Container Names**:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

**Should Match**:
- `shortseller_trading` ✓
- `lxalgo_trading` ✓
- `momentum_trading` ✓
- `trading_postgres` ✓
- `trading_pgbouncer` ✓
- `trading_redis` ✓
- `trading_websocket_listener` ✓
- `telegram_c2` ✓

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────┐
│             Docker Network: trading-network             │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   telegram   │  │ shortseller  │  │    lxalgo    │ │
│  │     _c2      │  │   _trading   │  │   _trading   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                  │          │
│         │    ┌──────────────┐                │          │
│         │    │   momentum   │                │          │
│         │    │   _trading   │                │          │
│         │    └──────┬───────┘                │          │
│         │           │                        │          │
│         ▼           ▼                        ▼          │
│  ┌──────────────────────────────────────────────────┐  │
│  │              trading_pgbouncer                   │  │
│  │          (Connection Pool - Port 6432)           │  │
│  └────────────────────┬─────────────────────────────┘  │
│                       │                                 │
│                       ▼                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │             trading_postgres                      │  │
│  │          (PostgreSQL 15 - Port 5432)              │  │
│  │          Database: trading_db                     │  │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │             trading_redis                         │  │
│  │          (Redis 7 - Port 6379)                    │  │
│  │          Live positions & cache                   │  │
│  └───────────────────────────────────────────────────┘ │
│                       ▲                                 │
│                       │                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │       trading_websocket_listener                  │  │
│  │       (Bybit WebSocket Streams)                   │  │
│  │       Execution, Order, Position                  │  │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │
         │ External Ports
         ▼
    5433 → PostgreSQL
    6432 → PgBouncer
    6379 → Redis
```

---

## Production Best Practices

### 1. Use PgBouncer for Queries

Always connect through PgBouncer (port 6432) instead of direct PostgreSQL:

```bash
# Good (via PgBouncer)
POSTGRES_HOST=pgbouncer
POSTGRES_PORT=6432

# Less optimal (direct)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

**Benefits**:
- Connection pooling reduces overhead
- Handles connection limits better
- Faster query execution
- Better resource management

### 2. Monitor Connection Pools

```bash
# Check PgBouncer stats
docker exec telegram_c2 psql -h pgbouncer -p 6432 -U trading_user -d pgbouncer -c "SHOW STATS;"

# Check active connections
docker exec telegram_c2 psql -h pgbouncer -p 6432 -U trading_user -d pgbouncer -c "SHOW POOLS;"
```

### 3. Regular Health Checks

Add to cron or monitoring:

```bash
#!/bin/bash
# Check all production containers
docker-compose -f docker-compose.production.yml ps | grep -v "Up" && echo "Container down!" || echo "All OK"
```

### 4. Log Monitoring

```bash
# Follow all logs
docker-compose -f docker-compose.production.yml logs -f

# Specific service
docker-compose -f docker-compose.production.yml logs -f telegram_manager

# Check for errors
docker-compose -f docker-compose.production.yml logs | grep -i error | tail -20
```

---

## Migration Checklist

If migrating from development to production setup:

- [ ] Update `.env` with production credentials
- [ ] Verify all container names match production
- [ ] Update POSTGRES_HOST to `pgbouncer`
- [ ] Update POSTGRES_PORT to `6432`
- [ ] Update POSTGRES_DB to `trading_db`
- [ ] Update REDIS_HOST to `redis`
- [ ] Run migration scripts if needed
- [ ] Test database connectivity
- [ ] Verify analytics commands work
- [ ] Test system control commands
- [ ] Check all infrastructure containers running
- [ ] Monitor logs for errors

---

## Quick Reference

### Start Production System

```bash
docker-compose -f docker-compose.production.yml up -d
```

### Deploy Analytics Update

```bash
./deploy_analytics_production.sh
```

### View System Status

```bash
docker-compose -f docker-compose.production.yml ps
```

### Check Telegram Logs

```bash
docker-compose -f docker-compose.production.yml logs -f telegram_manager
```

### Restart Telegram Only

```bash
docker-compose -f docker-compose.production.yml restart telegram_manager
```

### Full System Restart

```bash
docker-compose -f docker-compose.production.yml restart
```

---

## Support

For issues:
1. Check logs: `docker-compose -f docker-compose.production.yml logs telegram_manager`
2. Verify connectivity tests above
3. Review environment variables
4. Check container health status
5. Consult [ANALYTICS_INTEGRATION_GUIDE.md](ANALYTICS_INTEGRATION_GUIDE.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-25
**Production Ready**: ✅ YES
