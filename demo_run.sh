#!/usr/bin/env bash
# Demo script to seed DB, run Flask dev server and a worker in background
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
PYTHONPATH="$ROOT_DIR"

# seed DB
python3 "$ROOT_DIR/src/seed.py"

# start flask app in background
nohup python3 -u -c "import sys, pathlib; sys.path.insert(0, str(pathlib.Path('.').resolve())); from src.partners.routes import app; app.run(host='127.0.0.1', port=5001)" > "$ROOT_DIR/partner_server.log" 2>&1 &
FLASK_PID=$!

echo "Flask server started pid=$FLASK_PID"

# start worker in background
nohup python3 -u -c "import sys, pathlib; sys.path.insert(0, str(pathlib.Path('.').resolve())); from src.partners.ingest_queue import start_worker; from pathlib import Path; start_worker(str(Path('.').resolve()/ 'app.sqlite')); import time; time.sleep(99999)" > "$ROOT_DIR/worker.log" 2>&1 &
WORKER_PID=$!

echo "Worker started pid=$WORKER_PID"

echo "Logs: partner_server.log, worker.log"
