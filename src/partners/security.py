from __future__ import annotations
import time
import threading
import sqlite3
from typing import Optional
from pathlib import Path
import os

# Simple in-memory rate limiter per API key (token bucket-like)
_limits: dict = {}
_lock = threading.Lock()
_inflight: set = set()


def _get_db_path() -> str:
    root = Path(__file__).resolve().parents[2]
    return str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))


def check_rate_limit(api_key: str, max_per_minute: int = 60) -> bool:
    now = int(time.time())
    window = now // 60
    with _lock:
        entry = _limits.get(api_key)
        if not entry or entry[0] != window:
            _limits[api_key] = (window, 1)
            return True
        if entry[1] < max_per_minute:
            _limits[api_key] = (entry[0], entry[1] + 1)
            return True
        return False


def try_acquire_inflight(api_key: str) -> bool:
    """Attempt to reserve an inflight slot for this API key.

    Returns True if the slot was acquired, False if another request is
    already in progress for the same key. This is a lightweight in-process
    guard intended for demos to avoid concurrent writes to SQLite.
    """
    with _lock:
        if api_key in _inflight:
            return False
        _inflight.add(api_key)
        return True


def release_inflight(api_key: str) -> None:
    """Release a previously-acquired inflight slot for the API key."""
    with _lock:
        try:
            _inflight.remove(api_key)
        except KeyError:
            pass


def record_audit(partner_id: Optional[int], api_key: Optional[str], action: str, payload: Optional[str] = None):
    db = _get_db_path()
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("INSERT INTO partner_ingest_audit (partner_id, api_key, action, payload) VALUES (?, ?, ?, ?)", (partner_id, api_key, action, payload))
        conn.commit()
    except Exception:
        # best-effort logging; don't crash the app
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def verify_api_key(db_path: Optional[str], api_key: str) -> Optional[int]:
    """Verify API key against partner_api_keys table. Returns partner_id or None.

    This helper supports plain-text keys for demo. Production should store
    hashed keys and use a constant-time compare.
    """
    try:
        if not db_path:
            root = Path(__file__).resolve().parents[2]
            db_path = str(Path(os.environ.get("APP_DB_PATH") or root / "app.sqlite"))
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT partner_id, api_key FROM partner_api_keys WHERE api_key = ?", (api_key,))
        row = cur.fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return None
