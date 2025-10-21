from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any
# APScheduler is optional for tests/environments where it's not installed.
# Import inside start_scheduler to avoid failing module import when the
# dependency is not available.
from pathlib import Path
import sqlite3
from .ingest_queue import enqueue_feed_db
from .partner_adapters import parse_json_feed, parse_csv_feed
import requests
import hashlib

logger = logging.getLogger(__name__)


def _get_db_path() -> str:
    root = Path(__file__).resolve().parents[2]
    return str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))


def _load_schedules() -> list[Dict[str, Any]]:
    db = _get_db_path()
    conn = sqlite3.connect(db)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, partner_id, schedule_type, schedule_value, enabled FROM partner_schedules WHERE enabled = 1")
        rows = cur.fetchall()
        res = []
        for r in rows:
            sid, partner_id, stype, svalue, enabled = r
            try:
                parsed = json.loads(svalue)
            except Exception:
                parsed = svalue
            res.append({"id": sid, "partner_id": partner_id, "type": stype, "value": parsed})
        return res
    finally:
        conn.close()


def _enqueue_for_partner(partner_id: int):
    """Fetch the partner's feed (if endpoint configured), parse it and enqueue.

    If partner.endpoint is empty, we enqueue an empty payload (backward compatible).
    """
    db = _get_db_path()
    # look up partner.endpoint and format
    conn = sqlite3.connect(db)
    try:
        cur = conn.cursor()
        cur.execute("SELECT endpoint, format FROM partner WHERE id = ?", (partner_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            # no endpoint configured; enqueue empty payload
            enqueue_feed_db(db, partner_id, [])
            logger.info("No endpoint for partner %s; enqueued empty payload", partner_id)
            return
        endpoint, fmt = row[0], row[1] if len(row) > 1 else "json"
    finally:
        conn.close()

    try:
        # look up optional auth and headers for this partner
        auth = None
        headers = {}
        try:
            conn2 = sqlite3.connect(db)
            cur2 = conn2.cursor()
            cur2.execute("SELECT endpoint_auth, endpoint_headers FROM partner WHERE id = ?", (partner_id,))
            r2 = cur2.fetchone()
            if r2:
                try:
                    if r2[0]:
                        auth_blob = json.loads(r2[0])
                        if auth_blob.get("type") == "basic":
                            auth = (auth_blob.get("username"), auth_blob.get("password"))
                        elif auth_blob.get("type") == "bearer":
                            headers["Authorization"] = f"Bearer {auth_blob.get('token')}"
                except Exception:
                    pass
                try:
                    if r2[1]:
                        headers.update(json.loads(r2[1]))
                except Exception:
                    pass
        finally:
            try:
                conn2.close()
            except Exception:
                pass

        resp = requests.get(endpoint, timeout=10, headers=headers, auth=auth)
        resp.raise_for_status()
        content = resp.content
        # choose parser
        if fmt and fmt.lower().startswith("csv"):
            products = parse_csv_feed(content)
        else:
            products = parse_json_feed(content)
        # compute feed hash
        try:
            feed_hash = hashlib.sha256(content).hexdigest()
        except Exception:
            feed_hash = hashlib.sha256(json.dumps(products, sort_keys=True).encode()).hexdigest()

        enqueue_feed_db(db, partner_id, products, feed_hash=feed_hash)
        logger.info("Fetched and enqueued feed for partner %s products=%s", partner_id, len(products))
    except Exception as e:
        logger.exception("Failed to fetch/parse feed for partner %s: %s", partner_id, e)
        # on failure, enqueue an empty payload to record attempt
        enqueue_feed_db(db, partner_id, [])


def start_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger
    except Exception:
        logger.info("APScheduler not available; scheduler will be a no-op")
        return None
    scheduler = BackgroundScheduler()
    # load schedules from DB
    schedules = _load_schedules()
    for s in schedules:
        pid = s["partner_id"]
        if s["type"] == "interval":
            # expect value like {"seconds": 60}
            try:
                interval_args = s["value"] if isinstance(s["value"], dict) else {"seconds": int(s["value"]) }
                trigger = IntervalTrigger(**interval_args)
            except Exception:
                continue
        elif s["type"] == "cron":
            # value is dict of cron fields
            try:
                trigger = CronTrigger(**(s["value"] if isinstance(s["value"], dict) else {}))
            except Exception:
                continue
        else:
            continue

        scheduler.add_job(lambda pid=pid: _enqueue_for_partner(pid), trigger=trigger, id=f"partner_schedule_{s['id']}")
        logger.info("Scheduled job partner=%s id=%s", pid, s["id"])

    scheduler.start()
    return scheduler
