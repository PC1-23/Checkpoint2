# Runbook — Checkpoint2 Demo & Run Instructions

This runbook explains how to run the Checkpoint2 app, manage the partner ingest worker, apply DB migrations, and run the async ingest demo via the web UI. It's written to be copy/paste friendly and minimal.

## Prerequisites
- Python 3.10+ (or 3.8+) with virtualenv
- Install project deps: `pip install -r requirements.txt`
- Optional: `jq` for pretty JSON in terminal

## Files of interest
- `src/app.py` — application factory and app entrypoint
- `src/partners/routes.py` — partner ingest, admin UI, jobs endpoints
- `src/partners/ingest_queue.py` — durable job queue and worker
- `db/init.sql` — schema used for new DBs
- `db/migrations/0001_add_diagnostics.sql` — migration to add `diagnostics` column

## 1) Start the app (dev)
From the repository root:

```bash
APP_DB_PATH=/absolute/path/to/app.sqlite \
  APP_SECRET_KEY=dev \
  ADMIN_API_KEY=admin-demo-key \
  python3 -m src.app
```

Notes:
- Use the `APP_DB_PATH` override if you want a different sqlite file. If omitted the repo root `app.sqlite` is used.
- The app will attempt to start an in-process worker when the partners blueprint is registered.

## 2) Apply migration (if needed)
If you're upgrading an existing DB that lacks the `diagnostics` column on `partner_ingest_jobs`, run:

```bash
# backup first
cp /absolute/path/to/app.sqlite /absolute/path/to/app.sqlite.bak
# apply migration
sqlite3 /absolute/path/to/app.sqlite < db/migrations/0001_add_diagnostics.sql
# verify
sqlite3 /absolute/path/to/app.sqlite "PRAGMA table_info(partner_ingest_jobs);"
```

## 3) Quick demo (web UI only)
1. Start the app (see step 1).
2. Open Admin UI: `http://127.0.0.1:5000/partner/admin`
   - Enter admin key `admin-demo-key` and click Login.
3. Onboard a partner (Admin UI): fill name/format/description, click Create Partner. Copy `api_key` from the response box.
4. Open Partner Upload UI: `http://127.0.0.1:5000/` (default)
  - Paste the partner `api_key`, choose Sync or Async (check the "Async" box to enqueue the feed for background processing; leave it unchecked to run the ingest synchronously in the request), and select a JSON or CSV feed (sample below). Click Upload to submit.
  - Async uploads (recommended for larger feeds): the server will enqueue the feed and return HTTP 202 Accepted along with a JSON response that may include a `job_id`. The background worker will process the job and you can monitor it from Admin → Jobs or via the job status API.
  - Sync uploads (use for small/fast samples or immediate feedback): the server will attempt validation and upsert during the request and return HTTP 200 with a summary on success, or HTTP 422 with validation errors.
5. Open Admin → Jobs: you will see the job in recent jobs and can click Requeue if needed.

Sample feed (save as `sample_feed.json`):
```json
[
  {"sku":"demo-sku-1","name":"Demo Product 1","price_cents":1999,"stock":10},
  {"sku":"demo-sku-2","name":"Demo Product 2","price_cents":2999,"stock":5}
]
```

## 4) Requeue a job (terminal)
If a job failed due to a prior schema issue or you want to re-run processing:

```bash
curl -i -X POST -H "X-Admin-Key: admin-demo-key" http://127.0.0.1:5000/partner/jobs/<JOB_ID>/requeue
```

Or requeue all failed jobs for a partner (partner API key required):

```bash
curl -s -X POST -H "X-API-Key: <PARTNER_API_KEY>" http://127.0.0.1:5000/partner/jobs/requeue_failed | jq
```

## 5) How to check job status and diagnostics
- Job status endpoint:

```bash
curl -s -H "X-API-Key: <PARTNER_API_KEY>" http://127.0.0.1:5000/partner/jobs/<JOB_ID> | jq
```

- Admin can view job JSON via Admin UI → Lookup job or:

