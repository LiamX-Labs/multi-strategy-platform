# ALPHA C2 - System Architecture

## Overview

The Command Center operates as an independent service that communicates with the Docker daemon to control all trading systems and infrastructure components.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         TELEGRAM CLOUD                          │
│                     (Telegram Bot API Servers)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTPS / WebSockets
                             │ (Bot API Protocol)
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      YOUR TELEGRAM CLIENT                       │
│                    (Mobile / Desktop / Web)                     │
│                                                                 │
│  User Interface:                                                │
│  • Command input: /sitrep, /deploy alpha, etc.                 │
│  • Interactive buttons: DEPLOY ALL, KILLSWITCH, etc.           │
│  • Status displays: System reports, diagnostics, logs          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Telegram Bot API
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DOCKER HOST (Your Server)                      │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │          telegram_manager Container (C2 Bot)              │ │
│  │                                                           │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │  bot.py (Python Application)                        │ │ │
│  │  │                                                      │ │ │
│  │  │  ┌────────────────┐  ┌────────────────────────────┐ │ │ │
│  │  │  │ Authorization  │  │  Command Handlers          │ │ │ │
│  │  │  │ • Check user   │  │  • /cc - Main menu         │ │ │ │
│  │  │  │   ID against   │  │  • /sitrep - Status        │ │ │ │
│  │  │  │   ADMIN_IDS    │  │  • /deploy - Start system  │ │ │ │
│  │  │  │ • Log access   │  │  • /terminate - Stop       │ │ │ │
│  │  │  │   attempts     │  │  • /reboot - Restart       │ │ │ │
│  │  │  │ • Deny unknown │  │  • /intel - Logs           │ │ │ │
│  │  │  │   users        │  │  • /diagnostics - Health   │ │ │ │
│  │  │  └────────────────┘  │  • /execute - Run commands │ │ │ │
│  │  │                      │  • /killswitch - Emergency │ │ │ │
│  │  │                      └────────────────────────────┘ │ │ │
│  │  │                                                      │ │ │
│  │  │  ┌────────────────────────────────────────────────┐ │ │ │
│  │  │  │  Docker SDK Client (python-docker)             │ │ │ │
│  │  │  │  • containers.get(name)                        │ │ │ │
│  │  │  │  • container.start()                           │ │ │ │
│  │  │  │  • container.stop()                            │ │ │ │
│  │  │  │  • container.restart()                         │ │ │ │
│  │  │  │  • container.logs()                            │ │ │ │
│  │  │  │  • container.stats()                           │ │ │ │
│  │  │  │  • container.exec_run(command)                 │ │ │ │
│  │  │  └─────────────────┬──────────────────────────────┘ │ │ │
│  │  └────────────────────┼────────────────────────────────┘ │ │
│  │                       │                                  │ │
│  │                       │ Docker API calls via socket      │ │
│  │                       │                                  │ │
│  └───────────────────────┼──────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │       /var/run/docker.sock (Docker Daemon Socket)      │ │
│  │                    (Mounted Read-Only)                  │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           │                                   │
│                           │ Container Management API          │
│                           │                                   │
│           ┌───────────────┼───────────────┐                  │
│           │               │               │                  │
│           ▼               ▼               ▼                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   ALPHA     │  │   BRAVO     │  │  CHARLIE    │         │
│  │   SYSTEM    │  │   SYSTEM    │  │   SYSTEM    │         │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤         │
│  │ Container:  │  │ Container:  │  │ Container:  │         │
│  │ shortseller │  │   lxalgo    │  │  momentum   │         │
│  │   _trading  │  │  _trading   │  │  _trading   │         │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤         │
│  │ Process:    │  │ Process:    │  │ Process:    │         │
│  │ start_      │  │   main.py   │  │ trading_    │         │
│  │ trading.py  │  │             │  │ system.py   │         │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤         │
│  │ Status:     │  │ Status:     │  │ Status:     │         │
│  │ Running     │  │ Running     │  │ Stopped     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│           │                              │                  │
│           ▼                              ▼                  │
│  ┌─────────────────┐           ┌─────────────────┐         │
│  │  DATABASE CORE  │           │   CACHE CORE    │         │
│  ├─────────────────┤           ├─────────────────┤         │
│  │ Container:      │           │ Container:      │         │
│  │ shortseller_    │           │ shortseller_    │         │
│  │ postgres        │           │ redis           │         │
│  ├─────────────────┤           ├─────────────────┤         │
│  │ PostgreSQL 14   │           │ Redis 6         │         │
│  │ Port: 5433      │           │ Port: 6379      │         │
│  ├─────────────────┤           ├─────────────────┤         │
│  │ Volumes:        │           │ Volumes:        │         │
│  │ - postgres_data │           │ - redis_data    │         │
│  └─────────────────┘           └─────────────────┘         │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              trading-network (Docker Bridge)          │  │
│  │  All containers connected for inter-service comms     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Flow Examples

