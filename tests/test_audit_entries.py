import sqlite3
import os
from pathlib import Path

from src.partners.security import record_audit, verify_api_key


def get_test_db_path(tmp_path: Path) -> str:
    # copy or use repo sqlite for test; try to use APP_DB_PATH env if set
    repo_root = Path(__file__).resolve().parents[2]
    return str(tmp_path / "test_app.sqlite")


def test_record_audit_writes_row(tmp_path):
    db = get_test_db_path(tmp_path)
    # initialize minimal schema
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE partner_ingest_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id INTEGER, api_key TEXT, action TEXT, payload TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

    # set env to point helper to this db
    os.environ["APP_DB_PATH"] = db

    # call record_audit
    record_audit(1, "some-key", "test_action", payload="ok")

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT partner_id, api_key, action, payload FROM partner_ingest_audit ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    assert row == (1, "some-key", "test_action", "ok")


def test_verify_api_key_returns_none_for_missing(tmp_path):
    db = get_test_db_path(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE partner_api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id INTEGER, api_key TEXT)")
    conn.commit()
    conn.close()
    # no keys inserted
    res = verify_api_key(db, "nope")
    assert res is None
