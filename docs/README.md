# Alpha Trading System Documentation

**Last Updated:** 2025-10-24

---

## 📚 Documentation Structure

```
docs/
├── README.md                          ← You are here
├── DOCUMENTATION_INDEX.md             ← Complete index of all docs
│
├── database/                          ← Database Architecture
│   ├── DATABASE_ARCHITECTURE_CATALOGUE.md
│   ├── DATABASE_IMPLEMENTATION_GUIDE.md
│   ├── DATABASE_PROJECT_SUMMARY.md
│   └── DATABASE_QUICK_START.md
│
├── architecture/                      ← System Architecture
│   ├── COMPLETE_SYSTEM_ARCHITECTURE.md
│   └── ARCHITECTURE_QUICK_REFERENCE.md
│
├── guides/                           ← Implementation Guides
│   ├── tradingsystemguide.md        ← Original trading system guide
│   ├── data.md                       ← Data flow and WebSocket guide
│   └── DOCKER_STARTUP_GUIDE.md
│
├── telegram/                         ← Telegram C2 Documentation
│   ├── C2_IMPLEMENTATION_SUMMARY.md
│   └── COMMAND_CENTER_GUIDE.md
│
└── reference/                        ← Reference Materials
    ├── CONFLICT_RESOLUTION_SUMMARY.md
    ├── IMPLEMENTATION_SUMMARY.md
    └── QUICK_REFERENCE.md
```

---

## 🚀 Quick Start Paths

### New to the System?
1. Read [../README.md](../README.md) - Main project README
2. Read [architecture/COMPLETE_SYSTEM_ARCHITECTURE.md](architecture/COMPLETE_SYSTEM_ARCHITECTURE.md)
3. Follow [database/DATABASE_QUICK_START.md](database/DATABASE_QUICK_START.md)

### Setting Up Database?
1. [database/DATABASE_QUICK_START.md](database/DATABASE_QUICK_START.md) - 30-minute setup
2. [database/DATABASE_IMPLEMENTATION_GUIDE.md](database/DATABASE_IMPLEMENTATION_GUIDE.md) - Full implementation
3. [database/DATABASE_ARCHITECTURE_CATALOGUE.md](database/DATABASE_ARCHITECTURE_CATALOGUE.md) - Technical spec

### Understanding Data Flow?
1. [guides/data.md](guides/data.md) - **CRITICAL: How WebSockets work**
2. [architecture/COMPLETE_SYSTEM_ARCHITECTURE.md](architecture/COMPLETE_SYSTEM_ARCHITECTURE.md)

### Setting Up Telegram C2?
1. [telegram/COMMAND_CENTER_GUIDE.md](telegram/COMMAND_CENTER_GUIDE.md)
2. [telegram/C2_IMPLEMENTATION_SUMMARY.md](telegram/C2_IMPLEMENTATION_SUMMARY.md)

---

## 📖 Documentation by Topic

### Database System
| Document | Purpose | Size |
|----------|---------|------|
| [DATABASE_QUICK_START.md](database/DATABASE_QUICK_START.md) | Get database running in 30 minutes | 12 KB |
| [DATABASE_IMPLEMENTATION_GUIDE.md](database/DATABASE_IMPLEMENTATION_GUIDE.md) | Complete implementation guide | 30 KB |
| [DATABASE_ARCHITECTURE_CATALOGUE.md](database/DATABASE_ARCHITECTURE_CATALOGUE.md) | Full technical specification | 47 KB |
| [DATABASE_PROJECT_SUMMARY.md](database/DATABASE_PROJECT_SUMMARY.md) | Executive summary | 21 KB |

### System Architecture
| Document | Purpose | Size |
|----------|---------|------|
| [COMPLETE_SYSTEM_ARCHITECTURE.md](architecture/COMPLETE_SYSTEM_ARCHITECTURE.md) | Complete system overview | 37 KB |
| [ARCHITECTURE_QUICK_REFERENCE.md](architecture/ARCHITECTURE_QUICK_REFERENCE.md) | Quick lookup guide | 13 KB |

