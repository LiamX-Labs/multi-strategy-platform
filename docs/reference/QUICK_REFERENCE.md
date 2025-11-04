# 🎯 ALPHA C2 - Quick Reference Card

## 🚀 Deployment (One-Time Setup)

```bash
# 1. Get Telegram Bot Token from @BotFather
# 2. Get your User ID from @userinfobot
# 3. Add to .env file:
echo "C2_TELEGRAM_BOT_TOKEN=your_token_here" >> .env
echo "C2_TELEGRAM_ADMIN_IDS=your_user_id_here" >> .env

# 4. Deploy
./deploy_c2.sh
```

---

## 📋 Essential Commands

| Command | Action |
|---------|--------|
| `/cc` | **Main Menu** (Start here) |
| `/sitrep` | **Full Status Report** |
| `/deploy alpha` | Start ALPHA system |
| `/terminate bravo` | Stop BRAVO system |
| `/reboot charlie` | Restart CHARLIE system |
| `/intel alpha 100` | View ALPHA logs (100 lines) |
| `/diagnostics alpha` | System diagnostics |
| `/killswitch CONFIRM` | **Emergency shutdown** |

---

## 🏷️ System IDs

**Trading:** `alpha` `bravo` `charlie`
**Infrastructure:** `database` `cache`

---

## ⚡ Quick Actions

### Check Everything
```
/sitrep
```

### Start All
```
/deploy_all
```

### Stop All
```
/terminate_all
```

### Emergency Stop Trading
```
/killswitch CONFIRM
```

### View Logs
```
/intel alpha
/intel bravo
/intel charlie
```

### System Health
```
/diagnostics alpha
/diagnostics bravo
/diagnostics charlie
```

---

## 🔧 Maintenance

```bash
# View C2 logs
docker-compose logs -f telegram_manager

# Restart C2
docker-compose restart telegram_manager

# Rebuild C2
docker-compose build telegram_manager
docker-compose up -d telegram_manager
```

---

## 🎯 System Mapping

| ID | Name | Container |
|----|------|-----------|
| `alpha` | ALPHA SYSTEM | shortseller_trading |
| `bravo` | BRAVO SYSTEM | lxalgo_trading |
| `charlie` | CHARLIE SYSTEM | momentum_trading |
| `database` | DATABASE CORE | shortseller_postgres |
| `cache` | CACHE CORE | shortseller_redis |

---

## 📞 Troubleshooting

**Bot not responding?**
```bash
docker-compose restart telegram_manager
docker-compose logs telegram_manager
```

**Access denied?**
```bash
# Check your user ID is in .env
grep C2_TELEGRAM_ADMIN_IDS .env
```

**Can't find systems?**
```bash
# Verify containers exist
docker ps -a
```

---

## 💡 Pro Tips

1. Use `/cc` for button interface (faster)
2. Pin the bot chat in Telegram
3. Use `/help` for full command list
4. Test `/killswitch` in safe environment first
5. Check `/sitrep` daily

---

**Full Documentation:** [COMMAND_CENTER_GUIDE.md](COMMAND_CENTER_GUIDE.md)
