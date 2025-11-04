Comprehensive Guide: Building a Scalable, Secure Trading Bot SystemThis guide provides a two-phase plan to migrate your existing trading bot projects into a single, robust, and scalable "Service Hub" architecture using Docker. This design simplifies management, enhances security, and allows for the easy integration of future projects.Introduction: The "Service Hub" ArchitectureThe core concept is to stop managing separate systems. Instead, you will build one central "Service Hub" that provides core services (data, caching, logging) to all your bots.Core Services: Postgres, InfluxDB, and Redis run as shared, central services.Shared Client: The data_recorder is a shared client that feeds the hub.Bot Clients: Your trading bots (bot_1, bot_2, bot_3, etc.) are individual "clients" that connect to the hub to get data and store their state.This "hub-and-spoke" model makes adding a new project (bot_4) as simple as plugging in a new client.PrerequisitesA Linux Server (VPS): A fresh Ubuntu 22.04 server is highly recommended.Domain Name: Required for Phase 2 (HTTPS/SSL).Docker & Docker Compose: Must be installed on your server.Your Bot Projects: The Python code for your existing trading bots.Phase 1: Build the Foundation & Migrate BotsGoal: Get your core database "hub" running and containerize your existing bots to successfully communicate with it.Step 1.1: Create Your Project StructureOrganize all your components in a single directory on your server./home/ubuntu/my_trading_system/
├── docker-compose.yml     # Our main blueprint
│
├── data_recorder/         # Folder for your data recorder
│   ├── Dockerfile
│   ├── recorder.py
│   └── requirements.txt
│
├── bot_1/                   # Folder for your first bot (project 1)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── bot_2/                   # Folder for your second bot (project 2)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
└── bot_3/                   # Folder for your third bot (project 3)
    ├── Dockerfile
    ├── main.py
    └── requirements.txt
Step 1.2: Define the Core Services (docker-compose.yml)Create the docker-compose.yml file in your main directory. This file defines your database hub.version: '3.8'

services:
  # --- 1. POSTGRES (The Permanent Record) ---
  postgres:
    image: postgres:15
    container_name: trading_postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=myuser
      - POSTGRES_PASSWORD=mysecretpgpassword # <-- CHANGE THIS
      - POSTGRES_DB=trading_db
    volumes:
      - postgres-data:/var/lib/postgresql/data
    # DO NOT add a 'ports' section. This keeps it private.

  # --- 2. INFLUXDB (The Time-Series Data) ---
  influxdb:
    image: influxdb:2.7
    container_name: trading_influxdb
    restart: unless-stopped
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=myuser
      - DOCKER_INFLUXDB_INIT_PASSWORD=mysecretinfluxpassword # <-- CHANGE THIS
      - DOCKER_INFLUXDB_INIT_ORG=my_org
      - DOCKER_INFLUXDB_INIT_BUCKET=market_data
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=mysecretinfluxtoken # <-- CHANGE THIS
    volumes:
      - influxdb-data:/var/lib/influxdb2
    # DO NOT add a 'ports' section.

  # --- 3. REDIS (The Live State Cache) ---
  redis:
    image: redis:7
    container_name: trading_redis
    restart: unless-stopped
    command: redis-server --requirepass mysecretredispassword # <-- CHANGE THIS
    volumes:
      - redis-data:/data
    # DO NOT add a 'ports' section.

# --- Define the persistent volumes ---
volumes:
  postgres-data:
  influxdb-data:
  redis-data:
Step 1.3: Initialize Your Databases (One-Time Task)Run docker-compose up -d postgres to start only Postgres.Connect to your Postgres database (using docker exec -it trading_postgres psql -U myuser -d trading_db or a GUI tool) and create your tables. This is where you add the bot_id column for segregation./* init_schema.sql */

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) UNIQUE NOT NULL,
    bot_id VARCHAR(50) NOT NULL, -- <-- The crucial column!
    symbol VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    side VARCHAR(10),
    qty DECIMAL,
    price DECIMAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fills (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL,
    bot_id VARCHAR(50) NOT NULL, -- <-- The crucial column!
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10),
    qty_filled DECIMAL,
    fill_price DECIMAL,
    commission DECIMAL,
    filled_at TIMESTAMP WITH TIME ZONE
);

