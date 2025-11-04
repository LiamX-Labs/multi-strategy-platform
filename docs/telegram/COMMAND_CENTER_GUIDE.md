# 🎯 ALPHA COMMAND CENTER - Deployment Guide

## Overview

Your Command & Control (C&C) layer is now ready for deployment. This professional-grade Telegram bot gives you complete tactical control over your entire trading infrastructure.

---

## 🚀 Quick Start

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name: `Alpha Command Center` (or your preference)
4. Choose a username: `your_alpha_c2_bot` (must end in 'bot')
5. Copy the token you receive (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Telegram User ID

1. Open Telegram and search for `@userinfobot`
2. Send any message to the bot
3. Copy your user ID (a number like: `123456789`)

### Step 3: Configure Environment Variables

Add these lines to your `.env` file in `/home/william/STRATEGIES/Alpha/`:

```bash
# Telegram Command Center
C2_TELEGRAM_BOT_TOKEN=your_token_from_botfather_here
C2_TELEGRAM_ADMIN_IDS=your_user_id_here
```

**Example:**
```bash
C2_TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
C2_TELEGRAM_ADMIN_IDS=123456789
```

**Multiple Admins** (comma-separated):
```bash
C2_TELEGRAM_ADMIN_IDS=123456789,987654321,555444333
```

### Step 4: Deploy the Command Center

```bash
cd /home/william/STRATEGIES/Alpha

# Build and start the command center
docker-compose up -d telegram_manager

# Verify it's running
docker-compose logs -f telegram_manager
```

You should see:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ALPHA COMMAND CENTER - INITIALIZING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Authorized operators: 1
✓ Systems under control: 5
✓ Command Center operational
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 5: First Contact

1. Open Telegram
2. Find your bot (search for the username you created)
3. Send `/cc` or `/start`

You should see the **Command Center Main Menu** with interactive buttons.

---

## 📋 Command Reference

### 🎯 Situation Awareness

| Command | Description |
|---------|-------------|
| `/cc` | Main Command Center Interface |
| `/sitrep` | Full Tactical Situation Report |
| `/diagnostics <system>` | Detailed System Diagnostics |

### ⚡ System Control

| Command | Description |
|---------|-------------|
| `/deploy <system>` | Deploy (Start) a System |
| `/terminate <system>` | Terminate (Stop) a System |
| `/reboot <system>` | Reboot (Restart) a System |

### 📡 Intelligence

| Command | Description |
|---------|-------------|
| `/intel <system> [lines]` | View System Logs (default 50 lines) |
| `/execute <system> <cmd>` | Execute Command in System Container |

### 🔧 Mass Operations

| Command | Description |
|---------|-------------|
| `/deploy_all` | Deploy All Systems |
| `/terminate_all` | Shutdown All Systems |
| `/reboot_all` | Restart All Systems |

### 🔴 Emergency

| Command | Description |
|---------|-------------|
| `/killswitch CONFIRM` | Emergency Trading Halt (All Trading Systems) |

### 📚 Help

| Command | Description |
|---------|-------------|
| `/help` | Display Full Command Reference |

---

## 🏷️ System Identifiers

### Trading Systems
- **`alpha`** - Multi-Asset Short Seller (shortseller_trading)
- **`bravo`** - LX Algorithm Executor (lxalgo_trading)
- **`charlie`** - Momentum Strategy Engine (momentum_trading)

### Infrastructure
- **`database`** - PostgreSQL Database Core (shortseller_postgres)
- **`cache`** - Redis Cache Layer (shortseller_redis)

---

## 💡 Usage Examples

### Example 1: Deploy Specific System
```
You: /deploy alpha

Bot: 🚀 DEPLOYED

ALPHA SYSTEM is now operational.
```

### Example 2: Check Full Status
```
You: /sitrep

Bot: 📊 TACTICAL SITUATION REPORT
━━━━━━━━━━━━━━━━━━━━━
⏰ 2025-10-23 14:30:00 UTC

🎯 TRADING SYSTEMS
🟢 ALPHA SYSTEM: OPERATIONAL
🟢 BRAVO SYSTEM: OPERATIONAL
🔴 CHARLIE SYSTEM: OFFLINE

🔧 INFRASTRUCTURE
🟢 DATABASE CORE: OPERATIONAL
🟢 CACHE CORE: OPERATIONAL

━━━━━━━━━━━━━━━━━━━━━
OPERATIONAL STATUS:
├─ Trading: 2/3
└─ Infrastructure: 2/2

🟡 PARTIAL OPERATIONS
```

### Example 3: View System Logs
```
You: /intel bravo 100

Bot: 📡 INTEL: BRAVO SYSTEM
━━━━━━━━━━━━━━━━━━━━━

[Last 100 log lines displayed]
```

### Example 4: System Diagnostics
```
You: /diagnostics alpha

Bot: 🔬 SYSTEM DIAGNOSTICS
━━━━━━━━━━━━━━━━━━━━━

SYSTEM: ALPHA SYSTEM
ID: alpha
TYPE: TRADING
CONTAINER: shortseller_trading

🟢 STATUS: OPERATIONAL

CPU USAGE: 12.34%
MEMORY: 245.5MB / 900.0MB (27.3%)
NETWORK (eth0):
  ├─ RX: 125.42MB
  └─ TX: 89.33MB

STARTED: 2025-10-23T10:15:22
```

### Example 5: Execute Command
```
You: /execute alpha ls -la /app

Bot: ⚡ COMMAND EXECUTED
━━━━━━━━━━━━━━━━━━━━━
SYSTEM: ALPHA SYSTEM
COMMAND: ls -la /app

OUTPUT:
total 48
drwxr-xr-x 1 root root 4096 Oct 23 10:15 .
drwxr-xr-x 1 root root 4096 Oct 23 10:15 ..
-rw-r--r-- 1 root root 1234 Oct 23 10:15 main.py
...
```

### Example 6: Emergency Shutdown
```
You: /killswitch

Bot: 🔴 KILLSWITCH ACTIVATION
━━━━━━━━━━━━━━━━━━━━━

⚠️ This will immediately terminate:
  • ALPHA System
  • BRAVO System
  • CHARLIE System

All active trades will cease.

To confirm: /killswitch CONFIRM

You: /killswitch CONFIRM

Bot: 🔴 KILLSWITCH EXECUTED
━━━━━━━━━━━━━━━━━━━━━

✅ ALPHA SYSTEM - TERMINATED
✅ BRAVO SYSTEM - TERMINATED
✅ CHARLIE SYSTEM - TERMINATED

⏰ 2025-10-23 14:45:30 UTC
```

---

## 🎮 Interactive Buttons

The bot provides a full interactive menu system when you send `/cc`:

### Main Menu Buttons:
- **📊 TACTICAL OVERVIEW** - View all systems status
- **🚀 DEPLOY ALL** - Start all systems
- **🔴 KILL SWITCH** - Emergency shutdown with confirmation
- **⚡ TRADING SYSTEMS** - Individual control panel for trading bots
- **🔧 INFRASTRUCTURE** - Control database and cache
- **📡 SYSTEM LOGS** - Quick access to logs
- **🔄 MASS RESTART** - Restart all systems
- **⚙️ ADVANCED OPS** - Advanced operations menu

### Per-System Controls:
Each system has:
- 🚀 **Deploy** - Start the system
- 🛑 **Terminate** - Stop the system
- 🔄 **Reboot** - Restart the system
- 📡 **Intel** - View logs
- 🔬 **Diagnostics** - Detailed stats

---

## 🔒 Security Features

1. **Authorization Layer**
   - Only configured Telegram user IDs can access
   - Unauthorized attempts are logged and rejected
   - All actions are logged with operator identification

2. **Docker Security**
   - Docker socket mounted as read-only (`:ro`)
   - Container cannot modify Docker daemon configuration
   - Limited to start/stop/inspect operations

3. **Command Confirmation**
   - Destructive operations (like killswitch) require explicit confirmation
   - No accidental shutdowns

4. **Isolation**
   - Bot does NOT interact with trading logic
   - Only manages container lifecycle
   - Cannot modify trading strategies or positions

5. **Audit Trail**
   - All commands logged to `/telegram_manager/logs/command_center.log`
   - Timestamp and operator identification on all actions

---

## 🔧 Advanced Operations

### Database Queries
```bash
/execute database psql -U trading_user -d multiasset_trading -c "SELECT COUNT(*) FROM trades WHERE status='active'"
```

### Redis Cache Stats
```bash
/execute cache redis-cli INFO stats
```

### Check Trading Bot Process
```bash
/execute alpha ps aux
```

### View Environment Variables (filtered)
```bash
/execute bravo printenv | grep -v SECRET
```

### Disk Space Check
```bash
/execute alpha df -h
```

---

## 📊 Monitoring Capabilities

The Command Center provides real-time monitoring of:

- **Container Status**: Running, stopped, restarting
- **CPU Usage**: Per-container CPU utilization
- **Memory Usage**: Current usage and limits
- **Network I/O**: Bytes transmitted and received
- **Uptime**: When each system was started
- **Health Status**: Container health check results

---

## 🐛 Troubleshooting

### Bot Not Responding

**Check bot status:**
```bash
docker-compose logs telegram_manager
```

**Restart the bot:**
```bash
docker-compose restart telegram_manager
```

### "ACCESS DENIED" Messages

**Verify your user ID is correct:**
```bash
# Check current configuration
docker exec telegram_c2 printenv TELEGRAM_ADMIN_IDS

# Should show your Telegram user ID
```

**Update if needed:**
1. Edit `.env` file
2. Update `C2_TELEGRAM_ADMIN_IDS`
3. Restart: `docker-compose restart telegram_manager`

### Docker Permission Errors

**Verify Docker socket is accessible:**
```bash
docker exec telegram_c2 ls -la /var/run/docker.sock
```

Should show:
```
srw-rw---- 1 root docker /var/run/docker.sock
```

### System Not Found Errors

**Verify container names match:**
```bash
docker ps -a --format "table {{.Names}}\t{{.Status}}"
```

Should show:
- `shortseller_trading`
- `lxalgo_trading`
- `momentum_trading`
- `shortseller_postgres`
- `shortseller_redis`

---

## 📝 Log Files

### Command Center Logs
```bash
tail -f /home/william/STRATEGIES/Alpha/telegram_manager/logs/command_center.log
```

### Docker Logs
```bash
docker-compose logs -f telegram_manager
```

---

## 🔄 Updates & Maintenance

### Restart Command Center
```bash
docker-compose restart telegram_manager
```

### Rebuild After Code Changes
```bash
docker-compose build telegram_manager
docker-compose up -d telegram_manager
```

### View Real-time Logs
```bash
docker-compose logs -f telegram_manager
```

### Check Resource Usage
```bash
docker stats telegram_c2
```

---

## 🎨 Customization

### Changing System Names

Edit `telegram_manager/bot.py` and modify the `SYSTEMS` dictionary:

```python
SYSTEMS = {
    'alpha': {
        'container': 'shortseller_trading',
        'name': 'YOUR CUSTOM NAME',
        'description': 'Your description',
        'type': 'trading'
    },
    # ... more systems
}
```

Then rebuild:
```bash
docker-compose build telegram_manager
docker-compose up -d telegram_manager
```

### Adding More Authorized Users

Update `.env`:
```bash
C2_TELEGRAM_ADMIN_IDS=123456789,987654321,555444333
```

Restart:
```bash
docker-compose restart telegram_manager
```

---

## 🌟 Pro Tips

1. **Use Interactive Menus**: The button interface (`/cc`) is faster than typing commands

2. **Bookmark Commands**: Create Telegram saved messages with common commands

3. **Monitor Regularly**: Set up a routine to check `/sitrep` daily

4. **Log Review**: Periodically check system logs with `/intel` to catch issues early

5. **Emergency Preparedness**: Test `/killswitch CONFIRM` in a safe environment first

6. **Combine Commands**: Use `/execute` for complex operations
   ```
   /execute alpha cat /app/config/settings.py | grep LEVERAGE
   ```

7. **Quick Status**: Pin the Command Center chat in Telegram for fast access

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────┐
│      TELEGRAM BOT API           │
│   (Cloud Infrastructure)        │
└────────────┬────────────────────┘
             │
             │ HTTPS
             ▼
┌─────────────────────────────────┐
│    telegram_manager Container   │
│  ┌───────────────────────────┐  │
│  │   bot.py (Python)         │  │
│  │   - Authorization         │  │
│  │   - Command Processing    │  │
│  │   - Docker API Client     │  │
│  └─────────────┬─────────────┘  │
└────────────────┼─────────────────┘
                 │
                 │ Docker API
                 ▼
┌─────────────────────────────────┐
│      /var/run/docker.sock       │
│         (Docker Daemon)         │
└────────────────┬────────────────┘
                 │
     ┌───────────┼───────────┐
     │           │           │
     ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ ALPHA   │ │ BRAVO   │ │ CHARLIE │
│ System  │ │ System  │ │ System  │
└─────────┘ └─────────┘ └─────────┘

     ▼                       ▼
┌─────────┐           ┌─────────┐
│Database │           │  Cache  │
│  Core   │           │  Core   │
└─────────┘           └─────────┘
```

---

## ✅ Verification Checklist

- [ ] Telegram bot created via @BotFather
- [ ] Bot token added to `.env` file
- [ ] Your Telegram user ID obtained from @userinfobot
- [ ] User ID added to `.env` file
- [ ] Command center deployed: `docker-compose up -d telegram_manager`
- [ ] Logs checked: `docker-compose logs telegram_manager`
- [ ] Bot responds to `/cc` command in Telegram
- [ ] `/sitrep` shows all systems
- [ ] Tested `/deploy alpha` command
- [ ] Tested `/intel alpha` command
- [ ] Emergency `/killswitch` understood

---

## 🎯 Next Steps

1. **Test All Commands**: Go through each command to familiarize yourself
2. **Set Up Alerts**: Consider adding automatic alerts for system failures
3. **Create Playbooks**: Document your standard operating procedures
4. **Monitor Performance**: Watch how the bot performs under normal operations
5. **Security Audit**: Review access logs regularly

---

## 📞 Support

If you encounter issues:

1. **Check Logs**: `docker-compose logs telegram_manager`
2. **Verify Configuration**: Review `.env` file
3. **Test Docker Access**: `docker exec telegram_c2 docker ps`
4. **Restart Services**: `docker-compose restart telegram_manager`

---

## 🎖️ Command Center is Ready

Your professional Command & Control layer is now fully operational. You have tactical oversight and control of your entire trading infrastructure from anywhere via Telegram.

**Stay operational. Stay in control.**

```
█████╗ ██╗     ██████╗ ██╗  ██╗ █████╗     ██████╗██████╗
██╔══██╗██║     ██╔══██╗██║  ██║██╔══██╗   ██╔════╝╚════██╗
███████║██║     ██████╔╝███████║███████║   ██║      █████╔╝
██╔══██║██║     ██╔═══╝ ██╔══██║██╔══██║   ██║     ██╔═══╝
██║  ██║███████╗██║     ██║  ██║██║  ██║   ╚██████╗███████╗
╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝    ╚═════╝╚══════╝
```