```bash
curl -s -H "X-Admin-Key: admin-demo-key" http://127.0.0.1:5000/partner/jobs/<JOB_ID> | jq
```

- Offloaded diagnostics (if large) are available at:

```bash
curl -s -H "X-Admin-Key: admin-demo-key" http://127.0.0.1:5000/partner/diagnostics/<DIAG_ID> | jq
```

## 6) Troubleshooting
- "no such column: diagnostics" in the web UI
  - Run the migration from section 2 and restart the app.
- Job shows `status: failed` but products are present
  - Likely the worker upserted products but failed when writing diagnostics (schema mismatch). Apply the migration and requeue the job.
- Worker not processing jobs
  - Ensure the worker is running: the app starts it automatically when the partners blueprint registers. If you launched app in a context where background threads aren't permitted, start the worker manually:
    ```bash
    python3 - <<'PY'
    from src.partners.ingest_queue import start_worker
    from pathlib import Path
    import os
    root = Path(__file__).resolve().parents[1]
    db = os.environ.get('APP_DB_PATH', str(root / 'app.sqlite'))
    start_worker(db)
    print('worker started')
    PY
    ```

## 7) Recommended maintenance
- Add the migration to your deployment process so all DBs have `diagnostics` column.
- Periodically inspect `partner_ingest_diagnostics` for large failure artifacts.
- Consider backing up DB before schema changes.

## 8) Developer notes
- For demos we accept async uploads (default) via `/partner/ingest` — the UI has an Async checkbox.
- The worker is resilient: if diagnostics column is missing, it now offloads diagnostics to `partner_ingest_diagnostics` and updates job status so the job isn't marked failed solely for missing diagnostics.

---

## 9) Testing (run the test suite)
Follow these steps to run unit and integration tests locally. Tests are pytest-based and expect the `src` package to be importable.

1) Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Ensure `src` is importable by pytest

- The repo root should be the current directory when running tests. If pytest reports import errors for `src`, set PYTHONPATH explicitly:

```bash
export PYTHONPATH=$(pwd)
```

3) Run all tests (fast)

```bash
pytest -q
```

4) Use the demo test runner (runs files one-by-one with context)

```bash
bash tools/demo_run_tests.sh
```

5) Run a single test file or test function (example)

```bash
pytest tests/test_product_repo.py -q
# or a single test function
pytest tests/test_scheduler_crud.py::test_schedule_crud -q
```

6) Environment variables for tests and demo

- `APP_DB_PATH` — path to the sqlite DB that tests/apps should use (default: repo root `app.sqlite`).
- `ADMIN_API_KEY` — set to `admin-demo-key` (or similar) when tests expect programmatic admin access.

Example: run a targeted test with env vars

```bash
APP_DB_PATH=/absolute/path/app.sqlite ADMIN_API_KEY=admin-demo-key pytest tests/test_scheduler_crud.py::test_schedule_crud -q
```

7) Deterministic job processing in tests

- The project exposes `process_next_job_once(db_path)` in `src.partners.ingest_queue` which can be used to synchronously claim and process a single pending job. This is handy for demos or deterministic test runs where you don't want to rely on background threads.

Example synchronous processing (run after enqueueing a job):

```bash
python3 - <<'PY'
from src.partners.ingest_queue import process_next_job_once
import os
db = os.environ.get('APP_DB_PATH', 'app.sqlite')
print(process_next_job_once(db))
PY
```

8) Worker in background (for manual integration testing)

```bash
python3 - <<'PY'
from src.partners.ingest_queue import start_worker
import os
from pathlib import Path
root = Path.cwd()
db = os.environ.get('APP_DB_PATH', str(root / 'app.sqlite'))
start_worker(db)
print('worker started for', db)
import time
time.sleep(1)
PY
```

9) Common test troubleshooting

- If tests fail with DB schema errors, ensure you applied migrations (see section 2).
- If tests expect admin access, set `ADMIN_API_KEY` in the environment.
- Use `-k` to filter tests by keyword and `-x` to stop on first failure while debugging.

Example: run tests stopping on failure and show output

```bash
pytest -k scheduler -x -q
```