-- Add indexes for faster lookups by bot
CREATE INDEX idx_orders_bot_id ON orders(bot_id);
CREATE INDEX idx_fills_bot_id ON fills(bot_id);
Now run docker-compose up -d to start all services. InfluxDB will automatically create your my_org and market_data bucket on its first run.Step 1.4: Containerize the data_recorderdata_recorder/recorder.py:Your recorder script must be modified to connect to InfluxDB using its Docker service name (influxdb).# data_recorder/recorder.py
import os
from influxdb_client import InfluxDBClient, Point, WritePrecision
# ... your bybit websocket code ...

# Connect to InfluxDB using its service name 'influxdb'
INFLUX_URL = "http://influxdb:8086"
INFLUX_TOKEN = "mysecretinfluxtoken" # Use your token from Step 1.2
INFLUX_ORG = "my_org"
INFLUX_BUCKET = "market_data"

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api()

def on_kline_message(msg):
    # ... parse kline data from msg (symbol, open, high, etc.)...
    point = (
        Point("kline")
        .tag("symbol", symbol)
        .field("open", open_price)
        .field("high", high_price)
        .field("low", low_price)
        .field("close", close_price)
        .field("volume", volume)
        .time(timestamp, WritePrecision.MS)
    )
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
    print(f"Recorded candle for {symbol}")

# ... your websocket run loop ...
data_recorder/Dockerfile:FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY recorder.py .
CMD ["python", "recorder.py"]
Add to docker-compose.yml:Add this service definition inside the services: block of your docker-compose.yml.# ... inside docker-compose.yml services:
# ... (postgres, influxdb, redis definitions) ...

  data_recorder:
    build: ./data_recorder
    container_name: trading_recorder
    restart: unless-stopped
    depends_on:
      - influxdb # Ensures influx is healthy before starting
Step 1.5: Adapt & Containerize Your Existing BotsThis is the core migration step. Repeat this for bot_1, bot_2, and bot_3.Create Dockerfile: Add a Dockerfile to each bot's folder (e.g., bot_1/Dockerfile). It's identical to the recorder's.FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["python", "main.py"]
Adapt Bot Code (main.py): This is the most important part. You must modify your bot's code to:Read its BOT_ID from an environment variable.Connect to postgres, influxdb, and redis using their Docker service names.Use the BOT_ID when writing to Postgres and Redis to prevent state collision.# Example: bot_1/main.py
import os
import redis
import psycopg2
from influxdb_client import InfluxDBClient

# --- 1. GET BOT IDENTITY (from docker-compose) ---
BOT_ID = os.environ.get('BOT_ID')
if not BOT_ID:
    raise ValueError("BOT_ID environment variable not set.")

print(f"Starting bot with ID: {BOT_ID}")

# --- 2. CONNECT TO DATABASES (use service names as hosts) ---
db_conn = psycopg2.connect(
    host="postgres",
    database="trading_db",
    user="myuser",
    password="mysecretpgpassword" # Use your password
)

redis_client = redis.Redis(
    host="redis",
    port=6379,
    password="mysecretredispassword", # Use your password
    decode_responses=True
)

influx_client = InfluxDBClient(
    url="http://influxdb:8086",
    token="mysecretinfluxtoken", # Use your token
    org="my_org"
)
query_api = influx_client.query_api()

# --- 3. USE REDIS FOR STATE (with prefixed keys) ---
def set_position(symbol, amount):
    redis_key = f"{BOT_ID}:position:{symbol}"
    redis_client.set(redis_key, amount)
    print(f"State saved for {redis_key}")

def get_position(symbol):
    redis_key = f"{BOT_ID}:position:{symbol}"
    return redis_client.get(redis_key)

# --- 4. USE POSTGRES FOR LEDGER (with bot_id column) ---
def record_new_order(order_data):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders (order_id, bot_id, symbol, status, qty)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                order_data['orderId'],
                BOT_ID,  # <-- Insert the bot's ID
                order_data['symbol'],
                order_data['status'],
                order_data['qty']
            )
        )
    db_conn.commit()
    print(f"Order recorded for {BOT_ID}")

# --- ON SCRIPT STARTUP (Example of robustness) ---
# Your bot can now ask Redis "Who am I?" on restart
current_pos = get_position("BTCUSDT")
if current_pos:
    print(f"{BOT_ID} restarting, found existing position: {current_pos}")

