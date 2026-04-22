#!/bin/bash

# Optimized for Render Free Tier (512MB RAM, 0.5 CPU)
# Runs both FastAPI and Celery worker in single instance

set -e

# Get port from environment or default to 8000
PORT=${PORT:-8000}

echo "🚀 Starting HireIQ on Render Free Tier..."
echo "   Port: $PORT"
echo "   Memory: 512MB available"
echo "   CPU: 0.5 cores shared"

# Start Celery worker in background (single process, single thread)
echo "📦 Starting Celery worker (background)..."
celery -A app.workers.resume_processor worker \
  --loglevel=info \
  --concurrency=1 \
  --prefetch-multiplier=1 \
  --max-tasks-per-child=100 \
  --time-limit=600 \
  --soft-time-limit=580 \
  > /tmp/celery.log 2>&1 &

CELERY_PID=$!
echo "   Celery PID: $CELERY_PID"

# Give Celery time to start
sleep 3

# Check if Celery started successfully
if ! kill -0 $CELERY_PID 2>/dev/null; then
  echo "❌ Celery failed to start. Check /tmp/celery.log"
  cat /tmp/celery.log
  exit 1
fi

echo "✅ Celery started"

# Start FastAPI app
echo "🌐 Starting FastAPI app..."
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --workers=1 \
  --loop=uvloop \
  --http=httptools \
  --timeout-keep-alive=30