"""DB-backed ingest job queue and worker with retry/backoff.

This implements a simple durable job table `partner_ingest_jobs` and a worker
that claims pending jobs (UPDATE ... WHERE status='pending') and processes them.
Jobs are persisted in `partner_ingest_jobs`. The worker claims jobs whose
status is 'pending' and whose `next_run` is NULL or in the past. On failure
the worker will schedule a retry using exponential backoff up to `max_attempts`.
"""
from __future__ import annotations
import json
import threading
import time
import logging
import random
from typing import Any, Dict, Optional, Tuple
import sqlite3
from .partner_ingest_service import upsert_products, validate_products
from .metrics import incr
from .security import record_audit

logger = logging.getLogger(__name__)


def enqueue_feed_db(db_path: str, partner_id: int, products: list[Dict[str, Any]], feed_hash: str | None = None) -> int:
    """Persist a job into the partner_ingest_jobs table and return job id.

    SQLite can raise sqlite3.OperationalError: "database is locked" when many
    connections attempt writes concurrently. To make the ingest endpoint more
    resilient to quick repeated clicks from the UI, use a connect timeout and
    retry loop with small backoff before giving up.
    """
    # configure a sensible timeout for sqlite connections (in seconds)
    timeout = 5.0
    max_attempts = 5
    backoff_base = 0.05
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            conn = sqlite3.connect(db_path, timeout=timeout)
            cur = conn.cursor()
            cur.execute("INSERT INTO partner_ingest_jobs (partner_id, payload, status, feed_hash) VALUES (?, ?, 'pending', ?)", (partner_id, json.dumps(products), feed_hash))
            jid = cur.lastrowid
            conn.commit()
            conn.close()
            incr("enqueued")
            return jid
        except sqlite3.OperationalError as e:
            last_exc = e
            # If it's a database locked error, wait a bit and retry; otherwise re-raise
            msg = str(e).lower()
            if "database is locked" in msg:
                sleep_time = backoff_base * (2 ** (attempt - 1))
                # add a small jitter
                sleep_time = sleep_time * (1 + (random.random() - 0.5) * 0.3)
                time.sleep(sleep_time)
                continue
            raise
    # If we exhausted retries, raise the last error to be handled by caller (Flask will map to 500)
    if last_exc:
        raise last_exc
    raise RuntimeError("enqueue_feed_db failed for unknown reasons")


def enqueue_feed(partner_id: int, products: list[Dict[str, Any]], feed_hash: str | None = None) -> None:
    """Compatibility wrapper: find APP_DB_PATH from environment and persist job."""
    import os
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    db_path = str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))
    enqueue_feed_db(db_path, partner_id, products, feed_hash=feed_hash)


_stop_event: Optional[threading.Event] = None


def _claim_job(conn: sqlite3.Connection) -> Optional[Tuple[int, int, list, int, int]]:
    """Claim one available pending job that is ready to run.

    Returns (job_id, partner_id, products, attempts, max_attempts) or None.
    """
    cur = conn.cursor()
    # Claim a single pending job: mark in_progress and return its id and payload
    cur.execute("BEGIN IMMEDIATE")
    row = cur.execute(
        "SELECT id, partner_id, payload, attempts, max_attempts FROM partner_ingest_jobs "
        "WHERE status = 'pending' AND (next_run IS NULL OR next_run <= CURRENT_TIMESTAMP) ORDER BY id LIMIT 1"
    ).fetchone()
    if not row:
        conn.rollback()
        return None
    jid, partner_id, payload, attempts, max_attempts = row
    cur.execute("UPDATE partner_ingest_jobs SET status='in_progress', attempts = attempts + 1 WHERE id = ?", (jid,))
    conn.commit()
    return jid, partner_id, json.loads(payload), attempts or 0, max_attempts or 5