# ... your bot's main trading loop ...
Add Bots to docker-compose.yml:Add your three bots to the services: block. Notice how we pass the BOT_ID and (for now) the API keys as environment variables.# ... inside docker-compose.yml services:
# ... (postgres, influxdb, redis, data_recorder) ...

  bot_1:
    build: ./bot_1
    container_name: trading_bot_1
    restart: unless-stopped
    depends_on: [postgres, influxdb, redis]
    environment:
      - BOT_ID=bot_1_momentum # Give it a unique, descriptive name
      - BYBIT_API_KEY=key_for_bot_1
      - BYBIT_API_SECRET=secret_for_bot_1

  bot_2:
    build: ./bot_2
    container_name: trading_bot_2
    restart: unless-stopped
    depends_on: [postgres, influxdb, redis]
    environment:
      - BOT_ID=bot_2_mean_reversion
      - BYBIT_API_KEY=key_for_bot_2
      - BYBIT_API_SECRET=secret_for_bot_2

  bot_3:
    build: ./bot_3
    container_name: trading_bot_3
    restart: unless-stopped
    depends_on: [postgres, influxdb, redis]
    environment:
      - BOT_ID=bot_3_arbitrage
      - BYBIT_API_KEY=key_for_bot_3
      - BYBIT_API_SECRET=secret_for_bot_3
Step 1.6: Launch and TestYou are now ready to launch the entire system.Build all images:docker-compose buildLaunch all services in detached (background) mode:docker-compose up -dCheck the logs to see them connect:docker-compose logs -f bot_1docker-compose logs -f data_recorderIf all goes well, data_recorder is populating InfluxDB, and your bots are reading from it and correctly writing their trades to Postgres and their state to Redis, all with their unique bot_id.Phase 2: Monitoring & Security HardeningGoal: Secure your server and API keys, and gain visual insight into your system's performance.Step 2.1: Add Grafana for MonitoringAdd to docker-compose.yml:Add this grafana service to your services: block.# ... inside docker-compose.yml services:
# ... (all your other services) ...

  grafana:
    image: grafana/grafana:latest
    container_name: trading_grafana
    restart: unless-stopped
    # We will expose port 3000 temporarily to set it up.
    # This will be removed and replaced by Caddy.
    ports:
      - "3000:3000" 
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - postgres
      - influxdb
      - redis

# ... inside docker-compose.yml volumes:
# ... (other volumes) ...
  grafana-data:
Relaunch & Configure:Run docker-compose up -d to start Grafana.Open your browser to http://YOUR_SERVER_IP:3000 (user/pass: admin/admin). Change your password.Go to Connections > Data Sources and add your 3 services:InfluxDB:URL: http://influxdb:8086Auth: Basic AuthUser: myuserPass: mysecretinfluxpassword(For InfluxDB 2.x, you might use the Token) Token: mysecretinfluxtokenOrganization: my_orgPostgreSQL:Host: postgres:5432DB: trading_dbUser: myuserPass: mysecretpgpasswordRedis:Host: redis:6379Pass: mysecretredispasswordYou can now build dashboards to see price data, PnL per bot (using WHERE bot_id = 'bot_1'), and live positions from Redis (using GET "bot_1:position:BTCUSDT").Step 2.2: Implement Server Firewall (UFW)You must lock down your server from the public internet.# Allow your SSH port (change 22 if you use a custom port)
sudo ufw allow 22/tcp 

# We will use Caddy for HTTPS, so allow web ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# DENY everything else by default
sudo ufw default deny incoming

# Enable the firewall
sudo ufw enable
Step 2.3: Secure Grafana (Reverse Proxy + HTTPS)We will use Caddy to automatically add HTTPS (SSL) to your Grafana dashboard. This is far more secure than exposing port 3000.Create a Caddyfile: In your main my_trading_system directory:# Caddyfile
# Replace your-domain.com with your actual domain
your-domain.com {
    # Caddy automatically handles SSL certs
    # It forwards traffic internally to the grafana container
    reverse_proxy grafana:3000
}
Update docker-compose.yml:REMOVE the ports: section from grafana.ADD the caddy service.# ... inside docker-compose.yml services:
  grafana:
    image: grafana/grafana:latest
    container_name: trading_grafana
    restart: unless-stopped
    # REMOVE THIS LINE: ports: - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on: [postgres, influxdb, redis]

  caddy:
    image: caddy:latest
    container_name: trading_proxy
    restart: unless-stopped
    ports:
      - "80:80"   # For HTTP challenge
      - "443:443" # For HTTPS
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config

