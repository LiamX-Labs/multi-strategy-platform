# 🚨 CRITICAL: Bybit Demo vs Testnet Configuration

**Date Created:** 2025-10-24
**Issue:** WebSocket listener was connecting to TESTNET instead of DEMO

---

## ⚠️ THE PROBLEM

Bybit has **THREE** different environments:
1. **Mainnet** (Real money, production trading)
2. **Testnet** (Free test coins, for testing with fake money)
3. **Demo** (Paper trading with simulated positions, NO actual API orders)

**We are using DEMO mode, NOT Testnet!**

---

## 🔑 KEY DIFFERENCES

| Feature | Testnet | Demo |
|---------|---------|------|
| API Endpoint | `https://api-testnet.bybit.com` | `https://api-demo.bybit.com` |
| WebSocket | `wss://stream-testnet.bybit.com` | `wss://stream-demo.bybit.com` |
| Account Type | Free testnet account | Regular account with demo mode |
| API Keys | Separate testnet keys | Regular API keys with `BYBIT_DEMO=true` |
| Order Execution | Real API orders (testnet) | Simulated locally (no actual orders) |
| Positions | Real positions on testnet | Simulated in memory |

---

## 🎯 OUR CONFIGURATION

### Current Setup:
- **BYBIT_DEMO=true** in all bot .env files
- **API credentials** are from REGULAR Bybit account (not testnet)
- **All bots** are configured for demo mode
- **WebSocket listener** should connect to DEMO endpoint

### Correct Settings:

```bash
# In .env and docker-compose files:
BYBIT_TESTNET=false          # ❌ NOT testnet!
BYBIT_DEMO=true              # ✅ Demo mode
BYBIT_API_KEY=<your_key>     # Regular account API key
BYBIT_API_SECRET=<secret>    # Regular account secret
```

### WebSocket Endpoints:

```python
# WRONG (Testnet):
wss://stream-testnet.bybit.com/v5/private

# CORRECT (Demo):
wss://stream-demo.bybit.com/v5/private
```

---

## 🔧 WHAT NEEDS TO BE FIXED

### 1. WebSocket Listener Code
File: `websocket_listener/listener.py`

The listener needs to:
- Check `BYBIT_DEMO` environment variable
- Use demo WebSocket endpoint when demo=true
- Use regular/testnet endpoint when demo=false

### 2. Environment Variables
File: `docker-compose.production.yml`

```yaml
environment:
  - BYBIT_TESTNET=false  # NOT testnet
  - BYBIT_DEMO=true      # Demo mode
```

### 3. All Bot Configurations
All bots (shortseller, lxalgo, momentum) already have:
```bash
BYBIT_DEMO=true
```

This is CORRECT - keep this.

---

## 📋 HOW TO VERIFY YOU'RE IN DEMO MODE

1. **Check bot logs** - should say "Demo mode enabled" or similar
2. **Check WebSocket URL** - should be `stream-demo.bybit.com`
3. **Place a test order** - should NOT appear in Bybit UI (it's simulated)
4. **Check positions** - managed locally in Redis, not on Bybit

---

## 🛠️ IMPLEMENTATION NOTES

### Demo Mode Behavior:
- Bots calculate signals normally
- Bots "place orders" but DON'T send to Bybit API
- Bots simulate fills based on market price
- Positions tracked in Redis only
- P&L calculated from simulated trades

### WebSocket Listener Behavior:
**CRITICAL DECISION NEEDED:**

Since we're in DEMO mode and NOT sending real orders to Bybit:
- **Do we even need the WebSocket listener?**
- Answer: NO for demo, YES for later production

**For now (demo mode):**
- WebSocket listener is OPTIONAL
- Bots simulate their own fills
- Can skip WebSocket authentication issues

**For future (production):**
- WebSocket listener is CRITICAL
- Must use correct endpoint (testnet or mainnet)
- Must have valid API credentials

---

## ✅ ACTION ITEMS

1. ✅ Document this difference (this file)
2. ⏸️ Decide: Continue without WebSocket for demo mode?
3. ⏸️ Or: Fix WebSocket to use demo endpoint
4. ⏸️ Update deployment docs to clarify demo vs testnet

---

## 📚 REFERENCES

- Bybit Demo Trading: https://www.bybit.com/en/help-center/article/Demo-Trading
- Bybit Testnet: https://testnet.bybit.com
- Bybit API Docs: https://bybit-exchange.github.io/docs/v5/intro

---

**Last Updated:** 2025-10-24
**Status:** WebSocket listener currently trying testnet, needs demo endpoint
