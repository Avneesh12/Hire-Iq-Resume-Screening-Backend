#!/bin/bash

# start celery in background
celery -A app.workers.resume_processor worker --loglevel=info &

# start fastapi
uvicorn main:app --host 0.0.0.0 --port $PORT