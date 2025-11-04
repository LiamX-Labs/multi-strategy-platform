"""
Bybit API Client for Trade Sync Service
Handles authentication and execution history fetching
"""

import time
import hmac
import hashlib
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone
from urllib.parse import unquote
import aiohttp
import logging

from config import (
    BYBIT_API_KEY,
    BYBIT_API_SECRET,
    BYBIT_REST_URL,
    RATE_LIMIT_DELAY,
    MAX_EXECUTIONS_PER_REQUEST
)

logger = logging.getLogger(__name__)


class BybitSyncClient:
    """Client for fetching execution history from Bybit API"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key or BYBIT_API_KEY
        self.api_secret = api_secret or BYBIT_API_SECRET
        self.base_url = BYBIT_REST_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_request_time = 0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _generate_signature(self, timestamp: str, params: str) -> str:
        """Generate HMAC SHA256 signature for Bybit V5 API"""
        recv_window = "5000"
        param_str = f"{timestamp}{self.api_key}{recv_window}{params}"
        logger.debug(f"Signature param_str: {param_str[:100]}...")
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        logger.debug(f"Generated signature: {signature[:20]}...")
        return signature

    async def _rate_limit(self):
        """Implement rate limiting: max 10 requests/second"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < RATE_LIMIT_DELAY:
            sleep_time = RATE_LIMIT_DELAY - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.3f}s")
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make authenticated request to Bybit API"""
        if not self.session:
            raise RuntimeError("Client session not initialized. Use 'async with' context manager.")

        await self._rate_limit()

        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"

        # Build query string (URL-decode values for signature, especially cursor parameter)
        # Bybit returns cursor URL-encoded in JSON, but expects decoded version in signature
        query_string = ""
        if params:
            sorted_params = sorted(params.items())
            # URL-decode parameter values for signature string
            decoded_params = [(k, unquote(str(v))) for k, v in sorted_params]
            query_string = "&".join([f"{k}={v}" for k, v in decoded_params])

        # Generate signature
        signature = self._generate_signature(timestamp, query_string)

        # Build headers
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }

        url = f"{self.base_url}{endpoint}"
        if query_string:
            url += f"?{query_string}"

        try:
            async with self.session.request(method, url, headers=headers, skip_auto_headers=['Content-Type']) as response:
                response.raise_for_status()
                data = await response.json()

                if data.get('retCode') != 0:
                    logger.error(f"Bybit API error: {data.get('retMsg')} (code: {data.get('retCode')})")
                    raise Exception(f"Bybit API error: {data.get('retMsg')}")

                return data.get('result', {})

        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    async def get_closed_pnl(
        self,
        category: str = "linear",
        symbol: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> Dict:
        """
        Get closed PnL (completed trades) from Bybit

        Args:
            category: Product type (linear, inverse, option)
            symbol: Trading symbol (optional, if None gets all symbols)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Number of records per request (max 100)
            cursor: Pagination cursor from previous response

        Returns:
            Dict with 'list' of closed trades and 'nextPageCursor'
        """
        params = {
            "category": category,
            "limit": min(limit, 100)
        }

        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["startTime"] = str(start_time)
        if end_time:
            params["endTime"] = str(end_time)
        if cursor:
            params["cursor"] = cursor

        logger.info(f"Fetching closed PnL: category={category}, symbol={symbol}, "
                   f"start={start_time}, end={end_time}, limit={limit}")

        result = await self._make_request("GET", "/v5/position/closed-pnl", params)

        return result

    async def get_all_closed_pnl_in_range(
        self,
        start_time: int,
        end_time: int,
        category: str = "linear",
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all closed PnL records in a time range, handling pagination

        Args:
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            category: Product type
            symbol: Trading symbol (optional)

        Returns:
            Complete list of closed PnL records in the range
        """
        all_records = []
        cursor = None

        while True:
            result = await self.get_closed_pnl(
                category=category,
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                limit=100,
                cursor=cursor
            )

            records = result.get('list', [])
            next_cursor = result.get('nextPageCursor')

            all_records.extend(records)

            logger.info(f"Fetched {len(records)} closed PnL records (total: {len(all_records)})")

            # Check if there are more pages
            if not next_cursor or not records:
                break

            cursor = next_cursor
            await asyncio.sleep(0.1)  # Small delay between paginated requests

        logger.info(f"Completed fetching {len(all_records)} total closed PnL records for range "
                   f"{datetime.fromtimestamp(start_time/1000, tz=timezone.utc)} to "
                   f"{datetime.fromtimestamp(end_time/1000, tz=timezone.utc)}")

        return all_records

    async def get_all_executions_in_range(
        self,
        start_time: int,
        end_time: int,
        category: str = "linear",
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all executions in a time range, handling pagination

        Args:
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            category: Product type
            symbol: Trading symbol (optional)

        Returns:
            Complete list of executions in the range
        """
        all_executions = []
        cursor = None

        while True:
            params = {
                "category": category,
                "limit": MAX_EXECUTIONS_PER_REQUEST,
                "startTime": str(start_time),
                "endTime": str(end_time)
            }

            if symbol:
                params["symbol"] = symbol
            if cursor:
                params["cursor"] = cursor
                logger.debug(f"Using cursor for pagination: {cursor}")

            result = await self._make_request("GET", "/v5/execution/list", params)
            executions = result.get('list', [])
            next_cursor = result.get('nextPageCursor')
            if next_cursor:
                logger.debug(f"Received nextPageCursor: {next_cursor}")

            all_executions.extend(executions)

            logger.info(f"Fetched {len(executions)} executions (total: {len(all_executions)})")

            # Check if there are more pages
            if not next_cursor or not executions:
                break

            cursor = next_cursor
            await asyncio.sleep(0.1)  # Small delay between paginated requests

        logger.info(f"Completed fetching {len(all_executions)} total executions for range "
                   f"{datetime.fromtimestamp(start_time/1000, tz=timezone.utc)} to "
                   f"{datetime.fromtimestamp(end_time/1000, tz=timezone.utc)}")

        return all_executions

    async def test_connection(self) -> bool:
        """Test API connection and credentials"""
        try:
            result = await self._make_request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
            logger.info("Bybit API connection successful")
            return True
        except Exception as e:
            logger.error(f"Bybit API connection failed: {str(e)}")
            return False
