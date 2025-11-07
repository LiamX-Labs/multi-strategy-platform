# Telegram Command Center - Security Setup

## Overview

The Alpha Command Center now includes a two-layer security system:
1. **Authorization Layer**: Only users in the authorized operators list can access the bot
2. **Authentication Layer**: Users must authenticate with an access code and maintain an active session

## Security Features

### 1. Access Code Authentication
- Users must provide a valid access code to create a session
- Access code is configurable via environment variable
- Failed authentication attempts are logged

### 2. Session Management
- Sessions automatically expire after a configurable timeout (default: 30 minutes)
- Each command refreshes the session timeout
- Users can manually logout to end their session

### 3. Authorization List
- Only users with their Telegram ID in `TELEGRAM_ADMIN_IDS` can attempt authentication
- Unauthorized users are blocked immediately with logged attempts

### 4. Message Auto-Delete (NEW!)
- User's `/auth` message is **immediately deleted** to prevent access code exposure
- Bot responses **self-destruct** after a configurable delay (default: 20 seconds)
- Prevents access code from remaining visible in chat history
- Configurable deletion timing for different security requirements

## Environment Variables

Add these to your `.env` file:

```bash
# Command Center Access Code (CHANGE THIS!)
C2_ACCESS_CODE=YourSecureAccessCode2025

# Session timeout in minutes (default: 30)
C2_SESSION_TIMEOUT=30

# Auto-delete delay for auth messages in seconds (default: 20)
C2_MESSAGE_DELETE_SECONDS=20

# Telegram Bot Token
C2_TELEGRAM_BOT_TOKEN=your_bot_token

# Authorized User IDs (comma-separated)
C2_TELEGRAM_ADMIN_IDS=123456789,987654321
```

## Usage Workflow

### First-Time Setup

1. User sends `/auth <access_code>` to the bot
2. **The message is immediately deleted** (access code not visible in history)
3. Bot responds with success/failure message
4. If authorized and code is correct, a session is created
5. **Bot response self-destructs after 20 seconds** (configurable)
6. User can now access all command center features
7. Session remains active for 30 minutes (or configured timeout)

### Message Auto-Delete Behavior

**What gets deleted:**
- ✅ Your `/auth <code>` message - **Deleted immediately**
- ✅ "Authentication Successful" message - **Deleted after 20s**
- ✅ "Authentication Failed" message - **Deleted after 20s**
- ✅ "Access Denied" message - **Deleted after 20s**
- ✅ "Authentication Required" message - **Deleted after 20s**

**Why this matters:**
- Access codes don't remain in chat history
- Even if someone has physical access to your device, they can't see the code
- Failed attempts are also cleaned up automatically
- Reduces the risk of shoulder surfing or screenshot exposure

### Example Commands

```
/auth ALPHA2025              # Authenticate with access code
/status                      # Check session status
/cc                          # Open Command Center (requires active session)
/sitrep                      # Get situation report (requires active session)
/logout                      # End session
```

## Security Best Practices

### Change the Default Access Code

**IMPORTANT**: The default access code is `ALPHA2025`. You MUST change this in production!

1. Open your `.env` file
2. Add or update: `C2_ACCESS_CODE=YourSecureCodeHere`
3. Restart the telegram_manager container

```bash
docker compose -f docker-compose.production.yml restart telegram_manager
```

### Manage Session Timeout

Adjust timeout based on your security requirements:

- **High Security**: Set to 15 minutes (`C2_SESSION_TIMEOUT=15`)
- **Moderate Security**: Set to 30 minutes (default)
- **Convenience**: Set to 60 minutes (`C2_SESSION_TIMEOUT=60`)

### Adjust Auto-Delete Timing

Configure how quickly auth messages are deleted:

- **High Security**: `C2_MESSAGE_DELETE_SECONDS=10` (10 seconds - very fast)
- **Standard Security**: `C2_MESSAGE_DELETE_SECONDS=20` (default - 20 seconds)
- **Relaxed**: `C2_MESSAGE_DELETE_SECONDS=30` (30 seconds - more time to read)

**Note**: User's message containing the access code is **always deleted immediately**, regardless of this setting. This setting only affects bot response messages.

### Monitor Access Attempts

All authentication events are logged:

```bash
docker logs telegram_c2 | grep "AUTH"
```

Log entries include:
- ✓ Successful authentications
- ❌ Failed authentication attempts
- ⚠️ Expired session warnings
- ❌ Unauthorized access attempts

## Commands Reference

### Authentication Commands (No Session Required)

| Command | Description |
|---------|-------------|
| `/auth <code>` | Authenticate with access code |
| `/logout` | End your session |
| `/status` | Check session status and remaining time |

### Protected Commands (Require Active Session)

