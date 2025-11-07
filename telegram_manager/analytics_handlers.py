#!/usr/bin/env python3
"""
Analytics Command Handlers for Telegram Bot
Provides formatted analytics summaries from database
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from db_analytics import get_analytics
import logging

logger = logging.getLogger(__name__)


def format_number(value, decimals=2):
    """Format number with proper decimals and commas"""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


def format_pnl(value, show_sign=True):
    """Format P&L with color indicators"""
    if value is None or value == 0:
        return "0.00"

    try:
        value = float(value)
        sign = "+" if value > 0 else ""
        if show_sign:
            return f"{sign}{value:,.2f}"
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return "0.00"


def format_percentage(value, show_sign=True):
    """Format percentage with sign"""
    if value is None:
        return "0.00%"

    try:
        value = float(value)
        sign = "+" if value > 0 else ""
        if show_sign:
            return f"{sign}{value:.2f}%"
        return f"{value:.2f}%"
    except (ValueError, TypeError):
        return "0.00%"


async def analytics_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /analytics [bot_id] [days] - Display comprehensive trading analytics

    Examples:
        /analytics - All bots, last 7 days
        /analytics alpha - Alpha bot, last 7 days
        /analytics alpha 30 - Alpha bot, last 30 days
    """
    analytics = get_analytics()

    # Parse arguments
    bot_id = None
    days = 7

    if len(context.args) >= 1:
        bot_id = context.args[0].lower()
        # Map system names to bot IDs
        bot_mapping = {
            'alpha': 'shortseller_001',
            'bravo': 'lxalgo_001',
            'charlie': 'momentum_001'
        }
        bot_id = bot_mapping.get(bot_id, bot_id)

    if len(context.args) >= 2:
        try:
            days = min(int(context.args[1]), 90)  # Max 90 days
        except ValueError:
            days = 7

    await update.message.reply_text("📊 *Generating Analytics Report...*", parse_mode='Markdown')

    # Get trading summary
    trading_summary = analytics.get_trading_summary(bot_id, days)

    # Get bot info
    bot_summary = analytics.get_bot_summary(bot_id)

    # Build report
    report = f"📊 *TRADING ANALYTICS REPORT*\n"
    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    report += f"📅 Period: Last {days} days\n\n"

    # Bot information
    if bot_id and bot_summary:
        bot = bot_summary[0]
        report += f"*BOT: {bot['bot_name']}*\n"
        report += f"├─ ID: `{bot['bot_id']}`\n"
        report += f"├─ Type: {bot['bot_type']}\n"
        report += f"├─ Status: {bot['status'].upper()}\n"
        report += f"├─ Capital: ${format_number(bot['initial_capital'])}\n"
        report += f"├─ Equity: ${format_number(bot['current_equity'])}\n"
        report += f"└─ Return: {format_percentage(bot['return_pct'])}\n\n"
    else:
        report += f"*PORTFOLIO OVERVIEW*\n"
        portfolio = analytics.get_portfolio_summary()
        if portfolio:
            report += f"├─ Total Bots: {portfolio.get('total_bots', 0)}\n"
            report += f"├─ Active: {portfolio.get('active_bots', 0)}\n"
            report += f"├─ Capital: ${format_number(portfolio.get('total_capital'))}\n"
            report += f"└─ Equity: ${format_number(portfolio.get('total_equity'))}\n\n"

    # Trading statistics
    if trading_summary:
        report += f"*TRADING STATISTICS*\n"
        report += f"├─ Total Trades: {trading_summary.get('total_trades', 0)}\n"
        report += f"├─ Closed: {trading_summary.get('closed_trades', 0)}\n"
        report += f"├─ Open: {trading_summary.get('open_trades', 0)}\n"
        report += f"├─ Wins: {trading_summary.get('winning_trades', 0)}\n"
        report += f"├─ Losses: {trading_summary.get('losing_trades', 0)}\n"
        report += f"└─ Win Rate: {format_percentage(trading_summary.get('win_rate', 0), False)}\n\n"

        # P&L
        total_pnl = trading_summary.get('total_pnl', 0)
        pnl_emoji = "🟢" if total_pnl and total_pnl > 0 else "🔴"

        report += f"*PROFIT & LOSS*\n"
        report += f"{pnl_emoji} Total P&L: ${format_pnl(total_pnl)}\n"
        report += f"├─ Avg P&L: ${format_pnl(trading_summary.get('avg_pnl'))}\n"
        report += f"├─ Max Win: ${format_pnl(trading_summary.get('max_win'))}\n"
        report += f"├─ Max Loss: ${format_pnl(trading_summary.get('max_loss'))}\n"
        report += f"└─ Total Fees: ${format_number(trading_summary.get('total_fees'))}\n\n"
    else:
        report += f"*No trading data for this period*\n\n"

    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"Use `/positions` to view active positions\n"
    report += f"Use `/trades` for recent trades"

    await update.message.reply_text(report, parse_mode='Markdown')


