"""
Mapper to convert Bybit closed PnL records to completed_trades schema
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class ClosedPnLMapper:
    """Maps Bybit closed PnL records to completed_trades format"""

    @staticmethod
    def parse_order_link_id(order_link_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """
        Parse orderLinkId to extract bot_id and reason
        Format: bot_id:reason:timestamp
        """
        if not order_link_id:
            return None, None

        parts = order_link_id.split(':')
        if len(parts) >= 2:
            return parts[0], parts[1]  # bot_id, reason
        return None, None

    @staticmethod
    def map_closed_pnl_to_trade(record: Dict, bot_id: str) -> Optional[Dict]:
        """
        Map a Bybit closed PnL record to completed_trades schema

        Args:
            record: Bybit closed PnL record
            bot_id: Bot identifier to assign to this trade

        Bybit closed PnL fields:
        - symbol, orderId, side, qty, orderPrice
        - avgEntryPrice, avgExitPrice, closedPnl
        - cumEntryValue, cumExitValue, closedSize
        - orderType, execType, fillCount, leverage
        - openFee, closeFee, createdTime, updatedTime

        Returns:
            Dict matching completed_trades schema, or None if invalid
        """
        try:
            # Extract basic info
            symbol = record.get('symbol')
            order_id = record.get('orderId')
            side = record.get('side')  # Buy or Sell
            qty = float(record.get('closedSize', 0))

            # Parse timestamps (milliseconds to datetime)
            created_time_ms = int(record.get('createdTime', 0))
            updated_time_ms = int(record.get('updatedTime', 0))

            entry_time = datetime.fromtimestamp(created_time_ms / 1000, tz=timezone.utc)
            exit_time = datetime.fromtimestamp(updated_time_ms / 1000, tz=timezone.utc)

            # If times are equal, add 1 second to exit time to satisfy database constraint
            if exit_time <= entry_time:
                exit_time = entry_time + timedelta(seconds=1)
                updated_time_ms = int(exit_time.timestamp() * 1000)

            # Extract prices and PnL
            avg_entry_price = float(record.get('avgEntryPrice', 0))
            avg_exit_price = float(record.get('avgExitPrice', 0))
            closed_pnl = float(record.get('closedPnl', 0))

            # Extract fees
            open_fee = float(record.get('openFee', 0))
            close_fee = float(record.get('closeFee', 0))
            total_commission = abs(open_fee) + abs(close_fee)

            # Calculate net PnL (closed_pnl from Bybit already includes fees)
            gross_pnl = closed_pnl + total_commission  # Reconstruct gross PnL
            net_pnl = closed_pnl

            # Calculate PnL percentage
            entry_value = float(record.get('cumEntryValue', 0))
            pnl_pct = (closed_pnl / abs(entry_value) * 100) if entry_value != 0 else 0

            # Calculate holding duration
            holding_duration_seconds = int((updated_time_ms - created_time_ms) / 1000)

            # Try to extract reason from orderLinkId if available
            # Otherwise use default reason
            order_link_id = record.get('orderLinkId', '')
            _, reason = ClosedPnLMapper.parse_order_link_id(order_link_id) if order_link_id else (None, None)

            # Determine entry and exit sides
            # If side is "Buy", it means we bought to enter and sold to exit (long position)
            # If side is "Sell", it means we sold to enter and bought to exit (short position)
            if side == "Buy":
                entry_side = "Buy"
                exit_side = "Sell"
                entry_reason = reason or "long_entry"
                exit_reason = "long_exit"
            else:  # Sell
                entry_side = "Sell"
                exit_side = "Buy"
                entry_reason = reason or "short_entry"
                exit_reason = "short_exit"

            # Generate trade_id
            trade_id = f"{bot_id}_{symbol}_{created_time_ms}"

            # Build completed trade record
            trade = {
                'trade_id': trade_id,
                'bot_id': bot_id,
                'symbol': symbol,
                'entry_order_id': order_id,
                'entry_client_order_id': order_link_id,
                'entry_side': entry_side,
                'entry_price': avg_entry_price,
                'entry_qty': qty,
                'entry_time': entry_time,
                'entry_reason': entry_reason,
                'entry_commission': abs(open_fee),
                'exit_order_id': order_id,  # Same order for now, could be different
                'exit_client_order_id': order_link_id,
                'exit_side': exit_side,
                'exit_price': avg_exit_price,
                'exit_qty': qty,
                'exit_time': exit_time,
                'exit_reason': exit_reason,
                'exit_commission': abs(close_fee),
                'gross_pnl': gross_pnl,
                'net_pnl': net_pnl,
                'pnl_pct': pnl_pct,
                'total_commission': total_commission,
                'holding_duration_seconds': holding_duration_seconds,
                'source': 'bybit_api'
            }

            return trade

        except Exception as e:
            logger.error(f"Failed to map closed PnL record: {str(e)}, record: {record}")
            return None

    @staticmethod
    def map_all(records: list[Dict], bot_id: str) -> list[Dict]:
        """Map all closed PnL records for a specific bot"""
        trades = []
        for record in records:
            trade = ClosedPnLMapper.map_closed_pnl_to_trade(record, bot_id)
            if trade:
                trades.append(trade)
        return trades
