"""
Trade Matcher - Pairs buy/sell executions to form completed trades
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


class TradeMatcher:
    """Matches buy and sell executions to form completed trades"""

    @staticmethod
    def parse_client_order_id(client_order_id: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse client order ID to extract bot_id, reason, and timestamp

        Format: "bot_id:reason:timestamp"
        Example: "shortseller_001:take_profit:1678886700"

        Returns:
            Tuple of (bot_id, reason, timestamp_str) or (None, None, None) if parsing fails
        """
        if not client_order_id:
            return None, None, None

        try:
            parts = client_order_id.split(':')
            if len(parts) >= 3:
                bot_id = parts[0]
                reason = parts[1]
                timestamp = parts[2]
                return bot_id, reason, timestamp
            elif len(parts) == 2:
                # Fallback for format without timestamp
                bot_id = parts[0]
                reason = parts[1]
                return bot_id, reason, None
        except Exception as e:
            logger.warning(f"Failed to parse client_order_id '{client_order_id}': {str(e)}")

        return None, None, None

    @staticmethod
    def extract_bot_id_from_executions(executions: List[Dict]) -> Optional[str]:
        """Extract bot_id from executions by parsing orderLinkId"""
        for exec in executions:
            order_link_id = exec.get('orderLinkId')
            if order_link_id:
                bot_id, _, _ = TradeMatcher.parse_client_order_id(order_link_id)
                if bot_id:
                    return bot_id
        return None

    @staticmethod
    def group_executions_by_symbol(executions: List[Dict]) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Group executions by symbol and side

        Returns:
            Dict with structure: {symbol: {'Buy': [...], 'Sell': [...]}}
        """
        grouped = defaultdict(lambda: {'Buy': [], 'Sell': []})

        for exec in executions:
            symbol = exec.get('symbol')
            side = exec.get('side')

            if symbol and side in ['Buy', 'Sell']:
                grouped[symbol][side].append(exec)

        return dict(grouped)

    @staticmethod
    def match_fifo(buys: List[Dict], sells: List[Dict]) -> List[Dict]:
        """
        Match buy and sell executions using FIFO (First In, First Out) method

        Args:
            buys: List of buy executions (sorted by execTime)
            sells: List of sell executions (sorted by execTime)

        Returns:
            List of matched trade dictionaries
        """
        # Sort by execution time
        buys_sorted = sorted(buys, key=lambda x: int(x.get('execTime', 0)))
        sells_sorted = sorted(sells, key=lambda x: int(x.get('execTime', 0)))

        matched_trades = []
        sell_idx = 0

        for buy_exec in buys_sorted:
            # Find the next sell after this buy
            while sell_idx < len(sells_sorted):
                sell_exec = sells_sorted[sell_idx]

                buy_time = int(buy_exec.get('execTime', 0))
                sell_time = int(sell_exec.get('execTime', 0))

                # Sell must come after buy
                if sell_time > buy_time:
                    # Match found
                    matched_trade = TradeMatcher._create_matched_trade(buy_exec, sell_exec)
                    matched_trades.append(matched_trade)

                    sell_idx += 1  # Move to next sell
                    break
                else:
                    # This sell is before the buy, skip it
                    sell_idx += 1

        logger.info(f"Matched {len(matched_trades)} trades from {len(buys)} buys and {len(sells)} sells")
        return matched_trades

    @staticmethod
    def _create_matched_trade(buy_exec: Dict, sell_exec: Dict) -> Dict:
        """Create a matched trade dictionary from buy and sell executions"""
        # Parse client order IDs
        entry_bot_id, entry_reason, _ = TradeMatcher.parse_client_order_id(buy_exec.get('orderLinkId'))
        exit_bot_id, exit_reason, _ = TradeMatcher.parse_client_order_id(sell_exec.get('orderLinkId'))

        # Use bot_id from entry if available, otherwise from exit
        bot_id = entry_bot_id or exit_bot_id

        # Convert timestamps
        entry_time = datetime.fromtimestamp(int(buy_exec.get('execTime', 0)) / 1000, tz=timezone.utc)
        exit_time = datetime.fromtimestamp(int(sell_exec.get('execTime', 0)) / 1000, tz=timezone.utc)

        # Calculate holding duration
        holding_duration = (exit_time - entry_time).total_seconds()

        # Get prices and quantities
        entry_price = float(buy_exec.get('execPrice', 0))
        exit_price = float(sell_exec.get('execPrice', 0))
        entry_qty = float(buy_exec.get('execQty', 0))
        exit_qty = float(sell_exec.get('execQty', 0))

        # Get commissions
        entry_commission = abs(float(buy_exec.get('execFee', 0)))
        exit_commission = abs(float(sell_exec.get('execFee', 0)))
        total_commission = entry_commission + exit_commission

        # Calculate PnL (for long position: Sell - Buy)
        quantity = min(entry_qty, exit_qty)  # Use the smaller quantity if they don't match
        gross_pnl = (exit_price - entry_price) * quantity
        net_pnl = gross_pnl - total_commission

        # Calculate PnL percentage
        position_value = entry_price * quantity
        pnl_pct = (net_pnl / position_value * 100) if position_value > 0 else 0

        # Generate trade_id
        symbol = buy_exec.get('symbol')
        trade_id = f"{bot_id}_{symbol}_{int(buy_exec.get('execTime', 0))}"

        matched_trade = {
            'trade_id': trade_id,
            'bot_id': bot_id,
            'symbol': symbol,

            # Entry leg
            'entry_order_id': buy_exec.get('orderId'),
            'entry_client_order_id': buy_exec.get('orderLinkId'),
            'entry_side': buy_exec.get('side'),
            'entry_price': entry_price,
            'entry_qty': entry_qty,
            'entry_time': entry_time,
            'entry_reason': entry_reason,
            'entry_commission': entry_commission,

            # Exit leg
            'exit_order_id': sell_exec.get('orderId'),
            'exit_client_order_id': sell_exec.get('orderLinkId'),
            'exit_side': sell_exec.get('side'),
            'exit_price': exit_price,
            'exit_qty': exit_qty,
            'exit_time': exit_time,
            'exit_reason': exit_reason,
            'exit_commission': exit_commission,

            # Performance
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'pnl_pct': pnl_pct,
            'total_commission': total_commission,
            'holding_duration_seconds': int(holding_duration),

            # Metadata
            'source': 'bybit_api'
        }

        return matched_trade

    @staticmethod
    def match_all_symbols(executions: List[Dict]) -> List[Dict]:
        """
        Match all executions across all symbols

        Args:
            executions: List of all executions

        Returns:
            List of all matched trades
        """
        grouped = TradeMatcher.group_executions_by_symbol(executions)

        all_matched_trades = []

        for symbol, sides in grouped.items():
            buys = sides['Buy']
            sells = sides['Sell']

            logger.info(f"Matching {symbol}: {len(buys)} buys, {len(sells)} sells")

            matched = TradeMatcher.match_fifo(buys, sells)
            all_matched_trades.extend(matched)

        logger.info(f"Total matched trades across all symbols: {len(all_matched_trades)}")
        return all_matched_trades

    @staticmethod
    def validate_trade(trade: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a matched trade

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = [
            'trade_id', 'bot_id', 'symbol',
            'entry_price', 'entry_qty', 'entry_time',
            'exit_price', 'exit_qty', 'exit_time'
        ]

        for field in required_fields:
            if field not in trade or trade[field] is None:
                return False, f"Missing required field: {field}"

        # Validate times
        if trade['exit_time'] <= trade['entry_time']:
            return False, "Exit time must be after entry time"

        # Validate quantities (allow small differences due to partial fills)
        qty_diff = abs(trade['entry_qty'] - trade['exit_qty'])
        if qty_diff > trade['entry_qty'] * 0.01:  # Allow 1% difference
            logger.warning(f"Quantity mismatch in trade {trade['trade_id']}: "
                         f"entry={trade['entry_qty']}, exit={trade['exit_qty']}")

        # Validate prices
        if trade['entry_price'] <= 0 or trade['exit_price'] <= 0:
            return False, "Invalid prices"

        return True, None