async def positions_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /positions [bot_id] - Display active positions

    Examples:
        /positions - All active positions
        /positions alpha - Alpha bot positions only
    """
    analytics = get_analytics()

    # Parse bot_id
    bot_id = None
    if len(context.args) >= 1:
        bot_id = context.args[0].lower()
        bot_mapping = {
            'alpha': 'shortseller_001',
            'bravo': 'lxalgo_001',
            'charlie': 'momentum_001'
        }
        bot_id = bot_mapping.get(bot_id, bot_id)

    positions = analytics.get_active_positions(bot_id)

    report = f"📍 *ACTIVE POSITIONS*\n"
    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    if not positions:
        report += "*No active positions*\n"
    else:
        report += f"*Total Positions: {len(positions)}*\n\n"

        for pos in positions:
            pnl = pos.get('unrealized_pnl', 0)
            pnl_emoji = "🟢" if pnl and pnl > 0 else "🔴"

            report += f"{pnl_emoji} *{pos['symbol']}* ({pos['side'].upper()})\n"
            report += f"├─ Bot: `{pos['bot_id']}`\n"
            report += f"├─ Size: {format_number(pos['size'], 4)}\n"
            report += f"├─ Entry: ${format_number(pos['avg_entry_price'])}\n"
            if pos.get('current_price'):
                report += f"├─ Current: ${format_number(pos['current_price'])}\n"
            report += f"├─ P&L: ${format_pnl(pnl)} ({format_percentage(pos.get('unrealized_pnl_pct'))})\n"

            if pos.get('stop_loss'):
                report += f"├─ SL: ${format_number(pos['stop_loss'])}\n"
            if pos.get('take_profit'):
                report += f"├─ TP: ${format_number(pos['take_profit'])}\n"

            opened_at = pos.get('opened_at')
            if opened_at:
                report += f"└─ Opened: {opened_at.strftime('%Y-%m-%d %H:%M')}\n"

            report += "\n"

    await update.message.reply_text(report, parse_mode='Markdown')


async def trades_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /trades [bot_id] [limit] - Display recent trades

    Examples:
        /trades - Last 10 trades (all bots)
        /trades alpha - Last 10 trades (alpha only)
        /trades alpha 20 - Last 20 trades (alpha only)
    """
    analytics = get_analytics()

    # Parse arguments
    bot_id = None
    limit = 10

    if len(context.args) >= 1:
        bot_id = context.args[0].lower()
        bot_mapping = {
            'alpha': 'shortseller_001',
            'bravo': 'lxalgo_001',
            'charlie': 'momentum_001'
        }
        bot_id = bot_mapping.get(bot_id, bot_id)

    if len(context.args) >= 2:
        try:
            limit = min(int(context.args[1]), 50)  # Max 50 trades
        except ValueError:
            limit = 10

    trades = analytics.get_recent_trades(bot_id, limit)

    report = f"📋 *RECENT TRADES*\n"
    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"Showing last {len(trades)} trades\n\n"

    if not trades:
        report += "*No trades found*\n"
    else:
        for trade in trades:
            # Status emoji
            if trade.get('exit_time'):
                pnl = trade.get('pnl_usd', 0)
                emoji = "🟢" if pnl and pnl > 0 else "🔴"
            else:
                emoji = "🟡"  # Open trade

            report += f"{emoji} *{trade['symbol']}* - {trade['side'].upper()}\n"
            report += f"├─ ID: `{trade['trade_id'][:12]}...`\n"
            report += f"├─ Bot: `{trade['bot_id']}`\n"
            report += f"├─ Entry: ${format_number(trade['entry_price'])}\n"

            if trade.get('exit_price'):
                report += f"├─ Exit: ${format_number(trade['exit_price'])}\n"
                report += f"├─ P&L: ${format_pnl(trade.get('pnl_usd'))} ({format_percentage(trade.get('pnl_pct'))})\n"
                if trade.get('exit_reason'):
                    report += f"├─ Reason: {trade['exit_reason']}\n"

            report += f"├─ Status: {trade['status']}\n"
            entry_time = trade.get('entry_time')
            if entry_time:
                report += f"└─ Time: {entry_time.strftime('%m-%d %H:%M')}\n"

            report += "\n"

    await update.message.reply_text(report, parse_mode='Markdown')


