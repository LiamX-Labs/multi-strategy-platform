# Alpha Trading System - Quick Start Guide

Get the Alpha trading system running in 5 minutes.

## Prerequisites

- Docker & Docker Compose installed
- Git with submodule support
- Bybit account with API keys

## Installation

### 1. Clone Repository

```bash
# Clone with all strategy submodules
git clone --recurse-submodules https://github.com/LiamX-Labs/Alpha.git
cd Alpha
```

If you already cloned without submodules:
```bash
git submodule update --init --recursive
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
nano .env  # or vim, code, etc.
```

**Minimum required configuration**:

```bash
# Database
POSTGRES_PASSWORD=your_secure_postgres_password
REDIS_PASSWORD=your_secure_redis_password

# Bybit Mode
BYBIT_DEMO=true          # Use demo account
BYBIT_TESTNET=false      # Don't use testnet

# Bybit API Keys (get from bybit.com)
SHORTSELLER_BYBIT_API_KEY=your_shortseller_api_key
SHORTSELLER_BYBIT_API_SECRET=your_shortseller_secret

LXALGO_BYBIT_API_KEY=your_lxalgo_api_key
LXALGO_BYBIT_API_SECRET=your_lxalgo_secret

MOMENTUM_BYBIT_API_KEY=your_momentum_api_key
MOMENTUM_BYBIT_API_SECRET=your_momentum_secret

# Telegram (optional but recommended)
C2_TELEGRAM_BOT_TOKEN=your_telegram_bot_token
C2_TELEGRAM_ADMIN_IDS=your_telegram_user_id
```

### 3. Start All Services

```bash
# Start everything
docker compose -f docker-compose.production.yml up -d

# Check status
docker compose -f docker-compose.production.yml ps
```

Expected output:
```
NAME                          STATUS          PORTS
trading_postgres              Up (healthy)    0.0.0.0:5433->5432/tcp
trading_redis                 Up (healthy)    0.0.0.0:6379->6379/tcp
trading_pgbouncer             Up              0.0.0.0:6432->6432/tcp
trading_websocket_listener    Up (healthy)
shortseller_trading           Up (healthy)
lxalgo_trading                Up (healthy)
momentum_trading              Up (healthy)
telegram_c2                   Up
trade_sync_service            Up (healthy)
```

### 4. Verify Operation

```bash
# Check logs for any errors
docker compose -f docker-compose.production.yml logs --tail=50

# Check database connection
docker exec -it trading_postgres psql -U trading_user -d trading_db -c "SELECT * FROM trading.bots;"

# Check Redis connection
docker exec trading_redis redis-cli -a your_redis_password ping
```

## Running Individual Strategies

### Start Only One Strategy

```bash
# Start infrastructure + shortseller only
docker compose -f docker-compose.production.yml up -d postgres redis pgbouncer websocket_listener shortseller

# Start infrastructure + momentum only
docker compose -f docker-compose.production.yml up -d postgres redis pgbouncer websocket_listener momentum

# Start infrastructure + lxalgo only
docker compose -f docker-compose.production.yml up -d postgres redis pgbouncer websocket_listener lxalgo
```

### Stop a Strategy

```bash
# Stop shortseller but keep infrastructure running
docker compose -f docker-compose.production.yml stop shortseller

# Restart it
docker compose -f docker-compose.production.yml start shortseller
```

## Monitoring

### View Logs

```bash
# All logs
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f shortseller
docker compose -f docker-compose.production.yml logs -f websocket_listener

# Last 100 lines
docker compose -f docker-compose.production.yml logs --tail=100
```

### Check Service Health

```bash
# List all containers with health status
docker compose -f docker-compose.production.yml ps

# Inspect specific service
docker inspect trading_postgres --format='{{.State.Health.Status}}'
```

### Database Queries

```bash
# Connect to database
docker exec -it trading_postgres psql -U trading_user -d trading_db

# Quick queries
docker exec -it trading_postgres psql -U trading_user -d trading_db -c "
  SELECT bot_id, COUNT(*) as fills
  FROM trading.fills
  GROUP BY bot_id;
"
```

### Redis Inspection

```bash
# Connect to Redis
docker exec -it trading_redis redis-cli -a your_redis_password

# Check keys
docker exec trading_redis redis-cli -a your_redis_password KEYS 'position:*'

# Get position data
docker exec trading_redis redis-cli -a your_redis_password GET 'position:shortseller_001:BTCUSDT'
```

## Common Operations

### Update a Strategy

```bash
# Go to strategy directory
cd strategies/momentum

# Pull latest changes
git pull origin main

# Return to Alpha root
cd ../..

# Rebuild and restart
docker compose -f docker-compose.production.yml up -d --build momentum

# Commit the submodule update
git add strategies/momentum
git commit -m "Update momentum strategy"
git push
```

### Restart All Services

```bash
# Restart everything
docker compose -f docker-compose.production.yml restart

# Restart specific service
docker compose -f docker-compose.production.yml restart shortseller
```

### View Resource Usage

```bash
# Container resource usage
docker stats

# Disk usage
docker system df
```

### Backup Database

```bash
# Manual backup
docker exec trading_postgres pg_dump -U trading_user trading_db | gzip > backup_$(date +%Y%m%d).sql.gz

# View automated backups
ls -lh database/backups/postgres/daily/
```