# ... inside docker-compose.yml volumes:
# ... (other volumes) ...
  caddy-data:
  caddy-config:
Relaunch: Run docker-compose up -d. Caddy will now serve your Grafana dashboard securely at https://your-domain.com.Step 2.4: Secure Your API Keys (Docker Secrets)This is the most important security step. Do not leave API keys in docker-compose.yml as plain text.On your server (one time per secret):# For Bot 1
echo "bot1_bybit_key" | docker secret create bot_1_api_key -
echo "bot1_bybit_secret" | docker secret create bot_1_api_secret -

# Repeat for bot 2 and 3...
echo "bot2_bybit_key" | docker secret create bot_2_api_key -
echo "bot2_bybit_secret" | docker secret create bot_2_api_secret -
Update docker-compose.yml:REMOVE the environment: block with the keys from bot_1, bot_2, bot_3.ADD a secrets: block to each bot.ADD a top-level secrets: block at the very bottom.# ... inside docker-compose.yml
services:
  bot_1:
    build: ./bot_1
    # ...
    # REMOVE environment block with keys
    environment:
      - BOT_ID=bot_1_momentum # Keep this one
    secrets:
      - bot_1_api_key
      - bot_1_api_secret

  bot_2:
    # ...
    environment:
      - BOT_ID=bot_2_mean_reversion
    secrets:
      - bot_2_api_key
      - bot_2_api_secret

  # ... repeat for bot_3 ...

# ... all other services ...

# --- Define all secrets as external (at the bottom of the file) ---
secrets:
  bot_1_api_key:
    external: true
  bot_1_api_secret:
    external: true
  bot_2_api_key:
    external: true
  bot_2_api_secret:
    external: true
  # ... repeat for bot 3 keys ...
Update Your Bot Code: Modify your bots to read keys from the secret files that Docker creates.# Example: bot_1/main.py

# Add this function to read secrets
def get_secret(secret_name):
    try:
        # Secrets are mounted as files
        with open(f'/run/secrets/{secret_name}', 'r') as f:
            return f.read().strip()
    except IOError:
        print(f"Error reading secret: {secret_name}")
        return None

# Get keys at the start of your script
API_KEY = get_secret('bot_1_api_key')
API_SECRET = get_secret('bot_1_api_secret')

if not API_KEY or not API_SECRET:
    raise ValueError("API secrets not found! Exiting.")

# ... rest of your bot code ...
# Your Bybit client will now use these variables
Relaunch your bots:docker-compose up -d --build --no-deps bot_1 bot_2 bot_3Step 2.5: Final Security Checks (Mandatory)Bybit API Whitelisting: Log in to Bybit. Edit your API keys and bind them to your server's static IP address. This is your single most powerful defense. If your keys are stolen, they are useless.Disable "Withdrawal" permissions on all your API keys.Integrating Future Projects (e.g., bot_4)This is now extremely simple.Create a new folder: /home/ubuntu/my_trading_system/bot_4/Write your bot_4/main.py following the rules:Read BOT_ID from os.environ.Connect to hosts postgres, redis, influxdb with the standard passwords.Use the BOT_ID in all SQL queries and Redis keys.Read API keys from /run/secrets/bot_4_api_key.Add the new key to Docker Secrets:echo "bot4_key" | docker secret create bot_4_api_key -echo "bot4_secret" | docker secret create bot_4_api_secret -Add the new service to docker-compose.yml:# ... inside services:
  bot_4:
    build: ./bot_4
    container_name: trading_bot_4
    restart: unless-stopped
    depends_on: [postgres, influxdb, redis]
    environment:
      - BOT_ID=bot_4_new_strategy
    secrets:
      - bot_4_api_key
      - bot_4_api_secret

# ... inside secrets:
  bot_4_api_key:
    external: true
  bot_4_api_secret:
    external: true
Launch just the new bot:docker-compose up -d --build --no-deps bot_4You now have a robust, secure, and infinitely scalable trading system. Each part is decoupled, persistent, and observable.