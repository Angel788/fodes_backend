#!/bin/bash

# FastAPI Server Runner for Linux
echo "--- FODES FastAPI Server ---"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "[INFO] .venv directory not found. Creating virtual environment..."
    python3 -m venv .venv
    
    echo "[INFO] Installing dependencies..."
    source .venv/bin/activate
    # Using the specific filename found in the directory
    if [ -f "requiremnts.txt" ]; then
        pip install --upgrade pip
        pip install -r requiremnts.txt
    else
        echo "[ERROR] requiremnts.txt not found!"
    fi
else
    echo "[INFO] Activating virtual environment..."
    source .venv/bin/activate
fi

echo "[INFO] Starting FastAPI on http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server."

# Run the server
uvicorn app.server:app --reload --host 0.0.0.0 --port 8000
