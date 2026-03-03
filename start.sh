#!/bin/bash

# Start Celery worker in background
celery -A worker:celery_app worker --loglevel=info &

# Start Gunicorn in foreground
gunicorn app:app --bind 0.0.0.0:$PORT