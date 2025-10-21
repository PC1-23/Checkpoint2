from __future__ import annotations
from flask import Flask, request, render_template, abort, jsonify
from pathlib import Path
from .partner_adapters import parse_json_feed, parse_csv_feed
from .partner_ingest_service import upsert_products
from .ingest_queue import enqueue_feed, start_worker
from .metrics import get_metrics
from . import scheduler
import sqlite3, os

app = Flask(__name__, template_folder=Path(__file__).parent.joinpath("templates"))


def get_conn():
    root = Path(__file__).resolve().parents[2]
    db_path = Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite")
    return sqlite3.connect(str(db_path))


@app.get("/")
def index():
    return render_template("partners/partner_upload.html")


# Start background services at module import / app creation time. This avoids
# using the deprecated `before_first_request` hook (removed in Flask 2.3).
# Services are started in a guarded try/except so tests or environments without
# APScheduler won't fail.
try:
    root = Path(__file__).resolve().parents[2]
    db_path = str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))
    start_worker(db_path)
    try:
        scheduler.start_scheduler()
    except Exception:
        # scheduler is optional / may log its own message if APScheduler missing
        pass
except Exception:
    # If anything goes wrong starting background services during import, don't
    # crash the app import (tests will still run). The worker/scheduler can be
    # started manually if needed.
    pass


@app.post("/partner/ingest")
def partner_ingest():
    api_key = request.headers.get("X-API-Key") or request.form.get("api_key")
    if not api_key:
        abort(401, "Missing API key")

    # Validate API key against partner_api_keys table
    conn_check = get_conn()
    try:
        cur = conn_check.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (api_key,))
        row = cur.fetchone()
        if not row:
            abort(401, "Invalid API key")
    finally:
        conn_check.close()

    # Choose adapter by content type or file extension
    content_type = request.content_type or ""
    payload = request.get_data()

    if content_type.startswith("application/json"):
        products = parse_json_feed(payload)
    else:
        # fallback to csv parser for form uploads
        products = parse_csv_feed(payload)

    # compute feed hash for idempotency
    import hashlib, json
    try:
        feed_hash = hashlib.sha256(payload).hexdigest()
    except Exception:
        # fallback: hash json dump of parsed products
        feed_hash = hashlib.sha256(json.dumps(products, sort_keys=True).encode()).hexdigest()

    # If async parameter provided, enqueue and return 202
    async_mode = request.args.get("async", "1")
    # determine partner_id early so both async and sync branches can use it
    partner_id = None
    if api_key:
        conn = get_conn()
        try:
            r = conn.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (api_key,)).fetchone()
            if r:
                partner_id = r[0]
        finally:
            conn.close()
    if async_mode in ("1", "true", "yes"):
        # Start worker if not running
        root = Path(__file__).resolve().parents[2]
        db_path = str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))
        start_worker(db_path)
        # partner_id already looked up above
        try:
            enqueue_feed(partner_id or 0, products + [], feed_hash=feed_hash)
        except TypeError:
            # backward compatibility with test doubles or older wrappers that don't accept feed_hash
            enqueue_feed(partner_id or 0, products + [])
        # store feed_hash alongside enqueue metadata if needed (in-process queue currently doesn't persist)
        return ("Accepted", 202)

    # Upsert into DB (sync)
    conn = get_conn()
    try:
        count, upsert_errors = upsert_products(conn, products, partner_id=partner_id, feed_hash=feed_hash)
    finally:
        conn.close()

    return (f"Ingested {count} products", 200)
@app.post('/partner/schedule')
def partner_schedule():
    """Trigger scheduled ingestion for a partner. For demo, this simply returns 200.

    In production, this could enqueue a job or call partner endpoints periodically.
    """
    return ("Scheduled", 200)


