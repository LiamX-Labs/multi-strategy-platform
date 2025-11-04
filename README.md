# Alpha Trading System

Unified monorepo containing all trading infrastructure and strategies.

## Repository Structure

```
Alpha/
├── strategies/           # Trading strategy implementations
│   ├── lxalgo/          # LX Algo trading strategy
│   ├── momentum/        # Apex Momentum trading strategy
│   └── shortseller/     # Multi-asset short trading strategy
├── telegram_manager/    # Telegram C2 bot
├── trade_sync_service/  # Trade synchronization service
├── websocket_listener/  # Real-time market data service
├── database/            # Database schemas and migrations
└── docs/                # Documentation

```

## Services

- **PostgreSQL** - Trade database
- **Redis** - Caching and real-time data
- **PgBouncer** - Connection pooling
- **Trade Sync Service** - Syncs trades from Bybit API
- **Telegram C2** - Command and control bot
- **WebSocket Listener** - Real-time market data

## Quick Start

```bash
# Start all services
docker compose -f docker-compose.production.yml up -d

# Check status
docker compose -f docker-compose.production.yml ps

# View logs
docker compose -f docker-compose.production.yml logs -f trade_sync_service
```

## Trading Strategies

### 1. LX Algo ([strategies/lxalgo](strategies/lxalgo))
LX Algorithm trading implementation

### 2. Momentum ([strategies/momentum](strategies/momentum))
Production-ready momentum trading system with:
- Exchange-side trailing stops
- MA exits and multi-level risk management
- Backtest: +252% over 27 months

### 3. ShortSeller ([strategies/shortseller](strategies/shortseller))
Multi-Asset Short Trading System with:
- EMA crossover strategy for BTC, ETH, SOL
- Bybit integration
- Telegram notifications
- Systematic risk management

## Trade Sync Service

Syncs completed trades from Bybit using per-bot API keys.

### Backfill Historical Trades

```bash
docker exec trade_sync_service python main.py backfill --months 1
```

### Check Trade Counts

```bash
docker exec -i trading_postgres psql -U trading_user -d trading_db -c \
  "SELECT bot_id, COUNT(*) as trades FROM trading.completed_trades GROUP BY bot_id;"
```

## Telegram Bot

Use `/analytics` command to view trading statistics.

## Per-Bot API Configuration

Each bot uses its own Bybit API key configured in `.env`:

- `SHORTSELLER_BYBIT_API_KEY`
- `LXALGO_BYBIT_API_KEY`
- `MOMENTUM_BYBIT_API_KEY`

## Database

Access database:

```bash
docker exec -it trading_postgres psql -U trading_user -d trading_db
```

## Environment Variables

Copy `.env.example` to `.env` and configure your API keys.

## Development

Each strategy in the `strategies/` directory can be developed independently while sharing the common infrastructure services.
