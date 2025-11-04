# DATABASE IMPLEMENTATION GUIDE
## Step-by-Step Implementation of Unified Database System

**Document Version:** 1.0
**Date:** 2025-10-24
**Estimated Implementation Time:** 2-3 weeks

---

## TABLE OF CONTENTS

1. [Prerequisites](#prerequisites)
2. [Phase 1: Database Infrastructure Setup](#phase-1-database-infrastructure-setup)
3. [Phase 2: Data Migration](#phase-2-data-migration)
4. [Phase 3: Application Updates](#phase-3-application-updates)
5. [Phase 4: Testing & Validation](#phase-4-testing--validation)
6. [Phase 5: Go-Live](#phase-5-go-live)
7. [Rollback Plan](#rollback-plan)
8. [Troubleshooting](#troubleshooting)

---

## PREREQUISITES

### Required Skills
- [ ] Basic PostgreSQL administration
- [ ] Docker and docker-compose proficiency
- [ ] Python programming (for bot updates)
- [ ] SQL query writing
- [ ] Linux command line

### Required Software
- [ ] Docker 20.10+
- [ ] Docker Compose 2.0+
- [ ] PostgreSQL client tools (psql)
- [ ] Redis CLI
- [ ] InfluxDB CLI
- [ ] Python 3.10+

### Required Access
- [ ] SSH access to production server
- [ ] Sudo/root privileges
- [ ] GitHub repository access (for version control)
- [ ] Backup storage access

### Pre-Implementation Checklist
- [ ] Review [DATABASE_ARCHITECTURE_CATALOGUE.md](DATABASE_ARCHITECTURE_CATALOGUE.md)
- [ ] Backup all existing databases
- [ ] Test migration scripts in staging
- [ ] Schedule maintenance window
- [ ] Notify stakeholders

---

## PHASE 1: DATABASE INFRASTRUCTURE SETUP

**Duration:** 2-3 days
**Goal:** Set up the unified database infrastructure

### Step 1.1: Create Directory Structure

```bash
cd /home/william/STRATEGIES/Alpha

# Create database directories
mkdir -p database/migrations
mkdir -p database/config
mkdir -p database/backups/postgres
mkdir -p database/backups/influxdb
mkdir -p database/grafana/dashboards
mkdir -p database/grafana/datasources

# Set permissions
chmod -R 755 database/
```

### Step 1.2: Create Environment File

Create `.env.database` with secure credentials:

```bash
# PostgreSQL
POSTGRES_PASSWORD=<generate_secure_password>

# Redis
REDIS_PASSWORD=<generate_secure_password>

# InfluxDB
INFLUX_USERNAME=admin
INFLUX_PASSWORD=<generate_secure_password>
INFLUX_ORG=trading_org
INFLUX_BUCKET=market_data
INFLUX_TOKEN=<generate_secure_token>

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=<generate_secure_password>
GRAFANA_ROOT_URL=http://your-server-ip:3000
```

**Security Note:** Generate strong passwords using:
```bash
openssl rand -base64 32
```

### Step 1.3: Create PostgreSQL Configuration

Create `database/config/postgresql.conf`:

```ini
# Connection Settings
max_connections = 100
shared_buffers = 256MB

# Query Tuning
work_mem = 4MB
maintenance_work_mem = 64MB
effective_cache_size = 1GB

# Write Ahead Log
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'mod'
log_duration = on
log_min_duration_statement = 1000  # Log queries > 1 second

# Performance
random_page_cost = 1.1
effective_io_concurrency = 200
```

### Step 1.4: Create Redis Configuration

Create `database/config/redis.conf`:

```conf
# Network
bind 0.0.0.0
port 6379
timeout 300
tcp-keepalive 60

# Persistence
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Memory Management
maxmemory 512mb
maxmemory-policy allkeys-lru
```

### Step 1.5: Start Database Services

```bash
# Load environment variables
source .env.database

# Start only databases first
docker-compose -f docker-compose.unified-db.yml up -d postgres redis influxdb

# Wait for services to be healthy
docker-compose -f docker-compose.unified-db.yml ps

# Check logs
docker-compose -f docker-compose.unified-db.yml logs postgres
docker-compose -f docker-compose.unified-db.yml logs redis
docker-compose -f docker-compose.unified-db.yml logs influxdb
```

### Step 1.6: Verify Database Connections

```bash
# Test PostgreSQL
docker exec -it trading_postgres psql -U trading_user -d trading_db -c "\dt trading.*"

# Test Redis
docker exec -it trading_redis redis-cli -a $REDIS_PASSWORD ping

# Test InfluxDB
docker exec -it trading_influxdb influx ping
```

✅ **Checkpoint:** All databases are running and accessible

---

## PHASE 2: DATA MIGRATION

**Duration:** 3-5 days
**Goal:** Migrate existing data to unified schema

### Step 2.1: Backup Existing Databases

```bash
# Backup Shortseller PostgreSQL
docker exec shortseller_postgres pg_dump -U trading_user multiasset_trading > \
    database/backups/shortseller_backup_$(date +%Y%m%d).sql

# Backup Momentum SQLite
cp momentum/data/trading.db database/backups/momentum_backup_$(date +%Y%m%d).db

# Verify backups
ls -lh database/backups/
```

### Step 2.2: Run Schema Migration

```bash
# Execute unified schema creation
docker exec -i trading_postgres psql -U trading_user -d trading_db < \
    database/migrations/001_unified_schema.sql

# Verify schema creation
docker exec trading_postgres psql -U trading_user -d trading_db -c "\dn"
docker exec trading_postgres psql -U trading_user -d trading_db -c "\dt trading.*"
```

Expected output:
```
Schema: trading (12 tables)
Schema: analytics (1 table + views)
Schema: config (1 table)
Schema: audit (2 tables)
```

### Step 2.3: Migrate Shortseller Data

```bash
# Run Shortseller migration
docker exec -i trading_postgres psql -U trading_user -d trading_db < \
    database/migrations/002_migrate_shortseller_data.sql

# Verify migration
docker exec trading_postgres psql -U trading_user -d trading_db -c \
    "SELECT COUNT(*) FROM trading.trades WHERE bot_id = 'shortseller_001';"
```

### Step 2.4: Migrate Momentum Data

```bash
# Install Python dependencies for migration script
pip install psycopg2-binary

# Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=trading_db
export POSTGRES_USER=trading_user
export POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# Run Python migration script
python database/migrations/migrate_momentum_sqlite_to_postgres.py

# Verify migration
docker exec trading_postgres psql -U trading_user -d trading_db -c \
    "SELECT COUNT(*) FROM trading.trades WHERE bot_id = 'momentum_001';"
```

### Step 2.5: Register LXAlgo Bot

```bash
# Register LXAlgo (no historical data to migrate)
docker exec -i trading_postgres psql -U trading_user -d trading_db < \
    database/migrations/004_register_lxalgo_bot.sql

# Verify registration
docker exec trading_postgres psql -U trading_user -d trading_db -c \
    "SELECT * FROM trading.bots WHERE bot_id = 'lxalgo_001';"
```

### Step 2.6: Verify All Migrations

```bash
# Create verification script
cat > verify_migration.sql <<'EOF'
-- Check all bots registered
SELECT bot_id, bot_name, status, current_equity
FROM trading.bots
ORDER BY bot_id;

-- Check trades per bot
SELECT
    bot_id,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE exit_time IS NOT NULL) as closed_trades,
    SUM(pnl_usd) FILTER (WHERE exit_time IS NOT NULL) as total_pnl
FROM trading.trades
GROUP BY bot_id;

-- Check system events
SELECT
    event_type,
    event_level,
    COUNT(*) as count
FROM audit.system_events
GROUP BY event_type, event_level
ORDER BY count DESC;
EOF

# Run verification
docker exec -i trading_postgres psql -U trading_user -d trading_db < verify_migration.sql
```

✅ **Checkpoint:** All data migrated successfully

---

## PHASE 3: APPLICATION UPDATES

**Duration:** 5-7 days
**Goal:** Update bot applications to use unified database

### Step 3.1: Update Shortseller Bot

#### 3.1.1: Add `bot_id` to All Queries

**File:** `shortseller/src/database/trade_logger.py`

```python
# Before
def log_trade(symbol, side, quantity, price):
    cursor.execute("""
        INSERT INTO trading.trades (symbol, side, quantity, price, ...)
        VALUES (%s, %s, %s, %s, ...)
    """, (symbol, side, quantity, price, ...))

# After
BOT_ID = os.getenv('BOT_ID', 'shortseller_001')

def log_trade(symbol, side, quantity, price):
    cursor.execute("""
        INSERT INTO trading.trades (trade_id, bot_id, symbol, side, quantity, entry_price, ...)
        VALUES (%s, %s, %s, %s, %s, %s, ...)
    """, (f"{BOT_ID}_{symbol}_{int(time.time())}", BOT_ID, symbol, side, quantity, price, ...))
```

#### 3.1.2: Update Connection Settings

**File:** `shortseller/config/settings.py`

```python
# Update database config to use PgBouncer
self.database = DatabaseConfig(
    host=os.getenv('POSTGRES_HOST', 'pgbouncer'),  # Changed from 'localhost'
    port=int(os.getenv('POSTGRES_PORT', '6432')),  # Changed from 5432
    database='trading_db',  # Changed from 'multiasset_trading'
    username='trading_user',
    password=os.getenv('POSTGRES_PASSWORD')
)
```

#### 3.1.3: Update All SELECT Queries

Add `WHERE bot_id = 'shortseller_001'` to all SELECT statements:

```python
# Get active positions
def get_active_positions():
    query = """
        SELECT * FROM trading.positions
        WHERE bot_id = %s AND status = 'open'
    """
    cursor.execute(query, (BOT_ID,))
    return cursor.fetchall()
```

### Step 3.2: Update Momentum Bot

#### 3.2.1: Replace SQLite with PostgreSQL

**File:** `momentum/database/trade_database.py`

```python
# Before (SQLite)
import sqlite3
conn = sqlite3.connect('data/trading.db')

# After (PostgreSQL)
import psycopg2
from psycopg2.extras import RealDictCursor

BOT_ID = os.getenv('BOT_ID', 'momentum_001')

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'pgbouncer'),
    port=int(os.getenv('POSTGRES_PORT', '6432')),
    database=os.getenv('POSTGRES_DB', 'trading_db'),
    user=os.getenv('POSTGRES_USER', 'trading_user'),
    password=os.getenv('POSTGRES_PASSWORD')
)
```

#### 3.2.2: Update Query Syntax

```python
# SQLite syntax
cursor.execute("SELECT * FROM trades WHERE exit_time IS NULL")

# PostgreSQL syntax with bot_id
cursor.execute("""
    SELECT * FROM trading.trades
    WHERE bot_id = %s AND exit_time IS NULL
""", (BOT_ID,))
```

### Step 3.3: Update LXAlgo Bot

#### 3.3.1: Add Database Persistence

**File:** `lxalgo/database/db_connector.py` (NEW FILE)

```python
import os
import psycopg2
from psycopg2.extras import RealDictCursor

BOT_ID = os.getenv('BOT_ID', 'lxalgo_001')

class DatabaseConnector:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'pgbouncer'),
            port=int(os.getenv('POSTGRES_PORT', '6432')),
            database=os.getenv('POSTGRES_DB', 'trading_db'),
            user=os.getenv('POSTGRES_USER', 'trading_user'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        self.bot_id = BOT_ID

    def log_trade_entry(self, symbol, side, quantity, price):
        cursor = self.conn.cursor()
        trade_id = f"{self.bot_id}_{symbol}_{int(time.time())}"

        cursor.execute("""
            INSERT INTO trading.trades (
                trade_id, bot_id, symbol, side, quantity,
                entry_price, position_size_usd, entry_time,
                strategy, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            trade_id, self.bot_id, symbol, side, quantity,
            price, quantity * price, datetime.now(),
            'lx_multi_indicator', 'filled'
        ))

        self.conn.commit()
        return trade_id
```

#### 3.3.2: Integrate with Main Trading Loop

**File:** `lxalgo/main.py`

```python
from database.db_connector import DatabaseConnector

db = DatabaseConnector()

def execute_trade(signal):
    # ... existing trade execution code ...

    # Log to database
    trade_id = db.log_trade_entry(
        symbol=signal['symbol'],
        side=signal['side'],
        quantity=quantity,
        price=price
    )

    logger.info(f"Trade logged to database: {trade_id}")
```

### Step 3.4: Update Environment Files

**Shortseller `.env`:**
```bash
BOT_ID=shortseller_001
POSTGRES_HOST=pgbouncer
POSTGRES_PORT=6432
POSTGRES_DB=trading_db
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=<from .env.database>
```

**Momentum `.env`:**
```bash
BOT_ID=momentum_001
USE_POSTGRES=true
POSTGRES_HOST=pgbouncer
POSTGRES_PORT=6432
POSTGRES_DB=trading_db
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=<from .env.database>
```

**LXAlgo `.env`:**
```bash
BOT_ID=lxalgo_001
POSTGRES_HOST=pgbouncer
POSTGRES_PORT=6432
POSTGRES_DB=trading_db
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=<from .env.database>
```

✅ **Checkpoint:** All bots updated to use unified database

---

## PHASE 4: TESTING & VALIDATION

**Duration:** 3-4 days
**Goal:** Thoroughly test the unified system

### Step 4.1: Unit Testing

Test each bot's database operations:

```python
# test_database_operations.py
import pytest
from database.db_connector import DatabaseConnector

def test_trade_logging():
    db = DatabaseConnector()

    trade_id = db.log_trade_entry(
        symbol='BTCUSDT',
        side='buy',
        quantity=0.01,
        price=45000
    )

    assert trade_id is not None
    assert trade_id.startswith(db.bot_id)

def test_position_tracking():
    # Test position creation and updates
    pass

def test_signal_logging():
    # Test signal recording
    pass
```

Run tests:
```bash
pytest test_database_operations.py -v
```

### Step 4.2: Integration Testing

```bash
# Start all services
docker-compose -f docker-compose.unified-db.yml up -d

# Monitor logs
docker-compose -f docker-compose.unified-db.yml logs -f shortseller lxalgo momentum

# Check database activity
docker exec trading_postgres psql -U trading_user -d trading_db -c \
    "SELECT bot_id, COUNT(*) FROM trading.trades GROUP BY bot_id;"
```

### Step 4.3: Performance Testing

```sql
-- Test query performance
EXPLAIN ANALYZE
SELECT * FROM trading.trades
WHERE bot_id = 'shortseller_001'
AND entry_time > NOW() - INTERVAL '7 days';

-- Check slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
WHERE mean_time > 100
ORDER BY mean_time DESC
LIMIT 10;
```

### Step 4.4: Data Integrity Checks

```sql
-- Check for orphaned records
SELECT COUNT(*) FROM trading.trades t
WHERE NOT EXISTS (
    SELECT 1 FROM trading.bots b WHERE b.bot_id = t.bot_id
);

-- Check for duplicate trade IDs
SELECT trade_id, COUNT(*)
FROM trading.trades
GROUP BY trade_id
HAVING COUNT(*) > 1;

-- Verify balance consistency
SELECT
    b.bot_id,
    b.current_equity,
    ab.equity as latest_balance,
    (b.current_equity - ab.equity) as difference
FROM trading.bots b
LEFT JOIN LATERAL (
    SELECT equity FROM trading.account_balance
    WHERE bot_id = b.bot_id
    ORDER BY timestamp DESC
    LIMIT 1
) ab ON true;
```

✅ **Checkpoint:** All tests passing

---

## PHASE 5: GO-LIVE

**Duration:** 1 day
**Goal:** Deploy to production

### Step 5.1: Pre-Go-Live Checklist

- [ ] All tests passed
- [ ] Backups verified
- [ ] Rollback plan reviewed
- [ ] Monitoring configured
- [ ] Alerts configured
- [ ] Documentation updated
- [ ] Team notified

### Step 5.2: Deployment

```bash
# Stop old system
docker-compose down

# Start unified system
docker-compose -f docker-compose.unified-db.yml up -d

# Verify all services healthy
docker-compose -f docker-compose.unified-db.yml ps

# Monitor for 30 minutes
watch -n 10 'docker-compose -f docker-compose.unified-db.yml ps'
```

### Step 5.3: Post-Deployment Verification

```sql
-- Verify all bots are active
SELECT bot_id, status, last_heartbeat
FROM trading.bots
WHERE status = 'active';

-- Check recent activity
SELECT
    bot_id,
    COUNT(*) as trades_last_hour
FROM trading.trades
WHERE entry_time > NOW() - INTERVAL '1 hour'
GROUP BY bot_id;

-- Check system health
SELECT * FROM analytics.system_health_dashboard;
```

### Step 5.4: Enable Monitoring

Set up Grafana dashboards:

1. Access Grafana: `http://your-server-ip:3000`
2. Login with admin credentials
3. Import dashboards from `database/grafana/dashboards/`
4. Configure alert channels (Telegram, Email)

### Step 5.5: Enable Automated Backups

```bash
# Verify backup service is running
docker-compose -f docker-compose.unified-db.yml ps postgres-backup

# Test manual backup
docker exec trading_postgres_backup /backup.sh

# Verify backup created
ls -lh database/backups/postgres/
```

✅ **Checkpoint:** System live and operational

---

## ROLLBACK PLAN

If critical issues occur, follow this rollback procedure:

### Rollback Steps

```bash
# 1. Stop unified system
docker-compose -f docker-compose.unified-db.yml down

# 2. Restore old system
docker-compose up -d

# 3. Restore databases from backup (if needed)
docker exec -i shortseller_postgres psql -U trading_user -d multiasset_trading < \
    database/backups/shortseller_backup_YYYYMMDD.sql

cp database/backups/momentum_backup_YYYYMMDD.db momentum/data/trading.db

# 4. Verify old system is working
docker-compose ps
docker-compose logs -f shortseller momentum lxalgo

# 5. Investigate issues
# - Check logs
# - Review error messages
# - Identify root cause
# - Plan fixes
```

---

## TROUBLESHOOTING

### Issue: Database Connection Failures

**Symptoms:**
- Bots cannot connect to PostgreSQL
- Connection timeout errors

**Solution:**
```bash
# Check database is running
docker ps | grep postgres

# Check connection from host
docker exec trading_postgres psql -U trading_user -d trading_db -c "SELECT 1"

# Check PgBouncer
docker logs trading_pgbouncer

# Verify credentials
echo $POSTGRES_PASSWORD
```

### Issue: Slow Query Performance

**Symptoms:**
- Dashboard loads slowly
- Bots experiencing delays

**Solution:**
```sql
-- Identify slow queries
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Rebuild indexes
REINDEX TABLE trading.trades;

-- Analyze tables
ANALYZE trading.trades;
ANALYZE trading.positions;
```

### Issue: Redis Connection Lost

**Symptoms:**
- Cache misses
- Redis connection errors

**Solution:**
```bash
# Check Redis
docker exec trading_redis redis-cli -a $REDIS_PASSWORD ping

# Check memory usage
docker exec trading_redis redis-cli -a $REDIS_PASSWORD info memory

# Clear cache if needed
docker exec trading_redis redis-cli -a $REDIS_PASSWORD FLUSHALL
```

### Issue: Data Mismatch Between Bots

**Symptoms:**
- Different equity values
- Missing trades

**Solution:**
```sql
-- Reconcile positions
SELECT
    bot_id,
    symbol,
    COUNT(*) as position_count,
    SUM(size) as total_size
FROM trading.positions
WHERE status = 'open'
GROUP BY bot_id, symbol;

-- Check for duplicates
SELECT trade_id, COUNT(*)
FROM trading.trades
GROUP BY trade_id
HAVING COUNT(*) > 1;
```

---

## MAINTENANCE TASKS

### Daily
- [ ] Check database backup completion
- [ ] Review error logs
- [ ] Monitor disk usage

### Weekly
- [ ] Analyze slow queries
- [ ] Review system events
- [ ] Check bot heartbeats

### Monthly
- [ ] Rebuild indexes
- [ ] Vacuum database
- [ ] Review and optimize queries
- [ ] Archive old data

---

## SUPPORT CONTACTS

**Database Issues:** Database Administrator
**Bot Issues:** Development Team
**Infrastructure:** DevOps Team
**Emergency:** On-Call Team

---

**End of Implementation Guide**
