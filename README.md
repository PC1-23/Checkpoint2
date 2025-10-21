# Partner (VAR) Catalog Ingest — Demo

This repository implements a partner catalog ingest flow (CSV/JSON feeds) with:

- Adapters (CSV/JSON) to normalize partner feeds.
- Validation and upsert into a product catalog (SQLite).
- Idempotency via feed checksums.
- Durable DB-backed job queue + worker for async processing.
- Retry with exponential backoff + jitter.
- Basic metrics and admin endpoints to inspect and requeue jobs.

Quick start (macOS / Linux)

1. Create a virtualenv and install deps (if any):

   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt  # optional; repo is mostly stdlib

2. Seed the local DB (optional) and run the dev server & worker:

   # seed DB (creates app.sqlite)
   python src/seed.py

   # start the Flask app (single-process dev)
   python -c "import sys, pathlib; sys.path.insert(0, str(pathlib.Path('.').resolve())); from src.partners.routes import app; app.run(host='127.0.0.1', port=5001)"

   # in another terminal start a worker (it will process enqueued jobs)
   python -c "import sys, pathlib; sys.path.insert(0, str(pathlib.Path('.').resolve())); from src.partners.ingest_queue import start_worker; from pathlib import Path; start_worker(str(Path('.').resolve()/ 'app.sqlite'))"

3. POST a JSON feed (sync):

   curl -X POST 'http://127.0.0.1:5001/partner/ingest?async=0' \
     -H 'Content-Type: application/json' -H 'X-API-Key: test-key' \
     --data '[{"sku":"sku-1","name":"Demo Product","price":9.99,"stock":10}]'

4. POST a JSON feed (async):

   curl -X POST 'http://127.0.0.1:5001/partner/ingest?async=1' \
     -H 'Content-Type: application/json' -H 'X-API-Key: test-key' \
     --data '[{"sku":"sku-1","name":"Demo Product","price":9.99,"stock":10}]'

5. Inspect jobs (admin):

   export ADMIN_API_KEY=admin-demo-key
   curl -H "X-Admin-Key: $ADMIN_API_KEY" http://127.0.0.1:5001/partner/jobs

6. Requeue a failed job (partner or admin):

   curl -X POST -H "X-API-Key: test-key" http://127.0.0.1:5001/partner/jobs/123/requeue

   # or as admin (requeue any job)
   curl -X POST -H "X-Admin-Key: $ADMIN_API_KEY" http://127.0.0.1:5001/partner/jobs/123/requeue

Notes
- This is a demo implementation intended for local development and testing.
- For production, replace the SQLite-backed queue with a proper durable queue (Redis/RabbitMQ/Cloud Tasks) and replace the simple metrics with Prometheus.
# CheckPoint1

## Project description

CheckPoint1 is a simple two-tier retail prototype built with Flask (web UI) and SQLite (persistence). Users can view products, add items to a cart, register/login, and checkout. Data is stored in a SQLite database and all checkout operations run atomically via a small DAO layer.

## Setup / Run / Test instructions

Prerequisites: Python 3.10+ (use a virtual environment)

1) Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Run the app
```bash
# Make sure the database is initialized and seeded (see next section)
python -m src.app
```
Open http://127.0.0.1:5000 in your browser.

3) Run tests
```bash
pytest -q
```

## Database setup instructions

The app uses a SQLite file (default path: <repo>/app.sqlite).

1) Initialize schema (idempotent)
```bash
python -m src.main
```

2) Seed demo data (users + products)
```bash
python -m src.seed
```

Options
- You can override the DB location by setting APP_DB_PATH, e.g.:
	```bash
	APP_DB_PATH=$(pwd)/app.sqlite python -m src.main
	APP_DB_PATH=$(pwd)/app.sqlite python -m src.seed
	```
- Seeded users for quick login:
	- john / password123
	- jane / password123
	- alice / password123

## Team members

- Pragya Chapagain
- Yanlin Wu