def worker_loop(db_path: str, poll_interval: float = 0.1):
    while True:
        if _stop_event and _stop_event.is_set():
            break
        try:
            conn = sqlite3.connect(db_path)
            claimed = _claim_job(conn)
            if not claimed:
                conn.close()
                time.sleep(poll_interval)
                continue

            jid, partner_id, products, attempts, max_attempts = claimed
            try:
                # If scheduler enqueued an empty payload, treat it as a valid no-op run.
                if not products:
                    logger.info("Scheduler-triggered empty payload for job=%s partner=%s; marking done.", jid, partner_id)
                    cur = conn.cursor()
                    cur.execute("UPDATE partner_ingest_jobs SET status='done', processed_at = CURRENT_TIMESTAMP WHERE id = ?", (jid,))
                    conn.commit()
                    incr("processed")
                    record_audit(partner_id, None, "worker_processed_empty", payload=str(jid))
                else:
                    # validate_products returns (valid_items, errors)
                    valid_items, validation_errors = validate_products(products)
                    cur = conn.cursor()
                    if validation_errors:
                        # If there are any validation errors, fail the job and persist diagnostics
                        logger.warning("Ingest validation failed for job=%s partner=%s errors=%s", jid, partner_id, validation_errors)
                        diag = {"accepted": 0, "rejected": len(validation_errors), "errors": validation_errors}
                        djson = json.dumps(diag)
                        if len(djson) > 2000:
                            odcur = conn.cursor()
                            odcur.execute("INSERT INTO partner_ingest_diagnostics (job_id, diagnostics) VALUES (?, ?)", (jid, djson))
                            off_id = odcur.lastrowid
                            cur.execute("UPDATE partner_ingest_jobs SET status='failed', error = ?, diagnostics = ? WHERE id = ?", (json.dumps(validation_errors), json.dumps({"errors_link": f"/partner/diagnostics/{off_id}"}), jid))
                        else:
                            cur.execute("UPDATE partner_ingest_jobs SET status='failed', error = ?, diagnostics = ? WHERE id = ?", (json.dumps(validation_errors), djson, jid))
                        conn.commit()
                        record_audit(partner_id, None, "worker_validation_failed", payload=json.dumps(validation_errors))
                    else:
                        upserted, upsert_errors = upsert_products(conn, valid_items, partner_id=partner_id)
                        logger.info("Ingest processed job=%s partner=%s upserted=%s errors=%s", jid, partner_id, upserted, upsert_errors)
                        diag = {"accepted": upserted, "rejected": len(upsert_errors), "errors": upsert_errors}
                        djson = json.dumps(diag)
                        # Offload large diagnostics to separate table to avoid bloating job rows
                        if len(djson) > 2000:
                            odcur = conn.cursor()
                            odcur.execute("INSERT INTO partner_ingest_diagnostics (job_id, diagnostics) VALUES (?, ?)", (jid, djson))
                            off_id = odcur.lastrowid
                            cur.execute("UPDATE partner_ingest_jobs SET status='done', processed_at = CURRENT_TIMESTAMP, diagnostics = ? WHERE id = ?", (json.dumps({"errors_link": f"/partner/diagnostics/{off_id}"}), jid))
                        else:
                            cur.execute("UPDATE partner_ingest_jobs SET status='done', processed_at = CURRENT_TIMESTAMP, diagnostics = ? WHERE id = ?", (djson, jid))
                        conn.commit()
                        incr("processed")
                        record_audit(partner_id, None, "worker_processed", payload=str(jid))
            except Exception as e:
                logger.exception("Ingest worker error for job %s: %s", jid, e)
                cur = conn.cursor()
                # attempts was incremented when claiming; schedule retry if below max_attempts
                cur.execute("SELECT attempts, max_attempts FROM partner_ingest_jobs WHERE id = ?", (jid,))
                row = cur.fetchone()
                cur_attempts = row[0] if row else attempts
                cur_max = row[1] if row else max_attempts
                if cur_attempts < (cur_max or 5):
                    # exponential backoff with jitter: base = 2 ** attempts, apply multiplier in [0.5, 1.5]
                    base = max(1, 2 ** (cur_attempts))
                    jittered = int(max(1, base * random.uniform(0.5, 1.5)))
                    delay = jittered
                    cur.execute(
                        "UPDATE partner_ingest_jobs SET status='pending', next_run = datetime(CURRENT_TIMESTAMP, '+' || ? || ' seconds'), error = ? WHERE id = ?",
                        (str(delay), str(e), jid),
                    )
                    incr("retried")
                else:
                    cur.execute("UPDATE partner_ingest_jobs SET status='failed', error = ? WHERE id = ?", (str(e), jid))
                incr("failed")
                record_audit(partner_id, None, "worker_exception", payload=str(e))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.exception("Worker outer exception")
            time.sleep(poll_interval)


