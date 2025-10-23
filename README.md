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
#
# Schema notes

This repository contains two schema files under `db/`:

- `db/init.sql` - canonical, full application schema used by the app. It contains the
   product catalog tables, partner integration tables, durable job table
   (`partner_ingest_jobs`), idempotency table (`partner_feed_imports`), and
   scheduling table (`partner_schedules`). Use this file to initialize or
   migrate the application database.

- `db/partners.sql` - a lightweight, compatibility-focused subset that documents
   the basic `partner` and `partner_api_keys` tables. This file is intentionally
   minimal and may lag behind `db/init.sql`. Prefer `db/init.sql` for any
   authoritative operations (initialization, migrations, seeding).

To initialize the database with the full schema (recommended):

```bash
sqlite3 app.sqlite < db/init.sql
# or run the app initialization helper
python -m src.main
```

# CheckPoint2

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
```markdown
# Partner (VAR) Catalog Ingest — Demo & Developer Guide

This repository is a demo implementation of a partner catalog ingest flow
designed for local development, demos, and experimentation. It includes
validation, a small admin UI, a background worker, and observability hooks.

What’s new / important to know
- Admin UI uses a session-based model: POST /partner/admin/login sets a session cookie.
   Admin actions in the browser require that session (UI buttons are disabled until
   the session is confirmed). Programmatic automation should use a separate token
   flow or the `ADMIN_API_KEY` environment variable if needed for scripts.
- Observability: the app exposes Prometheus-style metrics (protected) and uses
   structured JSON logging for easier ingestion.
- Optional API-key hashing: set `HASH_KEYS=true` to store hashed partner keys.

Repository layout (important files)
- `src/` — application code (Flask app, partners, observability)
- `src/partners/routes.py` — partner endpoints, admin UI, onboarding
- `src/observability.py` — Prometheus metrics helpers and JSON logging
- `db/init.sql` — full DB schema
- `tests/` — unit and integration tests (use pytest)

Quick start (dev)

1) Setup a virtualenv and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Initialize the database (idempotent)

```bash
# create schema
python -m src.main

# optional: seed demo data (users + products)
python -m src.seed
#seed for flash sale products
python -m db.seed_flash_sales
```

3) Start the Flask app (single-process dev)

```bash
# default: 127.0.0.1:5000
python -m src.app

# or with overridden env vars
APP_DB_PATH=$(pwd)/app.sqlite ADMIN_API_KEY=admin-demo-key APP_SECRET_KEY=dev-insecure-secret python -m src.app
```

4) Start the background worker in a second terminal

```bash
APP_DB_PATH=$(pwd)/app.sqlite python -c "import sys, pathlib; sys.path.insert(0, str(pathlib.Path('.').resolve())); from src.partners.ingest_queue import start_worker; from pathlib import Path; start_worker(str(Path('.').resolve()/ 'app.sqlite'))"
```

Important environment variables
- `APP_DB_PATH` — path to SQLite DB file (default: `app.sqlite` in repo)
- `ADMIN_API_KEY` — demo admin key (default: `admin-demo-key`)
- `APP_SECRET_KEY` — Flask session secret (set to a strong value in non-dev)
- `HASH_KEYS` — set to `true` to hash API keys before storing (default: `false`)

Key endpoints and UX notes
- `GET /partner/contract` — machine-readable contract (JSON)
- `GET /partner/contract/example` — example payload a partner can copy (JSON)
- `GET /partner/help` — quickstart and copyable curl examples (JSON)
- `POST /partner/ingest` — ingest endpoint (requires `X-API-Key` for partner auth)
- `GET /partner/admin` — admin UI; buttons disabled until session is confirmed
- `POST /partner/admin/login` — login (JSON or form); sets admin session cookie
- `POST /partner/onboard_form` — admin UI helper to onboard partner and return API key
- `GET /partner/jobs` — admin-only JSON jobs listing
- `GET /partner/metrics` — admin-only metrics dashboard (reads Prometheus registry)
- `GET /partner/audit` — admin-only audit viewer

Error responses
- API errors are normalized to JSON: `{ "error": "<Name>", "details": "<message>" }`.
   This makes it simple for partner automation to parse and react to failures.

Demo commands (copy/paste)

1) Contract & example (pretty-print with `jq`)

```bash
curl -sS http://127.0.0.1:5000/partner/contract | jq .
curl -sS http://127.0.0.1:5000/partner/contract/example | jq .
```

2) Quickstart/help

```bash
curl -sS http://127.0.0.1:5000/partner/help | jq .
```

3) Show JSON error for missing API key

```bash
curl -i -sS -X POST http://127.0.0.1:5000/partner/ingest -H 'Content-Type: application/json' -d '[]'
```

4) Admin login + onboard (session-based)

```bash
# login and save cookie
curl -i -c cookies.txt -H "Content-Type: application/json" \
   -d '{"admin_key":"admin-demo-key"}' -X POST http://127.0.0.1:5000/partner/admin/login

# create partner using session cookie (returns the API key)
curl -i -b cookies.txt -H "Content-Type: application/json" \
   -d '{"name":"DemoPartner","description":"Demo","format":"json"}' \
   -X POST http://127.0.0.1:5000/partner/onboard_form
```

Running tests

```bash
pytest -q
```

Notes and security guidance
- The demo `ADMIN_API_KEY` is `admin-demo-key` unless you override it. Do not commit real secrets.
- In production:
   - Use a secure `APP_SECRET_KEY` and rotate admin keys.
   - Replace SQLite + in-process worker with a durable queue (Redis, RabbitMQ, Cloud Tasks).
   - Harden cookies (SameSite, Secure) and add CSRF protections for forms.

Further reading
- ADR: `docs/ADR/0013-usability.md` — describes contract, example, quickstart and normalized errors.

Maintainers
- Pragya Chapagain
- Yanlin Wu

```