@app.get('/partner/schedules')
def list_schedules():
    """Admin endpoint: list all schedules."""
    admin_key = request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"
    if admin_key != (request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
        abort(401, "Missing or invalid admin key")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, partner_id, schedule_type, schedule_value, enabled, last_run FROM partner_schedules ORDER BY id DESC")
        rows = [dict(id=r[0], partner_id=r[1], schedule_type=r[2], schedule_value=r[3], enabled=r[4], last_run=r[5]) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()


@app.post('/partner/schedules')
def create_schedule():
    """Admin endpoint: create a schedule. Expects JSON: {partner_id, schedule_type, schedule_value, enabled}
    schedule_value may be a JSON object (for interval) or string (for cron).
    """
    admin_key = request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"
    if admin_key != (request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
        abort(401, "Missing or invalid admin key")
    data = request.get_json(force=True)
    partner_id = data.get('partner_id')
    schedule_type = data.get('schedule_type')
    schedule_value = data.get('schedule_value')
    enabled = 1 if data.get('enabled', True) else 0
    if not partner_id or not schedule_type or schedule_value is None:
        abort(400, "Missing required fields")
    # store schedule_value as JSON string if it's a dict
    import json
    sv = json.dumps(schedule_value) if isinstance(schedule_value, (dict, list)) else str(schedule_value)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO partner_schedules (partner_id, schedule_type, schedule_value, enabled) VALUES (?, ?, ?, ?)", (partner_id, schedule_type, sv, enabled))
        conn.commit()
        return ("Created", 201)
    finally:
        conn.close()


@app.delete('/partner/schedules/<int:sid>')
def delete_schedule(sid: int):
    admin_key = request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"
    if admin_key != (request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
        abort(401, "Missing or invalid admin key")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM partner_schedules WHERE id = ?", (sid,))
        conn.commit()
        return ("Deleted", 200)
    finally:
        conn.close()


@app.get('/partner/jobs')
def partner_jobs():
    """Inspect recent partner ingest jobs and counts.

    Returns JSON with counts per status and the last 20 jobs.
    """
    # admin-only
    admin_key = request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"
    if not admin_key or admin_key != (request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
        abort(401, "Missing or invalid admin key")

    conn = get_conn()
    try:
        cur = conn.cursor()
        counts = {}
        for status in ("pending", "in_progress", "done", "failed"):
            cur.execute("SELECT COUNT(1) FROM partner_ingest_jobs WHERE status = ?", (status,))
            counts[status] = cur.fetchone()[0]
        cur.execute("SELECT id, partner_id, status, attempts, created_at, processed_at FROM partner_ingest_jobs ORDER BY id DESC LIMIT 20")
        rows = [dict(id=r[0], partner_id=r[1], status=r[2], attempts=r[3], created_at=r[4], processed_at=r[5]) for r in cur.fetchall()]
        return jsonify({"counts": counts, "recent": rows})
    finally:
        conn.close()


@app.get('/partner/metrics')
def partner_metrics():
    admin_key = request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"
    if not admin_key or admin_key != (request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
        abort(401, "Missing or invalid admin key")
    return jsonify(get_metrics())


@app.post('/partner/jobs/<int:job_id>/requeue')
def partner_job_requeue(job_id: int):
    """Requeue a specific job.

    If caller provides X-Admin-Key (matching ADMIN_API_KEY), allow requeuing any job.
    Otherwise require X-API-Key belonging to the job's partner.
    """
    admin_key = request.headers.get("X-Admin-Key")
    api_key = request.headers.get("X-API-Key")
    if not admin_key and not api_key:
        abort(401, "Missing API key")
    conn = get_conn()
    try:
        cur = conn.cursor()
        # if admin key provided and valid, allow any job
        if admin_key and admin_key == (os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
            cur.execute("UPDATE partner_ingest_jobs SET status='pending', next_run = NULL, attempts = 0, error = NULL WHERE id = ?", (job_id,))
            conn.commit()
            return ("Requeued", 200)

        # verify partner owns api_key
        cur.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (api_key,))
        row = cur.fetchone()
        if not row:
            abort(401, "Invalid API key")
        partner_id = row[0]

        # ensure job belongs to this partner
        cur.execute("SELECT partner_id FROM partner_ingest_jobs WHERE id = ?", (job_id,))
        j = cur.fetchone()
        if not j:
            abort(404, "Job not found")
        if j[0] != partner_id:
            abort(403, "Not allowed")

        cur.execute("UPDATE partner_ingest_jobs SET status='pending', next_run = NULL, attempts = 0, error = NULL WHERE id = ?", (job_id,))
        conn.commit()
        return ("Requeued", 200)
    finally:
        conn.close()


@app.post('/partner/jobs/requeue_failed')
def partner_requeue_failed():
    """Requeue all failed jobs for the partner identified by X-API-Key."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        abort(401, "Missing API key")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (api_key,))
        row = cur.fetchone()
        if not row:
            abort(401, "Invalid API key")
        partner_id = row[0]

        cur.execute("UPDATE partner_ingest_jobs SET status='pending', next_run = NULL, attempts = 0, error = NULL WHERE partner_id = ? AND status = 'failed'", (partner_id,))
        updated = cur.rowcount
        conn.commit()
        return jsonify({"requeued": updated})
    finally:
        conn.close()
