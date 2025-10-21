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

logger = logging.getLogger(__name__)


def enqueue_feed_db(db_path: str, partner_id: int, products: list[Dict[str, Any]], feed_hash: str | None = None) -> int:
    """Persist a job into the partner_ingest_jobs table and return job id."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO partner_ingest_jobs (partner_id, payload, status, feed_hash) VALUES (?, ?, 'pending', ?)", (partner_id, json.dumps(products), feed_hash))
    jid = cur.lastrowid
    conn.commit()
    conn.close()
    incr("enqueued")
    return jid


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


def worker_loop(db_path: str, poll_interval: float = 0.5):
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
                else:
                    valid, errors = validate_products(products)
                    if valid:
                        upserted, upsert_errors = upsert_products(conn, valid, partner_id=partner_id)
                        logger.info("Ingest processed job=%s partner=%s upserted=%s errors=%s", jid, partner_id, upserted, upsert_errors)
                        cur = conn.cursor()
                        cur.execute("UPDATE partner_ingest_jobs SET status='done', processed_at = CURRENT_TIMESTAMP WHERE id = ?", (jid,))
                        conn.commit()
                        incr("processed")
                    else:
                        logger.warning("Ingest validation failed for job=%s partner=%s errors=%s", jid, partner_id, errors)
                        cur = conn.cursor()
                        cur.execute("UPDATE partner_ingest_jobs SET status='failed', error = ? WHERE id = ?", (json.dumps(errors), jid))
                        conn.commit()
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

