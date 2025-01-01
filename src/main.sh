#!/usr/bin/env bash

ENV="${ENV:-PRODUCTION}"

if [ "$ENV" = "PRODUCTION" ]; then
    echo "Worker Initiated"
    echo "Starting Runpod Handler"
    python -u "/app/handler.py"
else
    echo "Local Test Worker Initiated"
    echo "Starting Test Runpod Handler"
    python -u "src/handler.py" --rp_serve_api --rp_api_host="0.0.0.0"
fi