### 1. Deploy System Command

```
User → Telegram → Bot API → C2 Bot → Docker Socket → Container Start

1. User sends: "/deploy alpha"
2. Telegram delivers to bot via Bot API
3. C2 bot validates authorization
4. bot.py calls: docker_client.containers.get('shortseller_trading').start()
5. Docker daemon starts container
6. C2 bot confirms: "🚀 DEPLOYED - ALPHA SYSTEM is now operational"
```

### 2. Status Check (SITREP)

```
User → Telegram → Bot API → C2 Bot → Docker Socket → Container Info

1. User sends: "/sitrep"
2. C2 bot iterates through all systems
3. For each: docker_client.containers.get(name).status
4. For running containers: .stats() for CPU/memory
5. Formats tactical report
6. Returns to user via Telegram
```

### 3. View Logs

```
User → Telegram → Bot API → C2 Bot → Docker Socket → Container Logs

1. User sends: "/intel alpha 100"
2. C2 bot calls: container.logs(tail=100)
3. Receives log output from container
4. Formats and chunks for Telegram
5. Sends back to user
```

### 4. Emergency Killswitch

```
User → Telegram → Bot API → C2 Bot → Docker Socket → Multiple Containers

1. User sends: "/killswitch CONFIRM"
2. C2 bot validates confirmation
3. Loops through trading systems: alpha, bravo, charlie
4. For each: docker_client.containers.get(name).stop(timeout=10)
5. Reports results for each system
6. Logs emergency action
```

---

## Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Telegram User Authentication                      │
│ • Only authorized Telegram user IDs in ADMIN_IDS           │
│ • Unauthorized users receive "ACCESS DENIED"               │
│ • All access attempts logged                               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Command Authorization                             │
│ • @authorized_only decorator on all command handlers       │
│ • Pre-execution validation                                 │
│ • Logging of all authorized actions                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Docker Socket Security                            │
│ • Socket mounted read-only (:ro)                           │
│ • No daemon configuration changes allowed                  │
│ • Limited to container lifecycle operations                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Confirmation Requirements                         │
│ • Destructive operations require explicit confirmation     │
│ • Killswitch requires "CONFIRM" parameter                  │
│ • Interactive buttons show confirmation dialogs            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Audit Logging                                     │
│ • All commands logged with timestamp                       │
│ • User identification in logs                              │
│ • Persistent storage in logs/command_center.log            │
└─────────────────────────────────────────────────────────────┘
```

---

## Network Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  Docker Bridge Network                       │
│                   (trading-network)                          │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  telegram  │  │   alpha    │  │   bravo    │            │
│  │  _manager  │  │  system    │  │  system    │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  charlie   │  │  database  │  │   cache    │            │
│  │  system    │  │   core     │  │   core     │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│                                                              │
│  All containers can communicate with each other             │
│  DNS resolution by container name                           │
└──────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### Telegram Manager (C2 Bot)
**Responsibilities:**
- Receive and validate user commands
- Authenticate users via Telegram ID
- Translate commands to Docker operations
- Format and return results
- Log all operations

**Does NOT:**
- Execute trading logic
- Modify trading strategies
- Access trading positions directly
- Make trading decisions

### Trading Systems (Alpha, Bravo, Charlie)
**Responsibilities:**
- Execute trading strategies
- Manage positions
- Monitor markets
- Execute trades

**Managed by C2:**
- Start/stop/restart operations
- Health monitoring
- Log access
- Resource monitoring

### Infrastructure (Database, Cache)
**Responsibilities:**
- Data persistence (PostgreSQL)
- High-speed caching (Redis)
- Support trading systems

**Managed by C2:**
- Start/stop/restart operations
- Health monitoring
- Direct query execution via /execute

---

## State Management

```
User Commands → C2 Bot → Docker API → Container State Changes

Container States:
┌─────────┐     deploy      ┌─────────┐
│         │ ──────────────> │         │
│ Stopped │                 │ Running │
│         │ <────────────── │         │
└─────────┘    terminate    └─────────┘
     │                           │
     │          reboot           │
     └───────────────────────────┘
            (stop then start)

C2 Bot monitors and reports these state transitions
```

---

## Error Handling

```
User Command
     │
     ▼