### Implementation Guides
| Document | Purpose | Size |
|----------|---------|------|
| [data.md](guides/data.md) | **WebSocket data flow** | 10 KB |
| [tradingsystemguide.md](guides/tradingsystemguide.md) | Original service hub guide | 20 KB |
| [DOCKER_STARTUP_GUIDE.md](guides/DOCKER_STARTUP_GUIDE.md) | Docker deployment | 8 KB |

### Telegram Command Center
| Document | Purpose | Size |
|----------|---------|------|
| [COMMAND_CENTER_GUIDE.md](telegram/COMMAND_CENTER_GUIDE.md) | Complete C2 guide | 15 KB |
| [C2_IMPLEMENTATION_SUMMARY.md](telegram/C2_IMPLEMENTATION_SUMMARY.md) | Implementation summary | 10 KB |

---

## 🎯 Common Tasks

### I want to...

**Start the system**
→ See [../README.md](../README.md) and [guides/DOCKER_STARTUP_GUIDE.md](guides/DOCKER_STARTUP_GUIDE.md)

**Understand how data flows**
→ Read [guides/data.md](guides/data.md) - **THIS IS CRITICAL**

**Set up the database**
→ Follow [database/DATABASE_QUICK_START.md](database/DATABASE_QUICK_START.md)

**Understand order execution**
→ Read [guides/data.md](guides/data.md) Section 2

**Control bots via Telegram**
→ Follow [telegram/COMMAND_CENTER_GUIDE.md](telegram/COMMAND_CENTER_GUIDE.md)

**Understand the architecture**
→ Read [architecture/COMPLETE_SYSTEM_ARCHITECTURE.md](architecture/COMPLETE_SYSTEM_ARCHITECTURE.md)

**Look up a specific topic**
→ Use [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)

---

## 📁 Project Structure Reference

```
Alpha/
├── docs/                              ← All documentation (you are here)
├── database/                          ← Database files
│   ├── migrations/                    ← SQL migration scripts
│   ├── config/                        ← PostgreSQL, Redis config
│   └── backups/                       ← Database backups
├── shortseller/                       ← EMA crossover bot
├── lxalgo/                           ← LX technical analysis bot
├── momentum/                         ← Volatility breakout bot
├── telegram_manager/                 ← Telegram C2 system
├── docker-compose.yml                ← Main docker config
└── README.md                         ← Main README
```

---

## 🔧 Key Concepts

### The Three Databases
1. **PostgreSQL** - Permanent record (fills, trades history)
2. **Redis** - Live state (current positions, prices)
3. **InfluxDB** - Market context (OHLCV candles) - *Future*

### The Three WebSocket Streams
1. **execution** - Every fill (price, qty, fees)
2. **order** - Order lifecycle (new, filled, cancelled)
3. **position** - Exchange truth (reconciliation)

### The client_order_id System
Every order has a custom ID encoding WHY it was placed:
```
bot_1:entry:1678886400
bot_1:trailing_stop:1678886401
bot_1:take_profit:1678886402
```

This enables performance tracking by close reason.

---

## 📊 Document Status

| Category | Status | Last Updated |
|----------|--------|--------------|
| Database Architecture | ✅ Complete | 2025-10-24 |
| System Architecture | ✅ Complete | 2025-10-24 |
| Data Flow Guide | ✅ Complete | 2025-10-24 |
| Telegram C2 | ✅ Complete | 2025-10-24 |
| Implementation Guides | ✅ Complete | 2025-10-24 |

---

## 📝 Next Steps

1. **Phase 1:** Set up database infrastructure
2. **Phase 2:** Build WebSocket listener service
3. **Phase 3:** Update bot execution logic
4. **Phase 4:** Test and validate
5. **Phase 5:** Deploy to production

See [database/DATABASE_IMPLEMENTATION_GUIDE.md](database/DATABASE_IMPLEMENTATION_GUIDE.md) for detailed steps.

---

**For questions or issues, see the troubleshooting sections in the relevant guides.**
