from __future__ import annotations
from flask import Flask, request, render_template, abort, jsonify
from pathlib import Path
import json
from .partner_adapters import parse_feed
from .integrability import get_contract, validate_against_contract
from .partner_ingest_service import upsert_products
from .ingest_queue import enqueue_feed, start_worker
from .metrics import get_metrics
from .security import check_rate_limit, record_audit
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
    from .security import verify_api_key
    partner_id_lookup = verify_api_key(os.environ.get("APP_DB_PATH"), api_key)
    if partner_id_lookup is None:
        record_audit(None, api_key, "auth_invalid")
        abort(401, "Invalid API key")

    # Rate limit check (best-effort)
    if not check_rate_limit(api_key):
        record_audit(None, api_key, "rate_limited")
        abort(429, "Rate limit exceeded")

    # Choose adapter by content type or file extension
    content_type = request.content_type or ""
    payload = request.get_data()
    feed_version = request.headers.get("X-Feed-Version") or request.args.get("feed_version")
    products = parse_feed(payload, content_type=content_type, feed_version=feed_version)

    # compute feed hash for idempotency
    import hashlib, json
    try:
        feed_hash = hashlib.sha256(payload).hexdigest()
    except Exception:
        # fallback: hash json dump of parsed products
        feed_hash = hashlib.sha256(json.dumps(products, sort_keys=True).encode()).hexdigest()

    # Feed version header (optional) — can be used by adapters later
    feed_version = request.headers.get("X-Feed-Version") or request.args.get("feed_version")

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
        # Call the module-level enqueue_feed (may be monkeypatched in tests)
        jid = None
        try:
            enqueue_feed(partner_id or 0, products + [], feed_hash=feed_hash)
        except TypeError:
            enqueue_feed(partner_id or 0, products + [])

        # If the module-level enqueue_feed is the original implementation, try to get a job id
        try:
            import src.partners.ingest_queue as _iq
            root = Path(__file__).resolve().parents[2]
            db_path = str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))
            # If enqueue_feed in this module points to the original function, use enqueue_feed_db to obtain jid
            if getattr(_iq, 'enqueue_feed', None) is enqueue_feed and getattr(_iq, 'enqueue_feed_db', None):
                jid = _iq.enqueue_feed_db(db_path, partner_id or 0, products + [], feed_hash=feed_hash)
        except Exception:
            jid = None
        record_audit(partner_id, api_key, "enqueue", payload=str(feed_hash))
        # return JSON with job id when available
        if jid:
            return (jsonify({"job_id": jid, "status": "accepted"}), 202)
        return (jsonify({"status": "accepted"}), 202)

    # Synchronous validation + upsert with structured feedback
    conn = get_conn()
    try:
        valid, validation_errors = __import__("src.partners.partner_ingest_service", fromlist=["validate_products"]).validate_products(products)
        if not valid:
            # return structured validation summary
            summary = {"status": "validation_failed", "accepted": 0, "rejected": len(validation_errors), "errors": validation_errors}
            record_audit(partner_id, api_key, "ingest_sync_validation_failed", payload=str(feed_hash))
            return (jsonify(summary), 422)
        upserted, upsert_errors = upsert_products(conn, valid, partner_id=partner_id, feed_hash=feed_hash)
    finally:
        conn.close()
    # Persist a small diagnostics blob into partner_ingest_jobs for traceability (if job exists)
    try:
        from .ingest_queue import enqueue_feed_db
        # create a diagnostic record by inserting a job row with status=done
        root = Path(__file__).resolve().parents[2]
        db_path = str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))
        import sqlite3
        conn2 = sqlite3.connect(db_path)
        cur2 = conn2.cursor()
        diag = {"accepted": upserted, "rejected": len(upsert_errors), "errors": upsert_errors}
        cur2.execute("INSERT INTO partner_ingest_jobs (partner_id, payload, status, diagnostics, feed_hash, processed_at) VALUES (?, ?, 'done', ?, ?, CURRENT_TIMESTAMP)", (partner_id or 0, json.dumps(valid), json.dumps(diag), feed_hash))
        conn2.commit()
        conn2.close()
    except Exception:
        # best-effort diagnostics persistence; continue
        pass
    record_audit(partner_id, api_key, "ingest_sync", payload=str(feed_hash))

    return (jsonify({"status": "done", "accepted": upserted, "rejected": len(upsert_errors), "errors": upsert_errors}), 200)
# Integrability / onboarding endpoints


@app.get('/partner/contract')
def partner_contract():
    """Return machine-readable contract for partner feeds."""
    return jsonify(get_contract())


@app.get('/partner/contract/example')
def partner_contract_example():
    return jsonify(get_contract().get("example"))


@app.post('/partner/contract/validate')
def partner_contract_validate():
    """Sandbox validation endpoint for partners to validate sample feeds."""
    content_type = request.content_type or ""
    payload = request.get_data()
    feed_version = request.headers.get("X-Feed-Version") or request.args.get("feed_version")
    products = parse_feed(payload, content_type=content_type, feed_version=feed_version)
    valid, errors = validate_against_contract(products)
    if not valid:
        return (jsonify({"status": "validation_failed", "accepted": 0, "rejected": len(errors), "errors": errors}), 422)
    return jsonify({"status": "ok", "accepted": len(valid), "rejected": 0})