Authorization Check
     │
     ├─ PASS ──> Execute Command
     │               │
     │               ├─ SUCCESS ──> Confirm to User
     │               │
     │               └─ FAIL ──> Error Message + Log
     │
     └─ FAIL ──> "ACCESS DENIED" + Log Attempt
```

---

## Logging Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Logging System                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Application Logs (bot.py)                           │  │
│  │  • Command execution                                 │  │
│  │  • Authorization checks                              │  │
│  │  • Error conditions                                  │  │
│  │  • System operations                                 │  │
│  └─────────────────┬────────────────────────────────────┘  │
│                    │                                        │
│                    ├──> Console (STDOUT)                    │
│                    │    • Real-time monitoring              │
│                    │    • Docker logs command               │
│                    │                                        │
│                    └──> File (logs/command_center.log)      │
│                         • Persistent storage                │
│                         • Audit trail                       │
│                         • Historical analysis               │
└─────────────────────────────────────────────────────────────┘
```

---

## Resource Management

```
Container: telegram_manager
├─ CPU: Shared (no limit)
├─ Memory: 256MB limit, 128MB reservation
├─ Disk: Minimal (logs + code)
└─ Network: trading-network bridge

Docker Socket Access:
├─ Read container states
├─ Start/stop/restart containers
├─ Read logs
├─ Execute commands
└─ Query stats

No Access To:
├─ Modify daemon config
├─ Create networks
├─ Build images (from C2)
└─ Delete volumes
```

---

## Command Processing Flow

```
1. Telegram Message Received
         │
         ▼
2. Parse Command & Arguments
         │
         ▼
3. Authorization Check (@authorized_only)
         │
         ├─ FAIL ──> Log + Deny
         │
         ▼ PASS
4. Validate System ID (if applicable)
         │
         ▼
5. Execute Docker Operation
         │
         ├─ container.start()
         ├─ container.stop()
         ├─ container.restart()
         ├─ container.logs()
         ├─ container.stats()
         └─ container.exec_run()
         │
         ▼
6. Format Response
         │
         ▼
7. Send to Telegram
         │
         ▼
8. Log Operation
```

---

## Interactive Button Flow

```
User Clicks Button → Callback Query → C2 Bot Handler

Example: "DEPLOY ALL" button
1. User clicks button
2. Telegram sends callback_query with data='deploy_all'
3. button_callback() handler receives query
4. Validates authorization
5. Calls handle_deploy_all()
6. Loops through all systems
7. Starts each container
8. Collects results
9. Formats report
10. Edits original message with results
```

---

## Failure Modes & Recovery

### C2 Bot Crashes
```
Impact: Cannot control systems via Telegram
Recovery: docker-compose restart telegram_manager
Systems: Trading systems continue running independently
```

### Trading System Crashes
```
Detection: /sitrep shows system as "exited" or offline
Recovery: /deploy <system> or /reboot <system>
Data: Database and cache maintain state
```

### Docker Daemon Failure
```
Impact: All containers stop
Recovery: Restart Docker daemon
C2: Automatically restarts (restart: unless-stopped)
```

### Network Issues
```
C2 to Telegram: Bot cannot receive/send messages
Recovery: Automatic reconnection when network restored
Trading: Systems continue operating independently
```

---

## Performance Considerations

### Response Times
- Simple commands (deploy/terminate): < 2 seconds
- Status checks (/sitrep): 2-5 seconds (depends on system count)
- Logs (/intel): 1-3 seconds (depends on log size)
- Diagnostics: 3-6 seconds (requires stats collection)

### Resource Usage
- C2 Bot: ~50-100MB RAM (lightweight)
- CPU: Minimal (mostly idle, spikes on commands)
- Network: Minimal (only Telegram API + Docker socket)

### Scalability
- Can manage unlimited containers
- Performance degrades linearly with container count
- Telegram rate limits apply (30 messages/second)

---

## Monitoring the Monitor

### Health Checks
```bash
# Is C2 running?
docker ps | grep telegram_c2

# C2 resource usage
docker stats telegram_c2

# C2 logs
docker logs -f telegram_c2

# Is bot responding to Telegram?
Send /cc in Telegram
```

### Metrics to Track
- Command response time
- Authorization failures
- Docker API errors
- System restart frequency
- Uptime

---

## Integration Points

### With Trading Systems
- Lifecycle management (start/stop/restart)
- Log collection
- Health monitoring
- Resource usage tracking

### With Infrastructure
- Database: Direct SQL query execution
- Cache: Redis command execution
- Docker: Full container management API

### With External Services
- Telegram: Bot API for messaging
- User: Authentication via Telegram ID

---

This architecture provides a secure, scalable, and professional command and control system for managing your entire trading infrastructure from anywhere via Telegram.