async def daily_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /daily [bot_id] [days] - Daily performance breakdown

    Examples:
        /daily - Last 7 days (all bots)
        /daily alpha - Last 7 days (alpha only)
        /daily alpha 14 - Last 14 days (alpha only)
    """
    analytics = get_analytics()

    # Parse arguments
    bot_id = None
    days = 7

    if len(context.args) >= 1:
        bot_id = context.args[0].lower()
        bot_mapping = {
            'alpha': 'shortseller_001',
            'bravo': 'lxalgo_001',
            'charlie': 'momentum_001'
        }
        bot_id = bot_mapping.get(bot_id, bot_id)

    if len(context.args) >= 2:
        try:
            days = min(int(context.args[1]), 30)
        except ValueError:
            days = 7

    performance = analytics.get_daily_performance(bot_id, days)

    report = f"📅 *DAILY PERFORMANCE*\n"
    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"Period: Last {days} days\n\n"

    if not performance:
        report += "*No trading activity in this period*\n"
    else:
        total_pnl = 0
        total_trades = 0

        for day in performance:
            daily_pnl = day.get('daily_pnl', 0)
            total_pnl += daily_pnl if daily_pnl else 0
            total_trades += day.get('trades', 0)

            emoji = "🟢" if daily_pnl and daily_pnl > 0 else "🔴" if daily_pnl and daily_pnl < 0 else "⚪"

            report += f"{emoji} *{day['trade_date']}*\n"
            report += f"├─ Trades: {day.get('trades', 0)}\n"
            report += f"├─ W/L: {day.get('wins', 0)}/{day.get('losses', 0)}\n"
            report += f"├─ P&L: ${format_pnl(daily_pnl)}\n"
            report += f"└─ Avg: ${format_pnl(day.get('avg_pnl'))}\n\n"

        # Summary
        report += f"━━━━━━━━━━━━━━━━━━━━━\n"
        report += f"*PERIOD SUMMARY*\n"
        report += f"├─ Total Trades: {total_trades}\n"
        report += f"└─ Total P&L: ${format_pnl(total_pnl)}\n"

    await update.message.reply_text(report, parse_mode='Markdown')


async def cache_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cache - Display Redis cache statistics
    """
    analytics = get_analytics()
    stats = analytics.get_redis_stats()

    report = f"💾 *CACHE STATISTICS*\n"
    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    if stats:
        report += f"*Redis Cache Status*\n"
        report += f"├─ Total Keys: {format_number(stats.get('total_keys', 0), 0)}\n"
        report += f"├─ Memory Used: {stats.get('used_memory', 'N/A')}\n"
        report += f"├─ Clients: {stats.get('connected_clients', 0)}\n"
        report += f"├─ Uptime: {stats.get('uptime_days', 0)} days\n"
        report += f"└─ Hit Rate: {format_percentage(stats.get('hit_rate', 0), False)}\n"
    else:
        report += "*Cache unavailable*\n"

    await update.message.reply_text(report, parse_mode='Markdown')


async def quick_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /quick - Quick trading status summary
    """
    analytics = get_analytics()

    # Get portfolio summary
    portfolio = analytics.get_portfolio_summary()

    # Get today's trading
    trading_today = analytics.get_trading_summary(days=1)

    # Get active positions
    positions = analytics.get_active_positions()

    report = f"⚡ *QUICK STATUS*\n"
    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    # Portfolio
    if portfolio:
        report += f"*PORTFOLIO*\n"
        report += f"├─ Bots: {portfolio.get('active_bots', 0)}/{portfolio.get('total_bots', 0)} active\n"
        report += f"└─ Equity: ${format_number(portfolio.get('total_equity'))}\n\n"

    # Today's trading
    if trading_today:
        pnl_today = trading_today.get('total_pnl', 0)
        emoji = "🟢" if pnl_today and pnl_today > 0 else "🔴"

        # Show fills if no completed trades yet
        closed = trading_today.get('closed_trades', 0)
        fills = trading_today.get('filled_trades', 0)

        report += f"*TODAY*\n"
        if closed > 0:
            report += f"├─ Trades: {closed}\n"
            report += f"├─ W/L: {trading_today.get('winning_trades', 0)}/{trading_today.get('losing_trades', 0)}\n"
            report += f"{emoji} P&L: ${format_pnl(pnl_today)}\n\n"
        else:
            # Show fills (entries) instead
            report += f"├─ Fills: {fills}\n"
            report += f"├─ Completed: 0\n"
            report += f"⚪ P&L: Pending\n\n"

    # Positions
    report += f"*POSITIONS*\n"
    report += f"└─ Open: {len(positions)}\n\n"

    report += f"━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"Use `/analytics` for detailed report"

    await update.message.reply_text(report, parse_mode='Markdown')
