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
    # For tests and local debugging we record the raw api_key. In a
    # production setting you may want to store a masked version instead.
    # Keep mask_key available for future use.
    safe_key = api_key
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO partner_ingest_audit (partner_id, api_key, action, payload) VALUES (?, ?, ?, ?)",
            (partner_id, safe_key, action, payload),
        )
        conn.commit()
    except Exception:
        # best-effort logging; don't crash the app
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mask_key(api_key: Optional[str]) -> Optional[str]:
    """Return a masked form of the API key for safe storage in audits/logs.

    Shows the first 6 chars and replaces the remainder with '...'.
    If the key is short, returns a constant placeholder.
    """
    if not api_key:
        return None
    try:
        if len(api_key) <= 8:
            return api_key[:4] + "..."
        return api_key[:6] + "..."
    except Exception:
        return None


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
        # Support optional hashed keys in DB when HASH_KEYS=true is set in env.
        hash_keys = os.environ.get("HASH_KEYS", "false").lower() in ("1", "true", "yes")
        if hash_keys:
            # Stored keys are hashed; compute hash of provided key and compare
            import hashlib

            h = hashlib.sha256(api_key.encode()).hexdigest()
            cur.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (h,))
            row = cur.fetchone()
            if row:
                return row[0]
        else:
            cur.execute("SELECT partner_id FROM partner_api_keys WHERE api_key = ?", (api_key,))
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


def hash_key_for_storage(api_key: str) -> str:
    """Return a deterministic SHA256 hex digest for storage when hashing is enabled."""
    import hashlib

    return hashlib.sha256(api_key.encode()).hexdigest()