def start_worker(db_path: str) -> threading.Event:
    global _stop_event
    if _stop_event and not _stop_event.is_set():
        return _stop_event
    _stop_event = threading.Event()
    t = threading.Thread(target=worker_loop, args=(db_path,), daemon=True)
    t.start()
    return _stop_event


def stop_worker():
    global _stop_event
    if _stop_event:
        _stop_event.set()


def process_next_job_once(db_path: str) -> Optional[Dict[str, Any]]:
    """Claim and process a single pending job synchronously.

    Returns a dict with job_id and final status, or None if no pending job
    was available.
    """
    conn = sqlite3.connect(db_path)
    try:
        claimed = _claim_job(conn)
        if not claimed:
            return None
        jid, partner_id, products, attempts, max_attempts = claimed
        try:
            if not products:
                cur = conn.cursor()
                cur.execute("UPDATE partner_ingest_jobs SET status='done', processed_at = CURRENT_TIMESTAMP WHERE id = ?", (jid,))
                conn.commit()
                record_audit(partner_id, None, "worker_processed_empty", payload=str(jid))
                return {"job_id": jid, "status": "done"}

            valid_items, validation_errors = validate_products(products)
            if validation_errors:
                cur = conn.cursor()
                diag = {"accepted": 0, "rejected": len(validation_errors), "errors": validation_errors}
                djson = json.dumps(diag)
                if len(djson) > 2000:
                    odcur = conn.cursor()
                    odcur.execute("INSERT INTO partner_ingest_diagnostics (job_id, diagnostics) VALUES (?, ?)", (jid, djson))
                    off_id = odcur.lastrowid
                    cur.execute("UPDATE partner_ingest_jobs SET status='failed', error = ?, diagnostics = ? WHERE id = ?", (json.dumps(validation_errors), json.dumps({"errors_link": f"/partner/diagnostics/{off_id}"}), jid))
                    conn.commit()
                    record_audit(partner_id, None, "worker_validation_failed", payload=json.dumps(validation_errors))
                    return {"job_id": jid, "status": "failed", "diagnostics": {"errors_link": f"/partner/diagnostics/{off_id}"}}
                else:
                    cur.execute("UPDATE partner_ingest_jobs SET status='failed', error = ?, diagnostics = ? WHERE id = ?", (json.dumps(validation_errors), djson, jid))
                    conn.commit()
                    record_audit(partner_id, None, "worker_validation_failed", payload=json.dumps(validation_errors))
                    return {"job_id": jid, "status": "failed", "diagnostics": diag}
            else:
                upserted, upsert_errors = upsert_products(conn, valid_items, partner_id=partner_id)
                cur = conn.cursor()
                diag = {"accepted": upserted, "rejected": len(upsert_errors), "errors": upsert_errors}
                djson = json.dumps(diag)
                if len(djson) > 2000:
                    odcur = conn.cursor()
                    odcur.execute("INSERT INTO partner_ingest_diagnostics (job_id, diagnostics) VALUES (?, ?)", (jid, djson))
                    off_id = odcur.lastrowid
                    cur.execute("UPDATE partner_ingest_jobs SET status='done', processed_at = CURRENT_TIMESTAMP, diagnostics = ? WHERE id = ?", (json.dumps({"errors_link": f"/partner/diagnostics/{off_id}"}), jid))
                    conn.commit()
                    record_audit(partner_id, None, "worker_processed", payload=str(jid))
                    return {"job_id": jid, "status": "done", "diagnostics": {"errors_link": f"/partner/diagnostics/{off_id}"}}
                else:
                    cur.execute("UPDATE partner_ingest_jobs SET status='done', processed_at = CURRENT_TIMESTAMP, diagnostics = ? WHERE id = ?", (djson, jid))
                    conn.commit()
                    record_audit(partner_id, None, "worker_processed", payload=str(jid))
                    return {"job_id": jid, "status": "done", "diagnostics": diag}
        except Exception as e:
            cur = conn.cursor()
            cur.execute("UPDATE partner_ingest_jobs SET status='failed', error = ? WHERE id = ?", (str(e), jid))
            conn.commit()
            record_audit(partner_id, None, "worker_exception", payload=str(e))
            return {"job_id": jid, "status": "failed", "error": str(e)}
    finally:
        conn.close()

