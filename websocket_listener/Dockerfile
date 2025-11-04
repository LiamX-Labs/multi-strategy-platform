FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY listener.py .

# Create logs directory
RUN mkdir -p /app/logs

# Run the listener
CMD ["python", "listener.py"]
