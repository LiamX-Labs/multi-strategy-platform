# Alpha Trading System - Integration Architecture

This document describes how all components of the Alpha trading system work together.

## System Overview

Alpha is a unified trading infrastructure that supports multiple trading strategies through a shared services architecture.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALPHA TRADING SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ ShortSeller │  │   LXAlgo    │  │  Momentum   │            │
│  │  Strategy   │  │  Strategy   │  │  Strategy   │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                 │                 │                    │
│         └─────────────────┴─────────────────┘                   │
│                           │                                      │
│         ┌─────────────────┴─────────────────┐                   │
│         │                                     │                   │
│         ▼                                     ▼                   │
│  ┌──────────────┐                   ┌──────────────┐           │
│  │   Redis      │                   │  PostgreSQL  │           │
│  │ (Live State) │                   │  (History)   │           │
│  └──────────────┘                   └──────────────┘           │
│         ▲                                     ▲                   │
│         │                                     │                   │
│         └─────────────────┬─────────────────┘                   │
│                           │                                      │
│                  ┌────────┴────────┐                            │
│                  │   WebSocket     │                            │
│                  │    Listener     │                            │
│                  └─────────────────┘                            │
│                           │                                      │
│                           ▼                                      │
│                  ┌─────────────────┐                            │
│                  │  Bybit Exchange │                            │
│                  └─────────────────┘                            │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Support Services                            │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │  • Telegram C2 (Command & Control)                      │   │
│  │  • Trade Sync Service (Historical backfill)             │   │
│  │  • PgBouncer (Connection pooling)                       │   │
│  │  • Postgres Backup (Automated backups)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Shared Infrastructure Services

#### PostgreSQL Database
- **Purpose**: Permanent storage for all fills, trades, and performance history
- **Schema**: `trading` schema with tables for bots, fills, completed_trades
- **Access**: Direct connection for writes, PgBouncer for reads
- **Port**: 5433 (external), 5432 (internal)

#### Redis
- **Purpose**: Real-time position state and live data caching
- **Data**: Current positions, orders, market data snapshots
- **Per-Bot DBs**:
  - DB 0: ShortSeller
  - DB 1: LXAlgo
  - DB 2: Momentum
- **Port**: 6379

#### PgBouncer
- **Purpose**: Connection pooling for PostgreSQL
- **Pool Mode**: Transaction
- **Max Connections**: 1000 clients, 25 pool size
- **Port**: 6432

#### WebSocket Listener
- **Purpose**: Central Bybit WebSocket connection manager
- **Streams**:
  - Execution (fills)
  - Order (order status)
  - Position (position updates)
- **Actions**:
  - Writes fills to PostgreSQL
  - Updates live state in Redis
  - Broadcasts to all bots

### 2. Trading Strategies (Git Submodules)

Each strategy is a separate repository integrated as a git submodule.

#### ShortSeller
- **Location**: [strategies/shortseller](strategies/shortseller)
- **GitHub**: https://github.com/LiamX-Labs/shortseller
- **Strategy**: Multi-Asset EMA crossover shorts (BTC, ETH, SOL)
- **Bot ID**: `shortseller_001`
- **Redis DB**: 0
- **Entry Point**: `scripts/start_trading.py`

#### LXAlgo
- **Location**: [strategies/lxalgo](strategies/lxalgo)
- **GitHub**: https://github.com/LiamX-Labs/lxalgo
- **Strategy**: LX technical analysis multi-indicator system
- **Bot ID**: `lxalgo_001`
- **Redis DB**: 1
- **Entry Point**: `main.py`

#### Momentum
- **Location**: [strategies/momentum](strategies/momentum)
- **GitHub**: https://github.com/LiamX-Labs/apex-momentum-trading
- **Strategy**: 4H volatility breakout momentum (252% backtest)
- **Bot ID**: `momentum_001`
- **Redis DB**: 2
- **Entry Point**: `trading_system.py`

### 3. Support Services

