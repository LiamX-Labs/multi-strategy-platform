# Quick Start - Command Center Security

## 🚀 Immediate Setup (3 Steps)

### Step 1: Set Your Access Code

Add to your `.env` file:

```bash
C2_ACCESS_CODE=YourSecureAccessCode2025
```

**⚠️ IMPORTANT**: Change from the default `ALPHA2025`!

### Step 2: Restart Telegram Manager

```bash
docker compose -f docker-compose.production.yml restart telegram_manager
```

### Step 3: Authenticate in Telegram

Send to your bot:

```
/auth YourSecureAccessCode2025
```

✅ You'll get: "AUTHENTICATION SUCCESSFUL"

---

## 📱 Daily Usage

### Login
```
/auth YourAccessCode
```

### Check Session
```
/status
```
Shows: Session expires in X minutes

### Use Commands
All commands now require active session:
- `/cc` - Command Center
- `/quick` - Quick status
- `/sitrep` - Full report
- etc.

### Logout
```
/logout
```

---

## ⏱️ Session Info

- **Default Timeout**: 30 minutes
- **Auto-refresh**: Each command extends session
- **Lost on Restart**: Sessions cleared when bot restarts

---

## 🔒 Security Layers

1. **User ID Check** → Are you authorized?
2. **Access Code** → Do you know the code?
3. **Session Check** → Is session active?
4. **Message Auto-Delete** → Access code automatically removed

All checks must pass ✅

## 🗑️ Auto-Delete Feature

For maximum security:
- Your `/auth` message is **immediately deleted** after you send it
- Bot responses **self-destruct after 20 seconds** (configurable)
- No trace of access code left in chat history

---

## 🛠️ Configuration Options

```bash
# .env file

# Access code (REQUIRED)
C2_ACCESS_CODE=MyCode2025

# Session timeout (OPTIONAL, default: 30 minutes)
C2_SESSION_TIMEOUT=30

# Auto-delete delay (OPTIONAL, default: 20 seconds)
C2_MESSAGE_DELETE_SECONDS=20

# Your Telegram user ID (REQUIRED)
C2_TELEGRAM_ADMIN_IDS=123456789
```

**Security Levels:**
- **High Security**: `C2_MESSAGE_DELETE_SECONDS=10` (10 seconds)
- **Standard**: `C2_MESSAGE_DELETE_SECONDS=20` (default)
- **Relaxed**: `C2_MESSAGE_DELETE_SECONDS=30` (30 seconds)

---

## ⚠️ Common Issues

### "SESSION EXPIRED"
**Solution**: Run `/auth YourAccessCode` again

### "ACCESS DENIED"
**Cause**: Your Telegram ID not in `TELEGRAM_ADMIN_IDS`
**Solution**: Add your ID to `.env` and restart

### Commands not working
**Check**: Run `/status` to verify active session

---

## 📊 View Logs

```bash
# See all authentication events
docker logs telegram_c2 | grep "AUTH"

# See session activity
docker logs telegram_c2 | grep "SESSION"

# See unauthorized attempts
docker logs telegram_c2 | grep "UNAUTHORIZED"
```

---

## 🎯 Best Practices

✅ Use strong access codes (12+ characters)
✅ Change code every 30 days
✅ Monitor logs for suspicious activity
✅ Logout when done
✅ Set shorter timeout for high-security needs

❌ Don't share access codes
❌ Don't use default `ALPHA2025`
❌ Don't commit `.env` to git

---

## Need Help?

Run `/help` in Telegram for full command list

See `SECURITY_SETUP.md` for detailed documentation
