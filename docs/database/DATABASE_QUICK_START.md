# DATABASE QUICK START GUIDE
## Get the Unified Database System Running in 30 Minutes

**Last Updated:** 2025-10-24

---

## 🚀 QUICK START (30 Minutes)

### Prerequisites Check (5 minutes)

```bash
# Check Docker
docker --version  # Need 20.10+
docker-compose --version  # Need 2.0+

# Check available disk space (need at least 10GB)
df -h

# Verify you're in the right directory
cd /home/william/STRATEGIES/Alpha
pwd
```

### Step 1: Create Database Directories (2 minutes)

```bash
# Create required directories
mkdir -p database/{migrations,config,backups/{postgres,influxdb},grafana/{dashboards,datasources}}

# Set permissions
chmod -R 755 database/
```

### Step 2: Set Up Environment (3 minutes)

```bash
# Generate secure passwords
POSTGRES_PASS=$(openssl rand -base64 24)
REDIS_PASS=$(openssl rand -base64 24)
INFLUX_PASS=$(openssl rand -base64 24)
INFLUX_TOKEN=$(openssl rand -base64 32)
GRAFANA_PASS=$(openssl rand -base64 16)

# Create environment file
cat > .env.database <<EOF
POSTGRES_PASSWORD=$POSTGRES_PASS
REDIS_PASSWORD=$REDIS_PASS
INFLUX_USERNAME=admin
INFLUX_PASSWORD=$INFLUX_PASS
INFLUX_ORG=trading_org
INFLUX_BUCKET=market_data
INFLUX_TOKEN=$INFLUX_TOKEN
GRAFANA_USER=admin
GRAFANA_PASSWORD=$GRAFANA_PASS
GRAFANA_ROOT_URL=http://localhost:3000
EOF

# Save credentials for later
echo "IMPORTANT: Save these credentials!"
cat .env.database
```

### Step 3: Start Database Services (5 minutes)

```bash
# Load environment
source .env.database

# Start only databases first (PostgreSQL, Redis, InfluxDB)
docker-compose -f docker-compose.unified-db.yml up -d postgres redis influxdb

# Wait for services to be healthy (will take ~30 seconds)
echo "Waiting for databases to be ready..."
sleep 30

# Check status
docker-compose -f docker-compose.unified-db.yml ps
```

Expected output:
```
NAME                   STATUS
trading_postgres       Up (healthy)
trading_redis          Up (healthy)
trading_influxdb       Up (healthy)
```

### Step 4: Verify Database Connections (5 minutes)

```bash
# Test PostgreSQL
docker exec trading_postgres psql -U trading_user -d trading_db -c "SELECT version();"

# Test Redis
docker exec trading_redis redis-cli -a $REDIS_PASSWORD ping

# Test InfluxDB
docker exec trading_influxdb influx ping

# If all return success, you're good! ✅
```

### Step 5: Initialize Schema (5 minutes)

```bash
# The schema should auto-initialize from the mounted SQL files
# Verify tables were created
docker exec trading_postgres psql -U trading_user -d trading_db -c "\dt trading.*"

# You should see 8 tables in the trading schema
# If not, manually run the migration:
docker exec -i trading_postgres psql -U trading_user -d trading_db < database/migrations/001_unified_schema.sql
```

### Step 6: Start Monitoring (3 minutes)

```bash
# Start Grafana
docker-compose -f docker-compose.unified-db.yml up -d grafana

# Wait for Grafana to start
sleep 10

# Access Grafana
echo "Grafana URL: http://localhost:3000"
echo "Username: admin"
echo "Password: $GRAFANA_PASSWORD"
```

### Step 7: Register Bots (2 minutes)

```bash
# Register all three bots
docker exec -i trading_postgres psql -U trading_user -d trading_db < database/migrations/002_migrate_shortseller_data.sql
docker exec -i trading_postgres psql -U trading_user -d trading_db < database/migrations/003_migrate_momentum_data.sql
docker exec -i trading_postgres psql -U trading_user -d trading_db < database/migrations/004_register_lxalgo_bot.sql

# Verify registration
docker exec trading_postgres psql -U trading_user -d trading_db -c "SELECT bot_id, bot_name, status FROM trading.bots;"
```

Expected output:
```
     bot_id      |            bot_name             | status
-----------------+---------------------------------+--------
 shortseller_001 | Multi-Asset EMA Crossover Bot   | active
 momentum_001    | Volatility Breakout Momentum Bot| active
 lxalgo_001      | LX Technical Analysis Bot       | active
```

### Step 8: Verify Everything (5 minutes)

```bash
# Check all services
docker-compose -f docker-compose.unified-db.yml ps

# View logs
docker-compose -f docker-compose.unified-db.yml logs --tail=20 postgres

# Test a query
docker exec trading_postgres psql -U trading_user -d trading_db <<EOF
SELECT
    'Database Tables' as component,
    COUNT(*) as count
FROM information_schema.tables
WHERE table_schema = 'trading'
UNION ALL
SELECT
    'Registered Bots',
    COUNT(*)
FROM trading.bots
UNION ALL
SELECT
    'Active Bots',
    COUNT(*)
FROM trading.bots
WHERE status = 'active';
EOF
```

---

## ✅ SUCCESS CHECKLIST

After completing Quick Start, you should have:

- [x] PostgreSQL running on port 5432
- [x] Redis running on port 6379
- [x] InfluxDB running on port 8086
- [x] Grafana running on port 3000
- [x] 12 tables created in trading schema
- [x] 3 bots registered and active
- [x] Environment file with secure credentials

---

## 📊 ESSENTIAL COMMANDS

### Database Access

