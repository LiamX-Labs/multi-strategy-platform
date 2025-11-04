# ALPHA C2 - Command & Control Center

Professional Telegram-based Command Center for managing your trading infrastructure.

## System Designation

- **ALPHA SYSTEM** - Multi-Asset Short Seller (shortseller)
- **BRAVO SYSTEM** - LX Algorithm Executor (lxalgo)
- **CHARLIE SYSTEM** - Momentum Strategy Engine (momentum)
- **DATABASE CORE** - PostgreSQL Database
- **CACHE CORE** - Redis Cache Layer

## Command Reference

### Situation Awareness
```
/cc                     - Command Center (Main Menu)
/sitrep                 - Full System Status Report
/diagnostics <system>   - Detailed System Diagnostics
```

### System Control
```
/deploy <system>        - Deploy (Start) System
/terminate <system>     - Terminate (Stop) System
/reboot <system>        - Reboot (Restart) System
```

### Intelligence Gathering
```
/intel <system> [lines] - View System Logs
/execute <system> <cmd> - Execute Command in System
```

### Mass Operations
```
/deploy_all            - Deploy All Systems
/terminate_all         - Shutdown All Systems
/reboot_all            - Restart All Systems
```

### Emergency Operations
```
/killswitch CONFIRM    - Emergency Trading Halt (Trading Systems Only)
```

### Help
```
/help                  - Display Command Reference
```

## System Identifiers

### Trading Systems
- `alpha` - Multi-Asset Short Seller
- `bravo` - LX Algorithm
- `charlie` - Momentum Strategy

### Infrastructure
- `database` - PostgreSQL Core
- `cache` - Redis Cache

## Setup Instructions

### 1. Get Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow the prompts to create your bot
4. Copy the token you receive

### 2. Get Your Telegram User ID

1. Open Telegram and search for `@userinfobot`
2. Send any message
3. Copy your user ID

### 3. Configure Environment

Create `.env` file in this directory:

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ADMIN_IDS=123456789,987654321
```

Multiple admin IDs can be comma-separated.

### 4. Deploy Command Center

From the main project directory:

```bash
docker-compose up -d telegram_manager
```

### 5. Verify Operation

```bash
# Check logs
docker-compose logs -f telegram_manager

# Check status
docker ps | grep telegram_c2
```

### 6. Start Using

Open Telegram, find your bot, and send:
```
/cc
```

## Example Usage

### Deploy Specific System
```
/deploy alpha
```
Response: `🚀 DEPLOYED - ALPHA SYSTEM is now operational.`

### Check Status
```
/sitrep
```
Displays full tactical overview of all systems.

### View Logs
```
/intel bravo 100
```
Shows last 100 lines from BRAVO system.

### Execute Command
```
/execute charlie ls -la /app
```
Executes command in CHARLIE system container.

### Emergency Shutdown
```
/killswitch CONFIRM
```
Immediately terminates all trading systems.

## Security Features

- **Authorization**: Only configured user IDs can access
- **Logging**: All commands and access attempts logged
- **Read-Only Docker Socket**: Mounted as `:ro` for safety
- **Command Confirmation**: Destructive operations require confirmation
- **No Trading Logic**: Bot only manages containers, never touches trading code

## Interactive Buttons

The bot provides an interactive menu system:

- **📊 TACTICAL OVERVIEW** - View all systems status
- **🚀 DEPLOY ALL** - Start all systems
- **🔴 KILL SWITCH** - Emergency shutdown
- **⚡ TRADING SYSTEMS** - Control individual trading systems
- **🔧 INFRASTRUCTURE** - Manage database and cache
- **📡 SYSTEM LOGS** - View logs for any system
- **⚙️ ADVANCED OPS** - Mass operations menu

## Monitoring

The bot provides real-time monitoring:
- Container status (running/stopped)
- CPU usage
- Memory usage
- Network I/O
- Uptime information

## Troubleshooting

### Bot not responding
```bash
docker-compose logs telegram_manager
```

### Permission denied on Docker socket
Ensure docker-compose.yml has:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

### Unauthorized access
Verify your Telegram user ID is in `TELEGRAM_ADMIN_IDS` in `.env`

## Advanced Features

### Database Queries
You can execute SQL queries through the bot:
```
/execute database psql -U trading_user -d multiasset_trading -c "SELECT COUNT(*) FROM trades"
```

### Check Redis Cache
```
/execute cache redis-cli INFO
```

### View Container Resources
```
/diagnostics alpha
```

## Log Files

Command Center logs are stored in:
```
./telegram_manager/logs/command_center.log
```

## Updates & Maintenance

To update the bot:
```bash
docker-compose restart telegram_manager
```

To rebuild after code changes:
```bash
docker-compose build telegram_manager
docker-compose up -d telegram_manager
```

## Architecture

```
┌─────────────────────┐
│  Telegram Bot API   │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  telegram_manager   │
│   (Command Center)  │
└──────────┬──────────┘
           │
    ┌──────▼──────┐
    │ Docker API  │
    └──────┬──────┘
           │
    ┌──────▼──────────────────────┐
    │                             │
┌───▼────┐  ┌──────┐  ┌────────┐ │
│ ALPHA  │  │BRAVO │  │CHARLIE │ │
│ System │  │System│  │ System │ │
└────────┘  └──────┘  └────────┘ │
                                 │
┌──────────┐  ┌──────────┐      │
│ Database │  │  Cache   │      │
│   Core   │  │   Core   │      │
└──────────┘  └──────────┘      │
                                 │
└─────────────────────────────────┘
```

## Support

For issues or questions:
1. Check logs: `docker-compose logs telegram_manager`
2. Verify environment variables in `.env`
3. Ensure Docker socket is accessible
4. Confirm Telegram bot token is valid
