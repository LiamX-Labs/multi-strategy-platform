#!/usr/bin/env python3
"""
█████╗ ██╗     ██████╗ ██╗  ██╗ █████╗     ██████╗██████╗
██╔══██╗██║     ██╔══██╗██║  ██║██╔══██╗   ██╔════╝╚════██╗
███████║██║     ██████╔╝███████║███████║   ██║      █████╔╝
██╔══██║██║     ██╔═══╝ ██╔══██║██╔══██║   ██║     ██╔═══╝
██║  ██║███████╗██║     ██║  ██║██║  ██║   ╚██████╗███████╗
╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝    ╚═════╝╚══════╝

TACTICAL COMMAND CENTER
Trading Operations Management System
"""

import os
import logging
import docker
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# Import analytics handlers
try:
    from analytics_handlers import (
        analytics_summary,
        positions_summary,
        trades_history,
        daily_performance,
        cache_stats,
        quick_status
    )
    ANALYTICS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Analytics handlers not available: {e}")
    ANALYTICS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/app/logs/command_center.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('TELEGRAM_ADMIN_IDS', '').split(',') if id.strip()]

# Security Configuration
ACCESS_CODE = os.getenv('COMMAND_CENTER_ACCESS_CODE', 'ALPHA2025')  # Default code, should be changed
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT_MINUTES', '30'))  # Session expires after 30 minutes
MESSAGE_DELETE_DELAY = int(os.getenv('AUTH_MESSAGE_DELETE_SECONDS', '20'))  # Auto-delete auth messages after N seconds

# Active sessions: {user_id: last_activity_timestamp}
active_sessions = {}

# Docker client
docker_client = docker.from_env()

# System mappings - Military style designation
# Container names match docker-compose.production.yml
SYSTEMS = {
    'alpha': {
        'container': 'shortseller_trading',
        'name': 'ALPHA SYSTEM',
        'description': 'Multi-Asset Short Seller',
        'type': 'trading'
    },
    'bravo': {
        'container': 'lxalgo_trading',
        'name': 'BRAVO SYSTEM',
        'description': 'LX Algorithm Executor',
        'type': 'trading'
    },
    'charlie': {
        'container': 'momentum_trading',
        'name': 'CHARLIE SYSTEM',
        'description': 'Momentum Strategy Engine',
        'type': 'trading'
    },
    'database': {
        'container': 'trading_postgres',  # Production uses trading_postgres
        'name': 'DATABASE CORE',
        'description': 'PostgreSQL Database',
        'type': 'infrastructure'
    },
    'pgbouncer': {
        'container': 'trading_pgbouncer',  # Production connection pooler
        'name': 'PGBOUNCER',
        'description': 'PostgreSQL Connection Pooler',
        'type': 'infrastructure'
    },
    'cache': {
        'container': 'trading_redis',  # Production uses trading_redis
        'name': 'CACHE CORE',
        'description': 'Redis Cache Layer',
        'type': 'infrastructure'
    },
    'websocket': {
        'container': 'trading_websocket_listener',  # Production WebSocket listener
        'name': 'WEBSOCKET LISTENER',
        'description': 'Bybit WebSocket Stream Handler',
        'type': 'infrastructure'
    }
}

# System groups for bulk operations
TRADING_SYSTEMS = ['alpha', 'bravo', 'charlie']
INFRASTRUCTURE_SYSTEMS = ['database', 'pgbouncer', 'cache', 'websocket']
ALL_SYSTEMS = list(SYSTEMS.keys())


# ========================================
# AUTHORIZATION & SECURITY
# ========================================

def is_session_active(user_id: int) -> bool:
    """Check if user has an active session"""
    if user_id not in active_sessions:
        return False

    # Check if session has expired
    last_activity = active_sessions[user_id]
    elapsed_minutes = (datetime.now() - last_activity).total_seconds() / 60

    if elapsed_minutes > SESSION_TIMEOUT:
        # Session expired
        del active_sessions[user_id]
        return False

    return True


def refresh_session(user_id: int):
    """Refresh user session timestamp"""
    active_sessions[user_id] = datetime.now()


def create_session(user_id: int):
    """Create a new session for user"""
    active_sessions[user_id] = datetime.now()
    logger.info(f"✓ SESSION CREATED: User ID {user_id}")


def end_session(user_id: int):
    """Terminate user session"""
    if user_id in active_sessions:
        del active_sessions[user_id]
        logger.info(f"✓ SESSION ENDED: User ID {user_id}")


def requires_authentication(func):
    """Decorator that requires both authorization and active session"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        # First check: Is user in authorized list?
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "⛔ *ACCESS DENIED*\n\n"
                "Security clearance required.\n"
                "Unauthorized access attempt logged.",
                parse_mode='Markdown'
            )
            logger.warning(f"❌ UNAUTHORIZED ACCESS: User {username} (ID: {user_id})")
            return

        # Second check: Does user have an active session?
        if not is_session_active(user_id):
            await update.message.reply_text(
                "🔐 *SESSION EXPIRED*\n\n"
                "Your session has expired or you haven't authenticated yet.\n"
                "Please use `/auth <access_code>` to authenticate.\n\n"
                f"Example: `/auth {ACCESS_CODE[:4]}****`",
                parse_mode='Markdown'
            )
            logger.warning(f"⚠️ SESSION EXPIRED: User {username} (ID: {user_id})")
            return

        # Refresh session on each command
        refresh_session(user_id)
        logger.info(f"✓ AUTHENTICATED: {username} (ID: {user_id}) - Command: {update.message.text}")
        return await func(update, context)
    return wrapper


def authorized_only(func):
    """Security clearance check - Restrict to authorized operators only"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "⛔ *ACCESS DENIED*\n\n"
                "Security clearance required.\n"
                "Unauthorized access attempt logged.",
                parse_mode='Markdown'
            )
            logger.warning(f"❌ UNAUTHORIZED ACCESS: User {username} (ID: {user_id})")
            return

        logger.info(f"✓ AUTHORIZED: {username} (ID: {user_id}) - Command: {update.message.text}")
        return await func(update, context)
    return wrapper


# ========================================
# CORE COMMAND HANDLERS
# ========================================