#### Telegram Command Center
- **Purpose**: Monitor and control all bots via Telegram
- **Commands**: `/analytics`, `/status`, `/start`, `/stop`
- **Access**: Docker socket for bot control
- **Database**: Direct PostgreSQL connection for analytics

#### Trade Sync Service
- **Purpose**: Backfill historical trades from Bybit API
- **Schedule**: Runs continuously with hourly sync
- **Per-Bot API Keys**: Configured in `.env` file
- **Use Case**: Historical P&L reconstruction

#### Postgres Backup
- **Schedule**: Daily at 2 AM
- **Retention**: 30 days, 12 weeks, 12 months
- **Location**: `./database/backups/postgres/`

## Data Flow

### Trade Execution Flow

```
1. Strategy generates signal
   ↓
2. Strategy places order via Bybit REST API
   ↓
3. Bybit executes order
   ↓
4. WebSocket Listener receives execution event
   ↓
5. WebSocket writes to:
   • PostgreSQL (trading.fills) - permanent record
   • Redis (live state) - current position
   ↓
6. Strategy reads updated position from Redis
   ↓
7. Strategy makes next decision
```

### Database Access Patterns

**Writes (Critical Path)**:
- Only WebSocket Listener writes to fills table
- Ensures single source of truth for execution data

**Reads**:
- Strategies: Read from Redis (live state)
- Strategies: Can query PostgreSQL via PgBouncer (historical)
- Telegram Bot: Queries PostgreSQL for analytics
- Trade Sync: Writes to completed_trades table

## Configuration

### Environment Variables

Each strategy requires its own API keys:

```bash
# PostgreSQL
POSTGRES_PASSWORD=your_secure_password

# Redis
REDIS_PASSWORD=your_secure_redis_password

# Bybit Configuration
BYBIT_DEMO=true                    # Use demo/testnet
BYBIT_TESTNET=false

# Per-Bot Bybit API Keys
SHORTSELLER_BYBIT_API_KEY=...
SHORTSELLER_BYBIT_API_SECRET=...
LXALGO_BYBIT_API_KEY=...
LXALGO_BYBIT_API_SECRET=...
MOMENTUM_BYBIT_API_KEY=...
MOMENTUM_BYBIT_API_SECRET=...

# Telegram (per strategy)
SHORTSELLER_TELEGRAM_BOT_TOKEN=...
SHORTSELLER_TELEGRAM_CHANNEL_ID=...

# Telegram C2
C2_TELEGRAM_BOT_TOKEN=...
C2_TELEGRAM_ADMIN_IDS=123456789
```

### Network Architecture

All services run on a shared Docker bridge network: `trading-network`

**Internal DNS Resolution**:
- Services reference each other by container name
- Example: `POSTGRES_HOST=postgres` (not `localhost`)

**Service Dependencies**:
```
PostgreSQL (first)
  ↓
PgBouncer, Redis
  ↓
WebSocket Listener
  ↓
Trading Strategies
```

Health checks ensure services start in correct order.

## Deployment

### Initial Setup

1. **Clone with submodules**:
```bash
git clone --recurse-submodules https://github.com/LiamX-Labs/Alpha.git
cd Alpha
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Start all services**:
```bash
docker compose -f docker-compose.production.yml up -d
```

4. **Verify health**:
```bash
docker compose -f docker-compose.production.yml ps
```

### Starting Individual Strategies

```bash
# Start only shortseller
docker compose -f docker-compose.production.yml up -d shortseller

# Start only momentum
docker compose -f docker-compose.production.yml up -d momentum

# Start only lxalgo
docker compose -f docker-compose.production.yml up -d lxalgo
```

### Updating Strategies

Since strategies are git submodules, update them independently:

```bash
# Update shortseller to latest
cd strategies/shortseller
git pull origin main
cd ../..

# Rebuild and restart
docker compose -f docker-compose.production.yml up -d --build shortseller