All other commands require an active session:

- `/cc` - Command Center main menu
- `/sitrep` - System status report
- `/deploy <system>` - Deploy systems
- `/terminate <system>` - Stop systems
- `/quick` - Quick analytics
- `/analytics` - Full analytics report
- And all other operational commands...

## Implementation Details

### Session Storage

Sessions are stored in memory with the following structure:

```python
active_sessions = {
    user_id: last_activity_timestamp
}
```

**Note**: Sessions are lost on bot restart. This is intentional for security.

### Decorator Usage

Two decorators are available:

1. **`@requires_authentication`**: Checks both authorization AND active session
   - Used for all operational commands
   - Returns "SESSION EXPIRED" if no active session

2. **`@authorized_only`**: Checks only authorization (no session required)
   - Used for authentication commands themselves
   - Returns "ACCESS DENIED" if not in authorized list

### Security Flow

```
User sends command
    ↓
Check if user in ADMIN_IDS
    ↓ NO → ACCESS DENIED
    ↓ YES
Check if session active
    ↓ NO → SESSION EXPIRED (redirect to /auth)
    ↓ YES
Check if session expired
    ↓ YES → SESSION EXPIRED (session deleted)
    ↓ NO
Execute command & refresh session
```

## Troubleshooting

### "SESSION EXPIRED" after authentication

- Sessions expire after the configured timeout (default 30 minutes)
- Run `/auth <access_code>` again to create a new session
- Check `/status` to see remaining session time

### "ACCESS DENIED" message

- Your Telegram user ID is not in `TELEGRAM_ADMIN_IDS`
- Contact administrator to add your ID to the authorized list
- Find your Telegram ID: Send a message to [@userinfobot](https://t.me/userinfobot)

### Access code not working

- Ensure you're using the correct access code from `.env`
- Check if `C2_ACCESS_CODE` is set in the environment
- Default code is `ALPHA2025` if not configured
- Access codes are case-sensitive

### Session expires too quickly/slowly

- Adjust `C2_SESSION_TIMEOUT` in `.env`
- Value is in minutes
- Restart telegram_manager after changing

## Example .env Configuration

```bash
# ==============================================
# TELEGRAM COMMAND CENTER SECURITY
# ==============================================

# Access Code (CHANGE THIS IN PRODUCTION!)
C2_ACCESS_CODE=MySecure2025Code!@#

# Session timeout in minutes
C2_SESSION_TIMEOUT=30

# Telegram Bot Configuration
C2_TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
C2_TELEGRAM_ADMIN_IDS=123456789

# ==============================================
```

## Audit Log Example

Successful authentication:
```
2025-11-06 04:55:23 - [INFO] - ✓ SESSION CREATED: User ID 123456789
2025-11-06 04:55:23 - [INFO] - ✓ AUTHENTICATION SUCCESS: User LiamX (ID: 123456789)
```

Failed attempt:
```
2025-11-06 04:56:45 - [WARNING] - ❌ FAILED AUTH ATTEMPT: User Unknown (ID: 987654321) - Wrong code
```

Unauthorized access:
```
2025-11-06 04:57:10 - [WARNING] - ❌ UNAUTHORIZED ACCESS: User Hacker (ID: 111222333)
```

## Security Recommendations

1. **Change Default Access Code**: Never use the default `ALPHA2025` in production
2. **Use Strong Access Codes**: Minimum 12 characters, mix of letters, numbers, symbols
3. **Rotate Access Codes**: Change periodically (monthly recommended)
4. **Monitor Logs**: Regularly check for unauthorized access attempts
5. **Limit Admin List**: Only add trusted users to `TELEGRAM_ADMIN_IDS`
6. **Set Appropriate Timeout**: Balance security and convenience
7. **Secure .env File**: Ensure `.env` has restricted permissions (600)

```bash
chmod 600 .env
```

## FAQ

**Q: Can multiple users share the same access code?**
A: Yes, the access code is shared among all authorized users. Each user maintains their own session.

**Q: What happens if I restart the telegram_manager container?**
A: All active sessions are lost. Users must re-authenticate.

**Q: Can I have different access codes for different users?**
A: Not in the current implementation. All authorized users use the same code. Consider implementing user-specific codes for enhanced security.

**Q: How do I rotate the access code?**
A: Update `C2_ACCESS_CODE` in `.env` and restart telegram_manager. All users will need the new code.

**Q: Is the access code encrypted?**
A: The code is stored as an environment variable. Use strong access control on the server and `.env` file.

## Future Enhancements

Consider implementing:
- User-specific access codes
- Multi-factor authentication (MFA)
- Session persistence to database
- IP-based restrictions
- Rate limiting on authentication attempts
- Audit log export functionality
- Telegram callback query authentication