@requires_authentication
async def command_center(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main command center interface"""
    keyboard = [
        [InlineKeyboardButton("📊 TACTICAL OVERVIEW", callback_data='sitrep')],
        [
            InlineKeyboardButton("🚀 DEPLOY ALL", callback_data='deploy_all'),
            InlineKeyboardButton("🔴 KILL SWITCH", callback_data='killswitch')
        ],
        [
            InlineKeyboardButton("⚡ TRADING SYSTEMS", callback_data='menu_trading'),
            InlineKeyboardButton("🔧 INFRASTRUCTURE", callback_data='menu_infrastructure')
        ],
        [
            InlineKeyboardButton("📡 SYSTEM LOGS", callback_data='menu_logs'),
            InlineKeyboardButton("📈 ANALYTICS", callback_data='menu_analytics')
        ],
        [
            InlineKeyboardButton("🔄 MASS RESTART", callback_data='restart_all'),
            InlineKeyboardButton("⚙️ ADVANCED OPS", callback_data='menu_advanced')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎯 *ALPHA COMMAND CENTER*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*OPERATIONAL SYSTEMS:*\n"
        "▸ ALPHA - Multi-Asset Short Seller\n"
        "▸ BRAVO - LX Algorithm Executor\n"
        "▸ CHARLIE - Momentum Strategy\n\n"
        "*SUPPORT INFRASTRUCTURE:*\n"
        "▸ DATABASE CORE - PostgreSQL\n"
        "▸ CACHE CORE - Redis\n\n"
        "Select tactical option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


@requires_authentication
async def sitrep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Situation Report - Full system status"""
    message = await update.message.reply_text("🔍 *GENERATING SITREP...*", parse_mode='Markdown')

    status_text = "📊 *TACTICAL SITUATION REPORT*\n"
    status_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    status_text += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"

    # Trading Systems Status
    status_text += "*🎯 TRADING SYSTEMS*\n"
    trading_operational = 0

    for system_id in TRADING_SYSTEMS:
        system = SYSTEMS[system_id]
        status_line, is_running = await get_system_status(system)
        status_text += status_line
        if is_running:
            trading_operational += 1

    # Infrastructure Status
    status_text += "\n*🔧 INFRASTRUCTURE*\n"
    infra_operational = 0

    for system_id in INFRASTRUCTURE_SYSTEMS:
        system = SYSTEMS[system_id]
        status_line, is_running = await get_system_status(system)
        status_text += status_line
        if is_running:
            infra_operational += 1

    # Overall Status Summary
    status_text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    status_text += f"*OPERATIONAL STATUS:*\n"
    status_text += f"├─ Trading: {trading_operational}/{len(TRADING_SYSTEMS)}\n"
    status_text += f"└─ Infrastructure: {infra_operational}/{len(INFRASTRUCTURE_SYSTEMS)}\n"

    # Overall health
    total_operational = trading_operational + infra_operational
    total_systems = len(ALL_SYSTEMS)

    if total_operational == total_systems:
        status_text += "\n🟢 *ALL SYSTEMS OPERATIONAL*"
    elif total_operational >= total_systems * 0.7:
        status_text += "\n🟡 *PARTIAL OPERATIONS*"
    else:
        status_text += "\n🔴 *CRITICAL: MULTIPLE SYSTEMS DOWN*"

    await message.edit_text(status_text, parse_mode='Markdown')


@requires_authentication
async def deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deploy (start) specific system"""
    if len(context.args) < 1:
        systems_list = '\n'.join([f"  • {k} - {v['description']}" for k, v in SYSTEMS.items()])
        await update.message.reply_text(
            f"*DEPLOY COMMAND USAGE:*\n"
            f"`/deploy <system_id>`\n\n"
            f"*AVAILABLE SYSTEMS:*\n{systems_list}",
            parse_mode='Markdown'
        )
        return

    system_id = context.args[0].lower()

    if system_id not in SYSTEMS:
        await update.message.reply_text(f"❌ *UNKNOWN SYSTEM:* `{system_id}`", parse_mode='Markdown')
        return

    await execute_system_action(update, system_id, 'deploy')


@requires_authentication
async def terminate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terminate (stop) specific system"""
    if len(context.args) < 1:
        systems_list = '\n'.join([f"  • {k} - {v['description']}" for k, v in SYSTEMS.items()])
        await update.message.reply_text(
            f"*TERMINATE COMMAND USAGE:*\n"
            f"`/terminate <system_id>`\n\n"
            f"*AVAILABLE SYSTEMS:*\n{systems_list}",
            parse_mode='Markdown'
        )
        return

    system_id = context.args[0].lower()

    if system_id not in SYSTEMS:
        await update.message.reply_text(f"❌ *UNKNOWN SYSTEM:* `{system_id}`", parse_mode='Markdown')
        return

    await execute_system_action(update, system_id, 'terminate')


@requires_authentication
async def reboot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reboot (restart) specific system"""
    if len(context.args) < 1:
        systems_list = '\n'.join([f"  • {k} - {v['description']}" for k, v in SYSTEMS.items()])
        await update.message.reply_text(
            f"*REBOOT COMMAND USAGE:*\n"
            f"`/reboot <system_id>`\n\n"
            f"*AVAILABLE SYSTEMS:*\n{systems_list}",
            parse_mode='Markdown'
        )
        return

    system_id = context.args[0].lower()

    if system_id not in SYSTEMS:
        await update.message.reply_text(f"❌ *UNKNOWN SYSTEM:* `{system_id}`", parse_mode='Markdown')
        return

    await execute_system_action(update, system_id, 'reboot')


@requires_authentication
async def diagnostics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System diagnostics - detailed view"""
    if len(context.args) < 1:
        await update.message.reply_text(
            "*DIAGNOSTICS USAGE:*\n"
            "`/diagnostics <system_id>`\n\n"
            "Example: `/diagnostics alpha`",
            parse_mode='Markdown'
        )
        return

    system_id = context.args[0].lower()

    if system_id not in SYSTEMS:
        await update.message.reply_text(f"❌ *UNKNOWN SYSTEM:* `{system_id}`", parse_mode='Markdown')
        return

    system = SYSTEMS[system_id]
    message = await update.message.reply_text(f"🔍 *RUNNING DIAGNOSTICS: {system['name']}*", parse_mode='Markdown')

    try:
        container = docker_client.containers.get(system['container'])

        # Get detailed stats
        status = container.status
        stats = container.stats(stream=False) if status == 'running' else None

        diag_text = f"🔬 *SYSTEM DIAGNOSTICS*\n"
        diag_text += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        diag_text += f"*SYSTEM:* {system['name']}\n"
        diag_text += f"*ID:* `{system_id}`\n"
        diag_text += f"*TYPE:* {system['type'].upper()}\n"
        diag_text += f"*CONTAINER:* `{system['container']}`\n\n"

        # Status
        if status == 'running':
            diag_text += "🟢 *STATUS:* OPERATIONAL\n\n"

            if stats:
                # CPU Usage
                cpu_percent = calculate_cpu_percent(stats)
                diag_text += f"*CPU USAGE:* {cpu_percent:.2f}%\n"

                # Memory Usage
                mem_usage = stats['memory_stats'].get('usage', 0) / (1024**2)
                mem_limit = stats['memory_stats'].get('limit', 0) / (1024**2)
                mem_percent = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0
                diag_text += f"*MEMORY:* {mem_usage:.1f}MB / {mem_limit:.1f}MB ({mem_percent:.1f}%)\n"

                # Network I/O
                net_stats = stats.get('networks', {})
                if net_stats:
                    for iface, data in net_stats.items():
                        rx_mb = data.get('rx_bytes', 0) / (1024**2)
                        tx_mb = data.get('tx_bytes', 0) / (1024**2)
                        diag_text += f"*NETWORK ({iface}):*\n"
                        diag_text += f"  ├─ RX: {rx_mb:.2f}MB\n"
                        diag_text += f"  └─ TX: {tx_mb:.2f}MB\n"

        elif status == 'exited':
            diag_text += "🔴 *STATUS:* OFFLINE\n"
            # Get exit code
            exit_code = container.attrs.get('State', {}).get('ExitCode', 'Unknown')
            diag_text += f"*EXIT CODE:* {exit_code}\n"
        else:
            diag_text += f"🟡 *STATUS:* {status.upper()}\n"

        # Uptime
        started_at = container.attrs.get('State', {}).get('StartedAt', 'Unknown')
        if started_at != 'Unknown' and status == 'running':
            diag_text += f"\n*STARTED:* {started_at[:19]}\n"

        await message.edit_text(diag_text, parse_mode='Markdown')

    except docker.errors.NotFound:
        await message.edit_text(
            f"❌ *SYSTEM NOT FOUND*\n\n"
            f"System `{system_id}` is not deployed.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await message.edit_text(f"❌ *DIAGNOSTIC ERROR*\n\n`{str(e)}`", parse_mode='Markdown')
        logger.error(f"Diagnostics error for {system_id}: {e}")


@requires_authentication
async def intel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get system logs (intelligence)"""
    if len(context.args) < 1:
        await update.message.reply_text(
            "*INTEL COMMAND USAGE:*\n"
            "`/intel <system_id> [lines]`\n\n"
            "Example: `/intel alpha 100`\n"
            "Default: 50 lines",
            parse_mode='Markdown'
        )
        return

    system_id = context.args[0].lower()
    lines = int(context.args[1]) if len(context.args) > 1 else 50
    lines = min(lines, 200)  # Max 200 lines

    if system_id not in SYSTEMS:
        await update.message.reply_text(f"❌ *UNKNOWN SYSTEM:* `{system_id}`", parse_mode='Markdown')
        return

    system = SYSTEMS[system_id]

    try:
        container = docker_client.containers.get(system['container'])
        logs_output = container.logs(tail=lines).decode('utf-8', errors='ignore')

        # Split into chunks if too long
        max_length = 3800
        header = f"📡 *INTEL: {system['name']}*\n━━━━━━━━━━━━━━━━━━━━━\n\n"

        if len(logs_output) > max_length:
            # Take the last max_length characters
            logs_output = logs_output[-max_length:]
            chunks = [header + f"```\n{logs_output}\n```"]
        else:
            chunks = [header + f"```\n{logs_output}\n```"]

        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode='Markdown')

    except docker.errors.NotFound:
        await update.message.reply_text(
            f"❌ *SYSTEM NOT FOUND*\n\nSystem `{system_id}` is not deployed.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ *ERROR:* `{str(e)}`", parse_mode='Markdown')
        logger.error(f"Intel error for {system_id}: {e}")


@requires_authentication
async def execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute command in system"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "*EXECUTE COMMAND USAGE:*\n"
            "`/execute <system_id> <command>`\n\n"
            "Example: `/execute alpha ls -la /app`",
            parse_mode='Markdown'
        )
        return

    system_id = context.args[0].lower()
    command = ' '.join(context.args[1:])

    if system_id not in SYSTEMS:
        await update.message.reply_text(f"❌ *UNKNOWN SYSTEM:* `{system_id}`", parse_mode='Markdown')
        return

    system = SYSTEMS[system_id]

    try:
        container = docker_client.containers.get(system['container'])

        if container.status != 'running':
            await update.message.reply_text(
                f"❌ *SYSTEM OFFLINE*\n\n`{system_id}` is not operational.",
                parse_mode='Markdown'
            )
            return

        result = container.exec_run(command)
        output = result.output.decode('utf-8', errors='ignore')

        await update.message.reply_text(
            f"⚡ *COMMAND EXECUTED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"*SYSTEM:* {system['name']}\n"
            f"*COMMAND:* `{command}`\n\n"
            f"*OUTPUT:*\n```\n{output[:3500]}\n```",
            parse_mode='Markdown'
        )

        logger.info(f"Command executed on {system_id}: {command}")

    except Exception as e:
        await update.message.reply_text(f"❌ *EXECUTION ERROR:* `{str(e)}`", parse_mode='Markdown')
        logger.error(f"Execution error on {system_id}: {e}")


@requires_authentication
async def killswitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Emergency shutdown - terminate all trading systems"""
    # Confirmation required for killswitch
    if len(context.args) < 1 or context.args[0].upper() != 'CONFIRM':
        await update.message.reply_text(
            "🔴 *KILLSWITCH ACTIVATION*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ This will immediately terminate:\n"
            "  • ALPHA System\n"
            "  • BRAVO System\n"
            "  • CHARLIE System\n\n"
            "All active trades will cease.\n\n"
            "*To confirm:* `/killswitch CONFIRM`",
            parse_mode='Markdown'
        )
        return

    message = await update.message.reply_text(
        "🔴 *INITIATING EMERGENCY SHUTDOWN*\n━━━━━━━━━━━━━━━━━━━━━",
        parse_mode='Markdown'
    )

    results = []
    for system_id in TRADING_SYSTEMS:
        system = SYSTEMS[system_id]
        try:
            container = docker_client.containers.get(system['container'])
            if container.status == 'running':
                container.stop(timeout=10)
                results.append(f"✅ {system['name']} - TERMINATED")
                logger.warning(f"KILLSWITCH: Terminated {system_id}")
            else:
                results.append(f"⚪ {system['name']} - Already offline")
        except Exception as e:
            results.append(f"❌ {system['name']} - Error: {str(e)}")
            logger.error(f"Killswitch error on {system_id}: {e}")

    result_text = "🔴 *KILLSWITCH EXECUTED*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    result_text += "\n".join(results)
    result_text += f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"

    await message.edit_text(result_text, parse_mode='Markdown')


@requires_authentication
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display command reference"""
    help_text = """🎯 *COMMAND CENTER REFERENCE*
━━━━━━━━━━━━━━━━━━━━━

*AUTHENTICATION:*
`/auth <code>` - Authenticate Session
`/logout` - End Session
`/status` - Check Session Status

*SITUATION AWARENESS:*
`/cc` - Command Center (Main Menu)
`/sitrep` - Full System Status
`/diagnostics <system>` - Detailed Diagnostics

*SYSTEM CONTROL:*
`/deploy <system>` - Start System
`/terminate <system>` - Stop System
`/reboot <system>` - Restart System

*INTELLIGENCE:*
`/intel <system> [lines]` - View System Logs
`/execute <system> <cmd>` - Execute Command

*MASS OPERATIONS:*
`/deploy_all` - Deploy All Systems
`/terminate_all` - Shutdown All Systems
`/reboot_all` - Restart All Systems

*EMERGENCY:*
`/killswitch CONFIRM` - Emergency Trading Halt
"""

    if ANALYTICS_AVAILABLE:
        help_text += """
*ANALYTICS & TRADING:*
`/quick` - Quick Status Overview
`/analytics [bot] [days]` - Full Report
`/positions [bot]` - Active Positions
`/trades [bot] [limit]` - Recent Trades
`/daily [bot] [days]` - Daily Performance
`/cache` - Redis Cache Stats
"""

    help_text += """
━━━━━━━━━━━━━━━━━━━━━
*SYSTEM IDENTIFIERS:*

Trading Systems:
  • `alpha` - Multi-Asset Short Seller
  • `bravo` - LX Algorithm
  • `charlie` - Momentum Strategy

Infrastructure:
  • `database` - PostgreSQL Core
  • `cache` - Redis Cache

━━━━━━━━━━━━━━━━━━━━━
*EXAMPLES:*

`/deploy alpha`
`/intel bravo 100`
`/diagnostics charlie`
`/execute alpha ps aux`"""

    if ANALYTICS_AVAILABLE:
        help_text += """
`/analytics alpha 7`
`/positions bravo`
`/trades charlie 20`"""

    await update.message.reply_text(help_text, parse_mode='Markdown')


# ========================================
# AUTHENTICATION COMMANDS
# ========================================

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Authenticate user with access code"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    # Immediately delete the user's message containing the access code for security
    try:
        await update.message.delete()
        logger.info(f"🗑️ Deleted auth message from {username} (ID: {user_id})")
    except Exception as e:
        logger.warning(f"⚠️ Could not delete auth message: {e}")

    # Check if user is authorized
    if user_id not in ADMIN_IDS:
        response = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⛔ *ACCESS DENIED*\n\n"
                 "You are not in the authorized operators list.\n\n"
                 f"_This message will self-destruct in {MESSAGE_DELETE_DELAY} seconds._",
            parse_mode='Markdown'
        )
        logger.warning(f"❌ UNAUTHORIZED AUTH ATTEMPT: User {username} (ID: {user_id})")

        # Delete the response after configured delay
        await asyncio.sleep(MESSAGE_DELETE_DELAY)
        try:
            await response.delete()
        except:
            pass
        return

    # Check if code was provided
    if not context.args:
        response = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔐 *AUTHENTICATION REQUIRED*\n\n"
                 "Usage: `/auth <access_code>`\n\n"
                 "Contact your administrator for the access code.\n\n"
                 f"_This message will self-destruct in {MESSAGE_DELETE_DELAY} seconds._",
            parse_mode='Markdown'
        )
        # Delete instruction message after configured delay
        await asyncio.sleep(MESSAGE_DELETE_DELAY)
        try:
            await response.delete()
        except:
            pass
        return

    provided_code = ' '.join(context.args)

    # Verify access code
    if provided_code == ACCESS_CODE:
        create_session(user_id)
        response = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ *AUTHENTICATION SUCCESSFUL*\n\n"
                 f"Welcome, {username}!\n"
                 f"Session active for {SESSION_TIMEOUT} minutes.\n\n"
                 "Use `/cc` to access Command Center.\n"
                 "Use `/logout` to end your session.\n\n"
                 f"_This message will self-destruct in {MESSAGE_DELETE_DELAY} seconds._",
            parse_mode='Markdown'
        )
        logger.info(f"✓ AUTHENTICATION SUCCESS: User {username} (ID: {user_id})")

        # Delete success message after configured delay
        await asyncio.sleep(MESSAGE_DELETE_DELAY)
        try:
            await response.delete()
        except:
            pass
    else:
        response = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ *AUTHENTICATION FAILED*\n\n"
                 "Invalid access code.\n"
                 "Access attempt logged.\n\n"
                 f"_This message will self-destruct in {MESSAGE_DELETE_DELAY} seconds._",
            parse_mode='Markdown'
        )
        logger.warning(f"❌ FAILED AUTH ATTEMPT: User {username} (ID: {user_id}) - Wrong code")

        # Delete failure message after configured delay
        await asyncio.sleep(MESSAGE_DELETE_DELAY)
        try:
            await response.delete()
        except:
            pass


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logout and end session"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    if user_id in active_sessions:
        end_session(user_id)
        await update.message.reply_text(
            "✅ *LOGOUT SUCCESSFUL*\n\n"
            "Your session has been terminated.\n"
            "Use `/auth <access_code>` to login again.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "ℹ️ *NO ACTIVE SESSION*\n\n"
            "You were not logged in.",
            parse_mode='Markdown'
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check session status"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔ *ACCESS DENIED*",
            parse_mode='Markdown'
        )
        return

    if is_session_active(user_id):
        last_activity = active_sessions[user_id]
        elapsed_minutes = (datetime.now() - last_activity).total_seconds() / 60
        remaining_minutes = SESSION_TIMEOUT - elapsed_minutes

        await update.message.reply_text(
            f"✅ *SESSION ACTIVE*\n\n"
            f"User: {username}\n"
            f"Session expires in: {int(remaining_minutes)} minutes\n\n"
            "Use any command to refresh session.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🔐 *NO ACTIVE SESSION*\n\n"
            "Use `/auth <access_code>` to authenticate.",
            parse_mode='Markdown'
        )


# ========================================
# ANALYTICS BUTTON HANDLERS
# ========================================

async def handle_analytics_quick(query):
    """Handle quick status button"""
    if not ANALYTICS_AVAILABLE:
        await query.edit_message_text("⚠️ Analytics not available", parse_mode='Markdown')
        return

    # Call the quick_status handler with a mock update
    from analytics_handlers import quick_status

    # Create a message to send response
    await query.message.reply_text("📊 *Generating Quick Status...*", parse_mode='Markdown')

    # Create a mock update object to pass to the handler
    class MockUpdate:
        def __init__(self, message):
            self.message = message

    mock_update = MockUpdate(query.message)
    await quick_status(mock_update, None)


async def handle_analytics_full(query):
    """Handle full analytics button"""
    if not ANALYTICS_AVAILABLE:
        await query.edit_message_text("⚠️ Analytics not available", parse_mode='Markdown')
        return

    from analytics_handlers import analytics_summary

    await query.message.reply_text("📊 *Generating Full Analytics Report...*", parse_mode='Markdown')

    class MockUpdate:
        def __init__(self, message):
            self.message = message

    class MockContext:
        def __init__(self):
            self.args = []

    mock_update = MockUpdate(query.message)
    mock_context = MockContext()
    await analytics_summary(mock_update, mock_context)


async def handle_analytics_positions(query):
    """Handle positions button"""
    if not ANALYTICS_AVAILABLE:
        await query.edit_message_text("⚠️ Analytics not available", parse_mode='Markdown')
        return

    from analytics_handlers import positions_summary

    await query.message.reply_text("📍 *Fetching Active Positions...*", parse_mode='Markdown')

    class MockUpdate:
        def __init__(self, message):
            self.message = message

    class MockContext:
        def __init__(self):
            self.args = []

    mock_update = MockUpdate(query.message)
    mock_context = MockContext()
    await positions_summary(mock_update, mock_context)


async def handle_analytics_trades(query):
    """Handle trades button"""
    if not ANALYTICS_AVAILABLE:
        await query.edit_message_text("⚠️ Analytics not available", parse_mode='Markdown')
        return

    from analytics_handlers import trades_history

    await query.message.reply_text("📋 *Fetching Recent Trades...*", parse_mode='Markdown')

    class MockUpdate:
        def __init__(self, message):
            self.message = message

    class MockContext:
        def __init__(self):
            self.args = []

    mock_update = MockUpdate(query.message)
    mock_context = MockContext()
    await trades_history(mock_update, mock_context)


async def handle_analytics_daily(query):
    """Handle daily performance button"""
    if not ANALYTICS_AVAILABLE:
        await query.edit_message_text("⚠️ Analytics not available", parse_mode='Markdown')
        return

    from analytics_handlers import daily_performance

    await query.message.reply_text("📅 *Generating Daily Performance...*", parse_mode='Markdown')

    class MockUpdate:
        def __init__(self, message):
            self.message = message

    class MockContext:
        def __init__(self):
            self.args = []

    mock_update = MockUpdate(query.message)
    mock_context = MockContext()
    await daily_performance(mock_update, mock_context)


async def handle_analytics_cache(query):
    """Handle cache stats button"""
    if not ANALYTICS_AVAILABLE:
        await query.edit_message_text("⚠️ Analytics not available", parse_mode='Markdown')
        return

    from analytics_handlers import cache_stats

    await query.message.reply_text("💾 *Fetching Cache Statistics...*", parse_mode='Markdown')

    class MockUpdate:
        def __init__(self, message):
            self.message = message

    mock_update = MockUpdate(query.message)
    await cache_stats(mock_update, None)


# ========================================
# CALLBACK QUERY HANDLERS (Button Actions)
# ========================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks from inline keyboards"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ *ACCESS DENIED*", parse_mode='Markdown')
        return

    data = query.data

    # Main actions
    if data == 'sitrep':
        await handle_sitrep_button(query)
    elif data == 'deploy_all':
        await handle_deploy_all(query)
    elif data == 'killswitch':
        await handle_killswitch_button(query)
    elif data == 'terminate_all':
        await handle_terminate_all(query)
    elif data == 'restart_all':
        await handle_restart_all(query)

    # Menus
    elif data == 'menu_trading':
        await show_trading_menu(query)
    elif data == 'menu_infrastructure':
        await show_infrastructure_menu(query)
    elif data == 'menu_logs':
        await show_logs_menu(query)
    elif data == 'menu_analytics':
        await show_analytics_menu(query)
    elif data == 'menu_advanced':
        await show_advanced_menu(query)

    # Analytics actions
    elif data == 'analytics_quick':
        await handle_analytics_quick(query)
    elif data == 'analytics_full':
        await handle_analytics_full(query)
    elif data == 'analytics_positions':
        await handle_analytics_positions(query)
    elif data == 'analytics_trades':
        await handle_analytics_trades(query)
    elif data == 'analytics_daily':
        await handle_analytics_daily(query)
    elif data == 'analytics_cache':
        await handle_analytics_cache(query)

    # System actions
    elif data.startswith('deploy_'):
        system_id = data.replace('deploy_', '')
        await handle_system_action_button(query, system_id, 'deploy')
    elif data.startswith('terminate_'):
        system_id = data.replace('terminate_', '')
        await handle_system_action_button(query, system_id, 'terminate')
    elif data.startswith('reboot_'):
        system_id = data.replace('reboot_', '')
        await handle_system_action_button(query, system_id, 'reboot')
    elif data.startswith('intel_'):
        system_id = data.replace('intel_', '')
        await handle_intel_button(query, system_id)
    elif data.startswith('diag_'):
        system_id = data.replace('diag_', '')
        await handle_diagnostics_button(query, system_id)


# ========================================
# BUTTON HANDLERS
# ========================================

async def handle_sitrep_button(query):
    """SITREP via button"""
    await query.edit_message_text("🔍 *GENERATING SITREP...*", parse_mode='Markdown')

    status_text = "📊 *TACTICAL SITUATION REPORT*\n"
    status_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
    status_text += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"

    status_text += "*🎯 TRADING SYSTEMS*\n"
    trading_operational = 0

    for system_id in TRADING_SYSTEMS:
        system = SYSTEMS[system_id]
        status_line, is_running = await get_system_status(system)
        status_text += status_line
        if is_running:
            trading_operational += 1

    status_text += "\n*🔧 INFRASTRUCTURE*\n"
    infra_operational = 0

    for system_id in INFRASTRUCTURE_SYSTEMS:
        system = SYSTEMS[system_id]
        status_line, is_running = await get_system_status(system)
        status_text += status_line
        if is_running:
            infra_operational += 1

    status_text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    status_text += f"*OPERATIONAL STATUS:*\n"
    status_text += f"├─ Trading: {trading_operational}/{len(TRADING_SYSTEMS)}\n"
    status_text += f"└─ Infrastructure: {infra_operational}/{len(INFRASTRUCTURE_SYSTEMS)}\n"

    total_operational = trading_operational + infra_operational
    total_systems = len(ALL_SYSTEMS)

    if total_operational == total_systems:
        status_text += "\n🟢 *ALL SYSTEMS OPERATIONAL*"
    elif total_operational >= total_systems * 0.7:
        status_text += "\n🟡 *PARTIAL OPERATIONS*"
    else:
        status_text += "\n🔴 *CRITICAL: MULTIPLE SYSTEMS DOWN*"

    await query.edit_message_text(status_text, parse_mode='Markdown')


async def handle_deploy_all(query):
    """Deploy all systems"""
    await query.edit_message_text("🚀 *INITIATING MASS DEPLOYMENT...*", parse_mode='Markdown')

    results = []
    for system_id in ALL_SYSTEMS:
        system = SYSTEMS[system_id]
        try:
            container = docker_client.containers.get(system['container'])
            if container.status != 'running':
                container.start()
                results.append(f"✅ {system['name']}")
                logger.info(f"Deployed: {system_id}")
            else:
                results.append(f"🟢 {system['name']} (Already operational)")
        except Exception as e:
            results.append(f"❌ {system['name']}: {str(e)}")
            logger.error(f"Deploy error {system_id}: {e}")

    result_text = "🚀 *DEPLOYMENT COMPLETE*\n━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(results)
    await query.edit_message_text(result_text, parse_mode='Markdown')


async def handle_terminate_all(query):
    """Terminate all systems"""
    await query.edit_message_text("🛑 *INITIATING MASS SHUTDOWN...*", parse_mode='Markdown')

    results = []
    for system_id in ALL_SYSTEMS:
        system = SYSTEMS[system_id]
        try:
            container = docker_client.containers.get(system['container'])
            if container.status == 'running':
                container.stop(timeout=30)
                results.append(f"✅ {system['name']}")
                logger.info(f"Terminated: {system_id}")
            else:
                results.append(f"⚪ {system['name']} (Already offline)")
        except Exception as e:
            results.append(f"❌ {system['name']}: {str(e)}")
            logger.error(f"Terminate error {system_id}: {e}")

    result_text = "🛑 *SHUTDOWN COMPLETE*\n━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(results)
    await query.edit_message_text(result_text, parse_mode='Markdown')


async def handle_restart_all(query):
    """Restart all systems"""
    await query.edit_message_text("🔄 *INITIATING MASS REBOOT...*", parse_mode='Markdown')

    results = []
    for system_id in ALL_SYSTEMS:
        system = SYSTEMS[system_id]
        try:
            container = docker_client.containers.get(system['container'])
            container.restart(timeout=30)
            results.append(f"✅ {system['name']}")
            logger.info(f"Rebooted: {system_id}")
        except Exception as e:
            results.append(f"❌ {system['name']}: {str(e)}")
            logger.error(f"Reboot error {system_id}: {e}")

    result_text = "🔄 *REBOOT COMPLETE*\n━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(results)
    await query.edit_message_text(result_text, parse_mode='Markdown')


async def handle_killswitch_button(query):
    """Killswitch confirmation"""
    keyboard = [
        [InlineKeyboardButton("🔴 CONFIRM KILLSWITCH", callback_data='terminate_all')],
        [InlineKeyboardButton("❌ ABORT", callback_data='sitrep')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔴 *KILLSWITCH ACTIVATION*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ This will terminate all trading systems:\n"
        "  • ALPHA System\n"
        "  • BRAVO System\n"
        "  • CHARLIE System\n"
        "  • Database Core\n"
        "  • Cache Core\n\n"
        "*Confirm to proceed:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_trading_menu(query):
    """Trading systems control panel"""
    keyboard = []

    for system_id in TRADING_SYSTEMS:
        system = SYSTEMS[system_id]
        keyboard.append([
            InlineKeyboardButton(f"⚡ {system['name']}", callback_data='noop'),
        ])
        keyboard.append([
            InlineKeyboardButton("🚀 Deploy", callback_data=f'deploy_{system_id}'),
            InlineKeyboardButton("🛑 Terminate", callback_data=f'terminate_{system_id}'),
            InlineKeyboardButton("🔄 Reboot", callback_data=f'reboot_{system_id}')
        ])
        keyboard.append([
            InlineKeyboardButton("📡 Intel", callback_data=f'intel_{system_id}'),
            InlineKeyboardButton("🔬 Diagnostics", callback_data=f'diag_{system_id}')
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "⚡ *TRADING SYSTEMS CONTROL*\n━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_infrastructure_menu(query):
    """Infrastructure control panel"""
    keyboard = []

    for system_id in INFRASTRUCTURE_SYSTEMS:
        system = SYSTEMS[system_id]
        keyboard.append([
            InlineKeyboardButton(f"🔧 {system['name']}", callback_data='noop'),
        ])
        keyboard.append([
            InlineKeyboardButton("🚀 Deploy", callback_data=f'deploy_{system_id}'),
            InlineKeyboardButton("🛑 Terminate", callback_data=f'terminate_{system_id}'),
            InlineKeyboardButton("🔄 Reboot", callback_data=f'reboot_{system_id}')
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🔧 *INFRASTRUCTURE CONTROL*\n━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_logs_menu(query):
    """Logs selection menu"""
    keyboard = []

    for system_id in ALL_SYSTEMS:
        system = SYSTEMS[system_id]
        keyboard.append([
            InlineKeyboardButton(f"📡 {system['name']}", callback_data=f'intel_{system_id}')
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "📡 *SYSTEM INTELLIGENCE*\n━━━━━━━━━━━━━━━━━━━━━\n\nSelect system:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_analytics_menu(query):
    """Analytics menu"""
    if not ANALYTICS_AVAILABLE:
        await query.edit_message_text(
            "📈 *ANALYTICS*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ Analytics features are currently unavailable.\n"
            "Database connection may not be configured.",
            parse_mode='Markdown'
        )
        return

    keyboard = [
        [InlineKeyboardButton("⚡ Quick Status", callback_data='analytics_quick')],
        [InlineKeyboardButton("📊 Full Analytics Report", callback_data='analytics_full')],
        [InlineKeyboardButton("📍 Active Positions", callback_data='analytics_positions')],
        [InlineKeyboardButton("📋 Recent Trades", callback_data='analytics_trades')],
        [InlineKeyboardButton("📅 Daily Performance", callback_data='analytics_daily')],
        [InlineKeyboardButton("💾 Cache Stats", callback_data='analytics_cache')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📈 *ANALYTICS & REPORTS*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Available Commands:*\n\n"
        "`/quick` - Quick status overview\n"
        "`/analytics [bot] [days]` - Full report\n"
        "`/positions [bot]` - Active positions\n"
        "`/trades [bot] [limit]` - Recent trades\n"
        "`/daily [bot] [days]` - Daily breakdown\n"
        "`/cache` - Redis cache stats\n\n"
        "*Examples:*\n"
        "`/analytics alpha 7`\n"
        "`/positions bravo`\n"
        "`/trades charlie 20`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_advanced_menu(query):
    """Advanced operations menu"""
    keyboard = [
        [InlineKeyboardButton("🚀 Deploy All Systems", callback_data='deploy_all')],
        [InlineKeyboardButton("🛑 Terminate All Systems", callback_data='terminate_all')],
        [InlineKeyboardButton("🔄 Reboot All Systems", callback_data='restart_all')],
        [InlineKeyboardButton("🔴 KILLSWITCH", callback_data='killswitch')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "⚙️ *ADVANCED OPERATIONS*\n━━━━━━━━━━━━━━━━━━━━━\n\n⚠️ Use with caution:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_system_action_button(query, system_id, action):
    """Handle system action from button"""
    if system_id not in SYSTEMS:
        await query.edit_message_text(f"❌ Unknown system: {system_id}")
        return

    system = SYSTEMS[system_id]

    try:
        container = docker_client.containers.get(system['container'])

        if action == 'deploy':
            if container.status == 'running':
                await query.edit_message_text(
                    f"🟢 *{system['name']}*\n\nAlready operational.",
                    parse_mode='Markdown'
                )
            else:
                container.start()
                await query.edit_message_text(
                    f"🚀 *DEPLOYED*\n\n{system['name']} is now operational.",
                    parse_mode='Markdown'
                )
                logger.info(f"Deployed: {system_id}")

        elif action == 'terminate':
            if container.status != 'running':
                await query.edit_message_text(
                    f"⚪ *{system['name']}*\n\nAlready offline.",
                    parse_mode='Markdown'
                )
            else:
                container.stop(timeout=30)
                await query.edit_message_text(
                    f"🛑 *TERMINATED*\n\n{system['name']} has been shut down.",
                    parse_mode='Markdown'
                )
                logger.info(f"Terminated: {system_id}")

        elif action == 'reboot':
            container.restart(timeout=30)
            await query.edit_message_text(
                f"🔄 *REBOOTED*\n\n{system['name']} has been restarted.",
                parse_mode='Markdown'
            )
            logger.info(f"Rebooted: {system_id}")

    except Exception as e:
        await query.edit_message_text(f"❌ *ERROR*\n\n`{str(e)}`", parse_mode='Markdown')
        logger.error(f"Action error ({action}) on {system_id}: {e}")


async def handle_intel_button(query, system_id):
    """Show system logs via button"""
    if system_id not in SYSTEMS:
        await query.edit_message_text(f"❌ Unknown system: {system_id}")
        return

    system = SYSTEMS[system_id]

    try:
        container = docker_client.containers.get(system['container'])
        logs_output = container.logs(tail=50).decode('utf-8', errors='ignore')

        max_length = 3800
        if len(logs_output) > max_length:
            logs_output = logs_output[-max_length:]

        await query.edit_message_text(
            f"📡 *INTEL: {system['name']}*\n━━━━━━━━━━━━━━━━━━━━━\n\n```\n{logs_output}\n```",
            parse_mode='Markdown'
        )

    except Exception as e:
        await query.edit_message_text(f"❌ *ERROR*\n\n`{str(e)}`", parse_mode='Markdown')


async def handle_diagnostics_button(query, system_id):
    """Show diagnostics via button"""
    if system_id not in SYSTEMS:
        await query.edit_message_text(f"❌ Unknown system: {system_id}")
        return

    system = SYSTEMS[system_id]

    try:
        container = docker_client.containers.get(system['container'])
        status = container.status
        stats = container.stats(stream=False) if status == 'running' else None

        diag_text = f"🔬 *DIAGNOSTICS: {system['name']}*\n━━━━━━━━━━━━━━━━━━━━━\n\n"

        if status == 'running':
            diag_text += "🟢 *STATUS:* OPERATIONAL\n\n"

            if stats:
                cpu_percent = calculate_cpu_percent(stats)
                mem_usage = stats['memory_stats'].get('usage', 0) / (1024**2)
                mem_limit = stats['memory_stats'].get('limit', 0) / (1024**2)
                mem_percent = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0

                diag_text += f"*CPU:* {cpu_percent:.2f}%\n"
                diag_text += f"*MEMORY:* {mem_usage:.1f}MB / {mem_limit:.1f}MB ({mem_percent:.1f}%)\n"
        else:
            diag_text += f"🔴 *STATUS:* {status.upper()}\n"

        await query.edit_message_text(diag_text, parse_mode='Markdown')

    except Exception as e:
        await query.edit_message_text(f"❌ *ERROR*\n\n`{str(e)}`", parse_mode='Markdown')


# ========================================
# UTILITY FUNCTIONS
# ========================================

async def get_system_status(system):
    """Get status line for a system"""
    try:
        container = docker_client.containers.get(system['container'])
        status = container.status

        if status == 'running':
            emoji = "🟢"
            status_text = "OPERATIONAL"
            is_running = True
        elif status == 'exited':
            emoji = "🔴"
            status_text = "OFFLINE"
            is_running = False
        else:
            emoji = "🟡"
            status_text = status.upper()
            is_running = False

        return f"{emoji} {system['name']}: {status_text}\n", is_running

    except docker.errors.NotFound:
        return f"⚪ {system['name']}: NOT DEPLOYED\n", False


async def execute_system_action(update, system_id, action):
    """Execute system action (deploy/terminate/reboot)"""
    system = SYSTEMS[system_id]

    try:
        container = docker_client.containers.get(system['container'])

        if action == 'deploy':
            if container.status == 'running':
                await update.message.reply_text(
                    f"🟢 *{system['name']}* is already operational.",
                    parse_mode='Markdown'
                )
            else:
                container.start()
                await update.message.reply_text(
                    f"🚀 *DEPLOYED*\n\n{system['name']} is now operational.",
                    parse_mode='Markdown'
                )
                logger.info(f"Deployed: {system_id}")

        elif action == 'terminate':
            if container.status != 'running':
                await update.message.reply_text(
                    f"⚪ *{system['name']}* is already offline.",
                    parse_mode='Markdown'
                )
            else:
                container.stop(timeout=30)
                await update.message.reply_text(
                    f"🛑 *TERMINATED*\n\n{system['name']} has been shut down.",
                    parse_mode='Markdown'
                )
                logger.info(f"Terminated: {system_id}")

        elif action == 'reboot':
            container.restart(timeout=30)
            await update.message.reply_text(
                f"🔄 *REBOOTED*\n\n{system['name']} has been restarted.",
                parse_mode='Markdown'
            )
            logger.info(f"Rebooted: {system_id}")

    except docker.errors.NotFound:
        await update.message.reply_text(
            f"❌ *SYSTEM NOT FOUND*\n\nSystem `{system_id}` is not deployed.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ *ERROR:* `{str(e)}`", parse_mode='Markdown')
        logger.error(f"Action error ({action}) on {system_id}: {e}")


def calculate_cpu_percent(stats):
    """Calculate CPU percentage from container stats"""
    try:
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                    stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                       stats['precpu_stats']['system_cpu_usage']
        cpu_count = stats['cpu_stats']['online_cpus']

        if system_delta > 0 and cpu_delta > 0:
            return (cpu_delta / system_delta) * cpu_count * 100.0
    except:
        pass
    return 0.0


# ========================================
# MASS OPERATION COMMANDS
# ========================================

@requires_authentication
async def deploy_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deploy all systems via command"""
    message = await update.message.reply_text("🚀 *INITIATING MASS DEPLOYMENT...*", parse_mode='Markdown')

    results = []
    for system_id in ALL_SYSTEMS:
        system = SYSTEMS[system_id]
        try:
            container = docker_client.containers.get(system['container'])
            if container.status != 'running':
                container.start()
                results.append(f"✅ {system['name']}")
            else:
                results.append(f"🟢 {system['name']} (Already operational)")
        except Exception as e:
            results.append(f"❌ {system['name']}: {str(e)}")

    result_text = "🚀 *DEPLOYMENT COMPLETE*\n━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(results)
    await message.edit_text(result_text, parse_mode='Markdown')


@requires_authentication
async def terminate_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terminate all systems via command"""
    message = await update.message.reply_text("🛑 *INITIATING MASS SHUTDOWN...*", parse_mode='Markdown')

    results = []
    for system_id in ALL_SYSTEMS:
        system = SYSTEMS[system_id]
        try:
            container = docker_client.containers.get(system['container'])
            if container.status == 'running':
                container.stop(timeout=30)
                results.append(f"✅ {system['name']}")
            else:
                results.append(f"⚪ {system['name']} (Already offline)")
        except Exception as e:
            results.append(f"❌ {system['name']}: {str(e)}")

    result_text = "🛑 *SHUTDOWN COMPLETE*\n━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(results)
    await message.edit_text(result_text, parse_mode='Markdown')


@requires_authentication
async def reboot_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reboot all systems via command"""
    message = await update.message.reply_text("🔄 *INITIATING MASS REBOOT...*", parse_mode='Markdown')

    results = []
    for system_id in ALL_SYSTEMS:
        system = SYSTEMS[system_id]
        try:
            container = docker_client.containers.get(system['container'])
            container.restart(timeout=30)
            results.append(f"✅ {system['name']}")
        except Exception as e:
            results.append(f"❌ {system['name']}: {str(e)}")

    result_text = "🔄 *REBOOT COMPLETE*\n━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(results)
    await message.edit_text(result_text, parse_mode='Markdown')


# ========================================
# MAIN
# ========================================

def main():
    """Initialize and start the Command Center"""

    # Validation
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not configured")
        return

    if not ADMIN_IDS:
        logger.error("❌ TELEGRAM_ADMIN_IDS not configured")
        return

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("🎯 ALPHA COMMAND CENTER - INITIALIZING")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"✓ Authorized operators: {len(ADMIN_IDS)}")
    logger.info(f"✓ Systems under control: {len(ALL_SYSTEMS)}")

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Authentication handlers (no session required)
    application.add_handler(CommandHandler("auth", auth_command))
    application.add_handler(CommandHandler("logout", logout_command))
    application.add_handler(CommandHandler("status", status_command))

    # Command handlers (require authentication)
    application.add_handler(CommandHandler("cc", command_center))
    application.add_handler(CommandHandler("start", command_center))
    application.add_handler(CommandHandler("sitrep", sitrep))
    application.add_handler(CommandHandler("deploy", deploy))
    application.add_handler(CommandHandler("terminate", terminate))
    application.add_handler(CommandHandler("reboot", reboot))
    application.add_handler(CommandHandler("diagnostics", diagnostics))
    application.add_handler(CommandHandler("intel", intel))
    application.add_handler(CommandHandler("execute", execute))
    application.add_handler(CommandHandler("killswitch", killswitch))
    application.add_handler(CommandHandler("deploy_all", deploy_all_cmd))
    application.add_handler(CommandHandler("terminate_all", terminate_all_cmd))
    application.add_handler(CommandHandler("reboot_all", reboot_all_cmd))
    application.add_handler(CommandHandler("help", help_command))

    # Analytics handlers (if available)
    if ANALYTICS_AVAILABLE:
        application.add_handler(CommandHandler("quick", quick_status))
        application.add_handler(CommandHandler("analytics", analytics_summary))
        application.add_handler(CommandHandler("positions", positions_summary))
        application.add_handler(CommandHandler("trades", trades_history))
        application.add_handler(CommandHandler("daily", daily_performance))
        application.add_handler(CommandHandler("cache", cache_stats))
        logger.info("✓ Analytics features enabled")

    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start bot
    logger.info("✓ Command Center operational")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