# Commit the submodule update in Alpha repo
git add strategies/shortseller
git commit -m "Update shortseller to latest"
git push
```

## Database Schema

### Key Tables

#### `trading.bots`
Registry of all trading bots with their configuration and status.

#### `trading.fills`
**Most Important Table** - Every execution from Bybit WebSocket.
- Contains exact execution price, quantity, and commission
- Single source of truth for P&L calculation
- Indexed for fast bot/symbol/time queries

#### `trading.completed_trades`
Historical trades synced from Bybit API.
- Used for backtesting and historical analysis
- Populated by Trade Sync Service

### Performance Views

The system includes pre-built views for performance analytics:
- `bot_daily_performance`
- `position_summaries`
- `exit_reason_analysis`

See [database/migrations](database/migrations/) for complete schema.

## Monitoring & Operations

### Health Checks

All services include health checks:
- **PostgreSQL**: `pg_isready` check every 10s
- **Redis**: Connection ping every 10s
- **Strategies**: Process checks every 60s

### Logs

Logs are centralized with rotation:
```bash
# View specific service logs
docker compose -f docker-compose.production.yml logs -f shortseller
docker compose -f docker-compose.production.yml logs -f websocket_listener

# All logs
docker compose -f docker-compose.production.yml logs -f
```

Log files are also mounted locally:
- `./strategies/shortseller/logs/`
- `./strategies/lxalgo/logs/`
- `./strategies/momentum/logs/`
- `./websocket_listener/logs/`
- `./telegram_manager/logs/`
- `./trade_sync_service/logs/`

### Backups

Automated PostgreSQL backups run daily:
- Location: `./database/backups/postgres/`
- Retention: 30 days / 12 weeks / 12 months
- Restore: See [database/README.md](database/README.md)

### Telegram Command Center

Monitor all bots in real-time:
```
/status - Show all bot status
/analytics - Performance metrics
/start <bot_id> - Start specific bot
/stop <bot_id> - Stop specific bot
```

## Integration Testing

Before deploying, test the integration:

```bash
# 1. Start infrastructure only
docker compose -f docker-compose.production.yml up -d postgres redis pgbouncer

# 2. Start websocket listener
docker compose -f docker-compose.production.yml up -d websocket_listener

# 3. Start one strategy for testing
docker compose -f docker-compose.production.yml up -d shortseller

# 4. Monitor logs
docker compose -f docker-compose.production.yml logs -f shortseller websocket_listener

# 5. Check database connectivity
docker exec -it trading_postgres psql -U trading_user -d trading_db -c "SELECT * FROM trading.bots;"
```

## Troubleshooting

### Strategy Can't Connect to Database
- Check `POSTGRES_HOST` is set to `pgbouncer` (not `postgres` or `localhost`)
- Verify `POSTGRES_PORT` is `6432` (PgBouncer), not `5432`
- Check network: `docker network inspect alpha_trading-network`

### WebSocket Listener Not Receiving Data
- Verify Bybit API credentials
- Check `BYBIT_DEMO=true` for demo account
- Review logs: `docker compose logs -f websocket_listener`

### Redis Connection Issues
- Verify `REDIS_PASSWORD` matches across all services
- Check Redis is healthy: `docker compose ps redis`
- Test connection: `docker exec trading_redis redis-cli -a <password> ping`

### Performance Issues
- Monitor PostgreSQL connections: Check PgBouncer stats
- Review Redis memory: `docker exec trading_redis redis-cli INFO memory`
- Check disk space: `df -h`

## Security Considerations

1. **API Keys**: Never commit to git (use `.env` file)
2. **Database Passwords**: Change defaults in production
3. **Docker Socket**: Telegram C2 has Docker access (secure with admin IDs)
4. **Network**: All services isolated in Docker network
5. **Ports**: Only essential ports exposed to host

## Next Steps

1. Add InfluxDB for high-frequency tick data (Phase 2)
2. Implement multi-timeframe analysis service
3. Add ML model serving for signal generation
4. Create unified backtesting framework

## References

- [Main README](README.md) - System overview
- [Database Documentation](docs/database/) - Schema details
- [Telegram C2 Guide](docs/telegram/) - Bot control
- [Docker Startup Guide](docs/guides/DOCKER_STARTUP_GUIDE.md) - Deployment