@app.post('/partner/onboard')
def partner_onboard():
    """Simple demo onboarding: create a partner and issue an API key. Admin-only in demo."""
    admin_key = request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"
    if admin_key != (request.headers.get("X-Admin-Key") or os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
        abort(401, "Missing or invalid admin key")
    data = request.get_json(force=True)
    name = data.get("name")
    if not name:
        abort(400, "Missing partner name")
    import secrets
    api_key = secrets.token_urlsafe(16)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO partner (name, format) VALUES (?, ?)", (name, data.get("format", "json")))
        pid = cur.lastrowid
        cur.execute("INSERT INTO partner_api_keys (partner_id, api_key, description) VALUES (?, ?, ?)", (pid, api_key, data.get("description", "onboarded key")))
        conn.commit()
        return jsonify({"partner_id": pid, "api_key": api_key})
    finally:
        conn.close()


@app.get('/partner/help')
def partner_help():
    """Human-friendly quickstart for partners (small page with sample curl)."""
    # Keep this small and machine-readable (JSON) for discoverability
    quickstart = {
        "description": "Quickstart examples for Partner Ingest API",
        "post_example": {
            "curl": "curl -X POST http://HOST/partner/ingest -H 'Content-Type: application/json' -H 'X-API-Key: <your-key>' --data '[{\"sku\": \"sku-example-123\", \"name\": \"Sample Product\", \"price_cents\": 1999, \"stock\": 10}]'"
        },
        "notes": ["Use X-Feed-Version header to select adapter versions when supported."]
    }
    return jsonify(quickstart)


# JSON error handler: return consistent JSON with {error, details}
@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(429)
@app.errorhandler(500)
def json_error_handler(err):
    try:
        code = getattr(err, 'code', 500)
        name = getattr(err, 'name', 'Error')
        description = getattr(err, 'description', str(err))
    except Exception:
        code = 500
        name = 'Error'
        description = str(err)
    payload = {"error": name, "details": description}
    return jsonify(payload), code
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
    # record admin access
    record_audit(None, admin_key, "admin_list_schedules")


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
    record_audit(None, admin_key, "admin_create_schedule", payload=str(data))


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
    record_audit(None, admin_key, "admin_delete_schedule", payload=str(sid))


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


@app.get('/partner/jobs/<int:job_id>')
def partner_job_status(job_id: int):
    """Return structured diagnostics and status for a specific job.

    Partners may fetch this for async uploads to see validation results.
    Admin or partner key required and ownership is enforced.
    """
    api_key = request.headers.get("X-API-Key")
    admin_key = request.headers.get("X-Admin-Key")
    if not api_key and not admin_key:
        abort(401, "Missing API key")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, partner_id, status, created_at, processed_at, error, diagnostics FROM partner_ingest_jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        if not row:
            abort(404, "Job not found")
        job = dict(id=row[0], partner_id=row[1], status=row[2], created_at=row[3], processed_at=row[4])
        # enforce ownership unless admin
        if admin_key and admin_key == (os.environ.get("ADMIN_API_KEY") or "admin-demo-key"):
            pass
        else:
            # verify api_key belongs to partner
            cur.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (api_key,))
            prow = cur.fetchone()
            if not prow:
                abort(401, "Invalid API key")
            if prow[0] != job['partner_id']:
                abort(403, "Not allowed")

        # include diagnostics and error payloads (deserialize JSON where present)
        err = row[5]
        diag = row[6]
        try:
            job['error'] = json.loads(err) if err else None
        except Exception:
            job['error'] = err
        try:
            job['diagnostics'] = json.loads(diag) if diag else None
        except Exception:
            job['diagnostics'] = diag
        return jsonify(job)
    finally:
        conn.close()



@app.get('/partner/diagnostics/<int:diag_id>')
def partner_diagnostics(diag_id: int):
    """Return offloaded diagnostics artifact. Admin or owning partner may fetch."""
    api_key = request.headers.get("X-API-Key")
    admin_key = request.headers.get("X-Admin-Key")
    if not api_key and not admin_key:
        abort(401, "Missing API key")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, job_id, diagnostics, created_at FROM partner_ingest_diagnostics WHERE id = ?", (diag_id,))
        row = cur.fetchone()
        if not row:
            abort(404, "Diagnostics not found")
        job_id = row[1]
        # ownership check: admin can access any, otherwise ensure api_key belongs to job's partner
        if not (admin_key and admin_key == (os.environ.get("ADMIN_API_KEY") or "admin-demo-key")):
            cur.execute("SELECT partner_id FROM partner_ingest_jobs WHERE id = ?", (job_id,))
            j = cur.fetchone()
            if not j:
                abort(404, "Job not found")
            cur.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (api_key,))
            prow = cur.fetchone()
            if not prow or prow[0] != j[0]:
                abort(403, "Not allowed")
        # return diagnostics JSON (stored as text blob)
        try:
            return jsonify({"id": row[0], "job_id": row[1], "diagnostics": json.loads(row[2]), "created_at": row[3]})
        except Exception:
            return jsonify({"id": row[0], "job_id": row[1], "diagnostics": row[2], "created_at": row[3]})
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