```bash
# PostgreSQL CLI
docker exec -it trading_postgres psql -U trading_user -d trading_db

# Redis CLI
docker exec -it trading_redis redis-cli -a $REDIS_PASSWORD

# InfluxDB CLI
docker exec -it trading_influxdb influx
```

### Useful Queries

```sql
-- View all bots
SELECT bot_id, bot_name, status, current_equity
FROM trading.bots;

-- View recent trades (all bots)
SELECT bot_id, symbol, side, quantity, entry_price, entry_time
FROM trading.trades
ORDER BY entry_time DESC
LIMIT 20;

-- View active positions
SELECT bot_id, symbol, side, size, unrealized_pnl
FROM trading.positions
WHERE status = 'open';

-- Daily performance by bot
SELECT
    bot_id,
    date,
    total_trades,
    win_rate,
    daily_pnl
FROM trading.risk_metrics
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC, bot_id;

-- System health check
SELECT * FROM analytics.system_health_dashboard;
```

### Service Management

```bash
# Start all services
docker-compose -f docker-compose.unified-db.yml up -d

# Stop all services
docker-compose -f docker-compose.unified-db.yml down

# Restart a service
docker-compose -f docker-compose.unified-db.yml restart postgres

# View logs
docker-compose -f docker-compose.unified-db.yml logs -f [service_name]

# Check service health
docker-compose -f docker-compose.unified-db.yml ps
```

### Backup & Restore

```bash
# Manual backup
docker exec trading_postgres pg_dump -U trading_user trading_db > backup_$(date +%Y%m%d).sql

# Restore from backup
docker exec -i trading_postgres psql -U trading_user trading_db < backup_20251024.sql

# Redis backup
docker exec trading_redis redis-cli -a $REDIS_PASSWORD BGSAVE
```

---

## 🔍 COMMON ISSUES

### Issue: "Connection refused" errors

```bash
# Check if containers are running
docker ps | grep trading

# Check container logs
docker logs trading_postgres

# Restart the service
docker-compose -f docker-compose.unified-db.yml restart postgres
```

### Issue: "Permission denied" on database files

```bash
# Fix ownership
sudo chown -R $(whoami):$(whoami) database/

# Fix permissions
chmod -R 755 database/
```

### Issue: "Out of memory" errors

```bash
# Check container resources
docker stats

# Increase Docker memory limit in Docker Desktop settings
# Or add to docker-compose.yml:
mem_limit: 2g
```

### Issue: Migration scripts fail

```bash
# Check if schema already exists
docker exec trading_postgres psql -U trading_user -d trading_db -c "\dn"

# Drop and recreate if needed (WARNING: This deletes all data!)
docker exec trading_postgres psql -U trading_user -d trading_db -c "DROP SCHEMA trading CASCADE;"

# Re-run migration
docker exec -i trading_postgres psql -U trading_user -d trading_db < database/migrations/001_unified_schema.sql
```

---

## 🎯 NEXT STEPS

After Quick Start is complete:

### Immediate
1. **Configure Grafana Dashboards**
   - Login to Grafana (http://localhost:3000)
   - Add PostgreSQL data source
   - Import pre-built dashboards

2. **Set Up Automated Backups**
   ```bash
   # Start backup service
   docker-compose -f docker-compose.unified-db.yml up -d postgres-backup
   ```

3. **Update Bot Configurations**
   - Update each bot's `.env` file with new database credentials
   - Add `BOT_ID` environment variable
   - Point to `pgbouncer` for database connections

### This Week
4. **Data Migration**
   - Run Shortseller data migration: `002_migrate_shortseller_data.sql`
   - Run Momentum migration script: `migrate_momentum_sqlite_to_postgres.py`
   - Verify data integrity

5. **Update Bot Code**
   - Add `bot_id` to all database queries
   - Update connection strings
   - Test in development

6. **Testing**
   - Run unit tests
   - Verify data isolation between bots
   - Check performance

### This Month
7. **Go Live**
   - Deploy updated bots
   - Monitor for 24 hours
   - Enable all alerting

8. **Optimization**
   - Analyze slow queries
   - Tune indexes
   - Optimize configurations

---

## 📚 DOCUMENTATION

- **Full Architecture:** [DATABASE_ARCHITECTURE_CATALOGUE.md](DATABASE_ARCHITECTURE_CATALOGUE.md)
- **Implementation:** [DATABASE_IMPLEMENTATION_GUIDE.md](DATABASE_IMPLEMENTATION_GUIDE.md)
- **Summary:** [DATABASE_PROJECT_SUMMARY.md](DATABASE_PROJECT_SUMMARY.md)
- **This Guide:** [DATABASE_QUICK_START.md](DATABASE_QUICK_START.md)

---

## 🆘 NEED HELP?

### Check Logs
```bash
# All services
docker-compose -f docker-compose.unified-db.yml logs

# Specific service
docker-compose -f docker-compose.unified-db.yml logs postgres

# Follow logs in real-time
docker-compose -f docker-compose.unified-db.yml logs -f
```

### Database Status
```bash
# PostgreSQL
docker exec trading_postgres pg_isready -U trading_user

# Redis
docker exec trading_redis redis-cli -a $REDIS_PASSWORD info server

# InfluxDB
docker exec trading_influxdb influx ping
```

### Reset Everything (Nuclear Option)
```bash
# WARNING: This deletes ALL data!
docker-compose -f docker-compose.unified-db.yml down -v
docker volume prune -f
# Then start from Step 1
```

---

## 🎉 SUCCESS!

If you've made it this far, you now have:

✅ A fully functional unified database system
✅ All three bots registered
✅ Monitoring with Grafana
✅ Automated backups configured
✅ A scalable foundation for growth

**You're ready to start migrating data and updating your bots!**

---

**Quick Start Guide - v1.0**
**Total Time:** ~30 minutes
**Difficulty:** Intermediate
