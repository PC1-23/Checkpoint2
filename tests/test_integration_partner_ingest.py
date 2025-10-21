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
    cur.execute("INSERT INTO partner (name, format, endpoint) VALUES (?, ?, ?)", ("TestPartner", "json", "/"))
    pid = cur.lastrowid
    cur.execute("INSERT INTO partner_api_keys (partner_id, api_key) VALUES (?, ?)", (pid, "test-key"))
    conn.commit()
    conn.close()
    return str(dbfile), pid


def test_sync_ingest(tmp_path):
    db_path, pid = setup_db(tmp_path)
    os.environ["APP_DB_PATH"] = db_path

    # import app after env is set so get_conn picks up the test DB
    import src.partners.routes as routes
    importlib.reload(routes)
    app = routes.app

    client = app.test_client()
    payload = [{"sku": "sku-test-sync", "name": "SyncTest", "price": 4.5, "stock": 2}]
    resp = client.post("/partner/ingest?async=0", data=json.dumps(payload), content_type="application/json", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, price_cents, stock FROM product WHERE name = ?", ("SyncTest",))
    rows = cur.fetchall()
    assert len(rows) == 1

    cur.execute("SELECT id FROM partner_feed_imports WHERE partner_id = ?", (pid,))
    imports = cur.fetchall()
    assert len(imports) == 1
    conn.close()


def test_async_ingest_enqueue_called(tmp_path, monkeypatch):
    db_path, pid = setup_db(tmp_path)
    os.environ["APP_DB_PATH"] = db_path

    import src.partners.routes as routes
    importlib.reload(routes)
    app = routes.app

    # replace enqueue_feed and start_worker on the routes module so the route will call our test double
    called = []

    def fake_enqueue(partner_id, products):
        called.append((partner_id, products))

    monkeypatch.setattr(routes, "enqueue_feed", fake_enqueue)
    monkeypatch.setattr(routes, "start_worker", lambda db_path: None)

    client = app.test_client()
    payload = [{"sku": "sku-test-async", "name": "AsyncTest", "price": 1.25, "stock": 1}]
    resp = client.post("/partner/ingest?async=1", data=json.dumps(payload), content_type="application/json", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 202
    assert len(called) == 1
    assert called[0][0] == pid
    # product payload should be passed through (or similar dict); ensure name present
    assert any(p.get("name") == "AsyncTest" for p in called[0][1])
