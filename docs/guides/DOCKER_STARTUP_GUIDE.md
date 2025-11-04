# DOCKER COMPOSE STARTUP GUIDE

## ✅ CONFIGURATION FIXES COMPLETED

Your docker-compose.unified.yml has been **FIXED** and is now ready to use!

### Changes Made:
1. ✅ Fixed momentum path: `./momentum2` → `./momentum`
2. ✅ Verified shortseller paths (correct)
3. ✅ Verified lxalgo paths (correct)
4. ✅ All Dockerfiles exist and are properly configured
5. ✅ Created .env.example template for reference

---

## 📋 SYSTEM ARCHITECTURE VERIFIED

```
/home/william/STRATEGIES/Alpha/
├── docker-compose.unified.yml    ✅ FIXED AND READY
├── .env.example                  ✅ CREATED (template)
│
├── shortseller/                  ✅ VERIFIED
│   ├── Dockerfile                ✅ EXISTS
│   ├── init-db.sql              ✅ EXISTS (for PostgreSQL)
│   ├── requirements.txt          ✅ EXISTS
│   ├── .env                      ✅ EXISTS
│   └── scripts/start_trading.py  ✅ EXISTS (entry point)
│
├── lxalgo/                       ✅ VERIFIED
│   ├── Dockerfile                ✅ EXISTS
│   ├── main.py                   ✅ EXISTS (entry point)
│   ├── requirements.txt          ✅ EXISTS
│   └── .env                      ✅ EXISTS
│
└── momentum/                     ✅ VERIFIED
    ├── Dockerfile                ✅ EXISTS
    ├── trading_system.py         ✅ EXISTS (entry point)
    ├── requirements.txt          ✅ EXISTS
    └── .env                      ✅ EXISTS
```

---

## 🚀 HOW TO START YOUR SYSTEM

### PRE-FLIGHT CHECKLIST

Before starting, ensure:

1. **Docker and Docker Compose are installed**:
   ```bash
   # Check Docker
   docker --version

   # Check Docker Compose (try both commands)
   docker-compose --version
   # OR
   docker compose version
   ```

2. **Environment variables are configured**:
   ```bash
   # Check if .env files exist for each system
   ls -la shortseller/.env
   ls -la lxalgo/.env
   ls -la momentum/.env

   # Verify they contain API keys (don't print them!)
   grep -c "API_KEY" shortseller/.env
   grep -c "API_KEY" lxalgo/.env
   grep -c "API_KEY" momentum/.env
   ```

3. **You're in the correct directory**:
   ```bash
   cd /home/william/STRATEGIES/Alpha
   pwd  # Should show: /home/william/STRATEGIES/Alpha
   ```

---

## 🎯 STARTUP COMMANDS

### Option 1: Start Everything at Once

```bash
cd /home/william/STRATEGIES/Alpha

# Build all images first (one-time or after code changes)
docker compose -f docker-compose.unified.yml build

# Start all services
docker compose -f docker-compose.unified.yml up -d

# View logs from all services
docker compose -f docker-compose.unified.yml logs -f
```

### Option 2: Start Services Individually

```bash
cd /home/william/STRATEGIES/Alpha

# 1. Start infrastructure first (PostgreSQL + Redis)
docker compose -f docker-compose.unified.yml up -d shortseller-postgres shortseller-redis

# Wait 30 seconds for database initialization
sleep 30

# 2. Start shortseller (multi-asset trading)
docker compose -f docker-compose.unified.yml up -d shortseller

# 3. Start lxalgo (CFT prop trading)
docker compose -f docker-compose.unified.yml up -d lxalgo

# 4. Start momentum (momentum strategy)
docker compose -f docker-compose.unified.yml up -d momentum

# View logs
docker compose -f docker-compose.unified.yml logs -f
```

### Option 3: Start Only Specific System

```bash
# Start only shortseller (with dependencies)
docker compose -f docker-compose.unified.yml up -d shortseller

# Start only lxalgo
docker compose -f docker-compose.unified.yml up -d lxalgo

# Start only momentum
docker compose -f docker-compose.unified.yml up -d momentum
```

---

## 📊 MONITORING COMMANDS

### View Running Containers
```bash
docker compose -f docker-compose.unified.yml ps
```

### View Logs

```bash
# All services
docker compose -f docker-compose.unified.yml logs -f

# Specific service
docker compose -f docker-compose.unified.yml logs -f shortseller
docker compose -f docker-compose.unified.yml logs -f lxalgo
docker compose -f docker-compose.unified.yml logs -f momentum

# Last 100 lines
docker compose -f docker-compose.unified.yml logs --tail=100 shortseller

# Infrastructure logs
docker compose -f docker-compose.unified.yml logs -f shortseller-postgres
docker compose -f docker-compose.unified.yml logs -f shortseller-redis
```

### Check Service Health

```bash
# View health status
docker compose -f docker-compose.unified.yml ps

# Check PostgreSQL
docker compose -f docker-compose.unified.yml exec shortseller-postgres pg_isready -U trading_user -d multiasset_trading

# Check Redis
docker compose -f docker-compose.unified.yml exec shortseller-redis redis-cli ping

# Check if trading bot process is running
docker compose -f docker-compose.unified.yml exec shortseller pgrep -f start_trading.py
docker compose -f docker-compose.unified.yml exec lxalgo pgrep -f main.py
docker compose -f docker-compose.unified.yml exec momentum pgrep -f trading_system.py
```

### Enter a Container (Debug)

