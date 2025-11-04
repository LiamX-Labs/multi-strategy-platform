FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI for container management
RUN apt-get update && \
    apt-get install -y docker.io && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Run the bot
CMD ["python", "bot.py"]
