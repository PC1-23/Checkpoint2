import os
import json
import sqlite3
import importlib
from pathlib import Path


def setup_db(tmp_path):
    dbfile = tmp_path / "test_app.sqlite"
    sql = Path("db/init.sql").read_text()
    conn = sqlite3.connect(str(dbfile))
    conn.executescript(sql)
    cur = conn.cursor()
    # partner with endpoint and auth
    cur.execute("INSERT INTO partner (name, format, endpoint, endpoint_auth, endpoint_headers) VALUES (?, ?, ?, ?, ?)", (
        "AuthPartner", "json", "https://example.com/feed", json.dumps({"type":"bearer","token":"secrettoken"}), json.dumps({"X-Custom":"val"})
    ))
    pid = cur.lastrowid
    cur.execute("INSERT INTO partner_api_keys (partner_id, api_key) VALUES (?, ?)", (pid, "test-key"))
    conn.commit()
    conn.close()
    return str(dbfile), pid


def test_scheduler_fetch_auth(tmp_path, monkeypatch):
    db_path, pid = setup_db(tmp_path)
    os.environ["APP_DB_PATH"] = db_path

    import src.partners.scheduler as sched
    importlib.reload(sched)

    called = {}

    class FakeResp:
        def __init__(self, content=b'[]'):
            self.content = content
        def raise_for_status(self):
            return None

    def fake_get(url, timeout=10, headers=None, auth=None):
        called['url'] = url
        called['headers'] = headers
        called['auth'] = auth
        return FakeResp(b'[{"sku":"s","name":"n","price":1.0,"stock":1}]')

    monkeypatch.setattr('src.partners.scheduler.requests.get', fake_get)

    # call internal enqueue function directly
    sched._enqueue_for_partner(pid)

    assert called.get('url') == 'https://example.com/feed'
    # Authorization header should be present for bearer token
    assert 'Authorization' in (called.get('headers') or {})
    assert 'Bearer secrettoken' in called.get('headers').get('Authorization')
