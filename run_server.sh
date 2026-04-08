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

echo "[INFO] Starting FastAPI on http://0.0.0.0:8080"
echo "[INFO] Running in background (nohup). Logs: server.log"

# Run the server in the background
nohup uvicorn app.server:app --host 0.0.0.0 --port 8080 > server.log 2>&1 &


echo "[INFO] Server PID: $!"
echo "To stop the server, run: kill $!"
