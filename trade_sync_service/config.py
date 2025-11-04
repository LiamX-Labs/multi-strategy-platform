"""
Configuration for Trade Sync Service
Syncs completed trades from Bybit API to PostgreSQL
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# PostgreSQL Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'pgbouncer')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '6432'))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'trading_db')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'trading_user')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'trading_password')

# Bybit API Configuration
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET', '')
BYBIT_DEMO = os.getenv('BYBIT_DEMO', 'false').lower() == 'true'
BYBIT_TESTNET = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'

# Per-bot API keys (each bot has its own Bybit API key)
BOT_API_KEYS = {
    'shortseller_001': {
        'api_key': os.getenv('SHORTSELLER_BYBIT_API_KEY', BYBIT_API_KEY),
        'api_secret': os.getenv('SHORTSELLER_BYBIT_API_SECRET', BYBIT_API_SECRET)
    },
    'lxalgo_001': {
        'api_key': os.getenv('LXALGO_BYBIT_API_KEY', BYBIT_API_KEY),
        'api_secret': os.getenv('LXALGO_BYBIT_API_SECRET', BYBIT_API_SECRET)
    },
    'momentum_001': {
        'api_key': os.getenv('MOMENTUM_BYBIT_API_KEY', BYBIT_API_KEY),
        'api_secret': os.getenv('MOMENTUM_BYBIT_API_SECRET', BYBIT_API_SECRET)
    }
}

# Bybit API URLs
if BYBIT_DEMO:
    BYBIT_REST_URL = 'https://api-demo.bybit.com'
elif BYBIT_TESTNET:
    BYBIT_REST_URL = 'https://api-testnet.bybit.com'
else:
    BYBIT_REST_URL = 'https://api.bybit.com'

# Rate Limiting Configuration
BYBIT_RATE_LIMIT_PER_SECOND = 10  # Bybit allows 10 requests/second for private endpoints
RATE_LIMIT_DELAY = 0.12  # 120ms between requests (safer than 100ms for 10 req/sec)

# Sync Configuration
BACKFILL_MONTHS = 3  # Initial backfill period
HOURLY_SYNC_OVERLAP_HOURS = 2  # Fetch last 2 hours to ensure no gaps
SYNC_INTERVAL_SECONDS = 3600  # 1 hour

# Batch Configuration
BACKFILL_BATCH_DAYS = 1  # Backfill in 1-day chunks
MAX_EXECUTIONS_PER_REQUEST = 100  # Bybit API limit

# Registered Bots
REGISTERED_BOTS = [
    'shortseller_001',
    'lxalgo_001',
    'momentum_001'
]

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'logs/sync.log')

# Monitoring
ENABLE_TELEGRAM_ALERTS = os.getenv('ENABLE_TELEGRAM_ALERTS', 'false').lower() == 'true'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Redis Configuration (for distributed locking)
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_SYNC_DB', '1'))  # Use separate DB from main app
