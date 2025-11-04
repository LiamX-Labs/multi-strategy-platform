#!/usr/bin/env python3
"""
Test script to verify Bybit DEMO API credentials
Uses both pybit and direct HTTP requests
"""

import os
import sys
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')
BASE_URL = 'https://api-demo.bybit.com'

def generate_signature(timestamp, api_key, recv_window, params_string):
    """Generate HMAC SHA256 signature"""
    param_str = f"{timestamp}{api_key}{recv_window}{params_string}"
    print(f"Signature string: {param_str}")
    return hmac.new(
        API_SECRET.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_api():
    """Test API connection with simple request"""
    print(f"Testing Bybit DEMO API...")
    print(f"API Key: {API_KEY[:10]}...")
    print(f"Base URL: {BASE_URL}")

    # Test endpoint
    endpoint = "/v5/execution/list"
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    # Simple params
    params = {
        "category": "linear",
        "limit": "10"
    }

    # Build query string (sorted, no URL encoding)
    sorted_params = sorted(params.items())
    query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
    print(f"Query string: {query_string}")

    # Generate signature
    signature = generate_signature(timestamp, API_KEY, recv_window, query_string)
    print(f"Signature: {signature}")

    # Build headers
    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json"
    }

    # Make request
    url = f"{BASE_URL}{endpoint}?{query_string}"
    print(f"Request URL: {url}")

    try:
        response = requests.get(url, headers=headers)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0:
                print("\n✅ SUCCESS! API credentials are valid for DEMO environment")
                print(f"Fetched {len(data.get('result', {}).get('list', []))} executions")
                return True
            else:
                print(f"\n❌ API Error: {data.get('retMsg')} (code: {data.get('retCode')})")
                return False
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ Exception: {str(e)}")
        return False

if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        print("❌ ERROR: API credentials not found in .env file")
        sys.exit(1)

    success = test_api()
    sys.exit(0 if success else 1)