### Restore Database

```bash
# Restore from backup
gunzip -c backup_20250101.sql.gz | docker exec -i trading_postgres psql -U trading_user -d trading_db
```

## Telegram Control (Optional)

If you configured Telegram:

1. **Start your Telegram bot** (use BotFather to create one)
2. **Find your Telegram user ID** (use @userinfobot)
3. **Set in .env**: `C2_TELEGRAM_ADMIN_IDS=your_user_id`
4. **Restart Telegram service**:
   ```bash
   docker compose -f docker-compose.production.yml restart telegram_manager
   ```

### Available Commands

- `/status` - Show status of all bots
- `/analytics` - Performance metrics
- `/start <bot_id>` - Start a bot
- `/stop <bot_id>` - Stop a bot

## Troubleshooting

### Containers Won't Start

```bash
# Check for errors
docker compose -f docker-compose.production.yml logs

# Check Docker resources
docker system df
df -h

# Clean up if needed
docker system prune -a
```

### Database Connection Errors

```bash
# Check PostgreSQL is healthy
docker compose -f docker-compose.production.yml ps postgres

# Check logs
docker compose -f docker-compose.production.yml logs postgres

# Verify password
echo $POSTGRES_PASSWORD

# Test connection
docker exec -it trading_postgres psql -U trading_user -d trading_db -c "SELECT version();"
```

### Strategy Can't Connect

Common issues:
1. **Wrong host**: Use `postgres` not `localhost`
2. **Wrong port**: Use `6432` (PgBouncer) not `5432`
3. **Password mismatch**: Check `.env` file
4. **Network issue**: Verify `trading-network` exists

```bash
# Check network
docker network inspect alpha_trading-network

# Restart with network recreation
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

### WebSocket Not Receiving Data

```bash
# Check WebSocket logs
docker compose -f docker-compose.production.yml logs websocket_listener

# Verify Bybit credentials
echo $SHORTSELLER_BYBIT_API_KEY

# Check BYBIT_DEMO setting
docker compose -f docker-compose.production.yml config | grep BYBIT_DEMO
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Reduce strategy memory limits in docker-compose.production.yml
# Or increase host memory
```

## Stopping the System

### Stop All Services

```bash
# Stop but keep data
docker compose -f docker-compose.production.yml stop

# Stop and remove containers (keeps data in volumes)
docker compose -f docker-compose.production.yml down

# Stop and remove everything including volumes (⚠️ DELETES ALL DATA)
docker compose -f docker-compose.production.yml down -v
```

### Stop Individual Strategy

```bash
# Stop but keep running
docker compose -f docker-compose.production.yml stop shortseller

# Stop and remove container
docker compose -f docker-compose.production.yml rm -sf shortseller
```

## Performance Tuning

### Optimize PostgreSQL

Edit `docker-compose.production.yml`:

```yaml
postgres:
  environment:
    POSTGRES_SHARED_BUFFERS: "256MB"
    POSTGRES_EFFECTIVE_CACHE_SIZE: "1GB"
    POSTGRES_MAX_CONNECTIONS: "200"
```

### Optimize Redis

```yaml
redis:
  command: >
    redis-server
    --maxmemory 1gb
    --maxmemory-policy allkeys-lru
```

### Strategy Resources

Adjust memory limits per strategy:

```yaml
shortseller:
  mem_limit: 1g
  cpus: 2
```

## Development Mode

### Run with Live Code Reload

For lxalgo (already mounted as volume):
```bash
# Edit code locally
nano strategies/lxalgo/main.py

# Restart to apply
docker compose -f docker-compose.production.yml restart lxalgo
```

For other strategies, add volume mount:
```yaml
shortseller:
  volumes:
    - ./strategies/shortseller:/app  # Add this line
```

### Debug Mode

Add to strategy environment:
```yaml
shortseller:
  environment:
    - LOG_LEVEL=DEBUG
    - PYTHONUNBUFFERED=1
```

## Next Steps

- 📖 Read [INTEGRATION.md](INTEGRATION.md) for architecture details
- 📊 Read [ARCHITECTURE.md](ARCHITECTURE.md) for technical deep dive
- 📝 Check [README.md](README.md) for overview
- 🗂️ Explore [docs/](docs/) for detailed documentation

## Support

- **Issues**: https://github.com/LiamX-Labs/Alpha/issues
- **Strategies**:
  - ShortSeller: https://github.com/LiamX-Labs/shortseller
  - LXAlgo: https://github.com/LiamX-Labs/lxalgo
  - Momentum: https://github.com/LiamX-Labs/apex-momentum-trading

## Cheat Sheet

```bash
# Start everything
docker compose -f docker-compose.production.yml up -d

# Stop everything
docker compose -f docker-compose.production.yml down

# Restart a service
docker compose -f docker-compose.production.yml restart <service>

# View logs
docker compose -f docker-compose.production.yml logs -f <service>

# Check status
docker compose -f docker-compose.production.yml ps

# Update and rebuild
cd strategies/<strategy> && git pull && cd ../..
docker compose -f docker-compose.production.yml up -d --build <service>

# Database backup
docker exec trading_postgres pg_dump -U trading_user trading_db > backup.sql

# Clean up
docker system prune -a
```
