#!/bin/bash
set -e

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Start FastAPI application
echo "Starting FastAPI application..."
exec uvicorn analyzer.api.main:app --host 0.0.0.0 --port 8000 --workers 4