```bash
# Enter shortseller container
docker compose -f docker-compose.unified.yml exec shortseller /bin/bash

# Enter lxalgo container
docker compose -f docker-compose.unified.yml exec lxalgo /bin/bash

# Enter momentum container
docker compose -f docker-compose.unified.yml exec momentum /bin/bash

# Enter PostgreSQL
docker compose -f docker-compose.unified.yml exec shortseller-postgres psql -U trading_user -d multiasset_trading

# Enter Redis CLI
docker compose -f docker-compose.unified.yml exec shortseller-redis redis-cli
```

---

## 🛑 STOP COMMANDS

### Stop All Services
```bash
docker compose -f docker-compose.unified.yml down
```

### Stop Specific Service
```bash
docker compose -f docker-compose.unified.yml stop shortseller
docker compose -f docker-compose.unified.yml stop lxalgo
docker compose -f docker-compose.unified.yml stop momentum
```

### Stop and Remove Everything (Including Volumes)
```bash
# ⚠️ WARNING: This will delete database data!
docker compose -f docker-compose.unified.yml down -v
```

### Restart Services
```bash
# Restart all
docker compose -f docker-compose.unified.yml restart

# Restart specific service
docker compose -f docker-compose.unified.yml restart shortseller
docker compose -f docker-compose.unified.yml restart lxalgo
docker compose -f docker-compose.unified.yml restart momentum
```

---

## 🔧 TROUBLESHOOTING

### Issue: "docker compose" command not found

**Solution 1**: Try `docker-compose` (with hyphen):
```bash
docker-compose -f docker-compose.unified.yml up -d
```

**Solution 2**: Install Docker Compose:
```bash
# For Ubuntu/Debian
sudo apt update
sudo apt install docker-compose

# OR install Docker Compose V2
sudo apt install docker-compose-plugin
```

### Issue: "Permission denied" when running docker

**Solution**: Add your user to docker group:
```bash
sudo usermod -aG docker $USER
newgrp docker
# Or logout and login again
```

### Issue: Container keeps restarting

**Check logs**:
```bash
docker compose -f docker-compose.unified.yml logs shortseller
```

**Common causes**:
- Missing environment variables in .env files
- Invalid API keys
- Database connection failed
- Python import errors

### Issue: PostgreSQL connection refused

**Solution**:
```bash
# Wait for PostgreSQL to fully start (takes ~30 seconds)
sleep 30

# Check PostgreSQL health
docker compose -f docker-compose.unified.yml logs shortseller-postgres

# Check if database is ready
docker compose -f docker-compose.unified.yml exec shortseller-postgres pg_isready
```

### Issue: Module not found errors

**Solution**: Rebuild the image:
```bash
docker compose -f docker-compose.unified.yml build --no-cache shortseller
docker compose -f docker-compose.unified.yml up -d shortseller
```

### Issue: Port already in use

**Solution**: Check what's using the port:
```bash
# Check port 5432 (PostgreSQL)
sudo lsof -i :5432

# Check port 6379 (Redis)
sudo lsof -i :6379

# Stop conflicting service or change port in docker-compose.yml
```

---

## 📈 VERIFICATION CHECKLIST

After starting your system, verify:

- [ ] All containers are running: `docker compose -f docker-compose.unified.yml ps`
- [ ] No restart loops (Status should be "Up")
- [ ] PostgreSQL is healthy: `docker compose -f docker-compose.unified.yml exec shortseller-postgres pg_isready`
- [ ] Redis is healthy: `docker compose -f docker-compose.unified.yml exec shortseller-redis redis-cli ping`
- [ ] Logs show successful startup (no Python errors)
- [ ] Each bot connects to exchange successfully
- [ ] Telegram notifications work (if enabled)
- [ ] Database tables created in PostgreSQL
- [ ] Monitor for 5-10 minutes to ensure stability

---

## 🎯 QUICK REFERENCE

### Start Everything
```bash
cd /home/william/STRATEGIES/Alpha
docker compose -f docker-compose.unified.yml up -d
```

### View Logs
```bash
docker compose -f docker-compose.unified.yml logs -f
```

### Check Status
```bash
docker compose -f docker-compose.unified.yml ps
```

### Stop Everything
```bash
docker compose -f docker-compose.unified.yml down
```

### Rebuild After Code Changes
```bash
docker compose -f docker-compose.unified.yml build
docker compose -f docker-compose.unified.yml up -d
```

---

## 🔐 ENVIRONMENT VARIABLES

Each system needs its own .env file:

1. **shortseller/.env**: Already exists (contains Bybit API keys, Telegram tokens)
2. **lxalgo/.env**: Already exists (contains Bybit API keys)
3. **momentum/.env**: Already exists (contains demo/live API keys)

Reference the `.env.example` file in the root directory for the template.

---

## 📞 NEXT STEPS

1. **Verify your .env files have valid API keys**
2. **Start with testnet mode first** (BYBIT_TESTNET=true)
3. **Run the startup command**
4. **Monitor logs for 5-10 minutes**
5. **Check Telegram notifications** (if enabled)
6. **Verify trades are being executed** (on testnet first!)

---

## ⚠️ IMPORTANT REMINDERS

- **Always test on TESTNET first** before going live
- **Monitor your bots regularly** - set up alerts
- **Keep API keys secure** - never commit to git
- **Backup your database** regularly (PostgreSQL data)
- **Monitor system resources** (CPU, RAM, disk space)
- **Have a kill switch ready** - know how to stop everything quickly
- **Start with small position sizes** to test the system
- **Review logs daily** to catch issues early

---

**Your system is now ready to run! 🚀**

Good luck with your trading!
