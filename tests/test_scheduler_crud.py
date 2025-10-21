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
    cur.execute("INSERT INTO partner (name, format, endpoint) VALUES (?, ?, ?)", ("SchedPartner", "json", "/"))
    pid = cur.lastrowid
    cur.execute("INSERT INTO partner_api_keys (partner_id, api_key) VALUES (?, ?)", (pid, "test-key"))
    conn.commit()
    conn.close()
    return str(dbfile), pid


def test_schedule_crud(tmp_path):
    db_path, pid = setup_db(tmp_path)
    os.environ["APP_DB_PATH"] = db_path

    import src.partners.routes as routes
    importlib.reload(routes)

    app = routes.app
    client = app.test_client()

    # create schedule
    r = client.post('/partner/schedules', json={"partner_id": pid, "schedule_type": "interval", "schedule_value": {"seconds": 60}, "enabled": True}, headers={"X-Admin-Key": "admin-demo-key"})
    assert r.status_code == 201

    # list schedules
    r = client.get('/partner/schedules', headers={"X-Admin-Key": "admin-demo-key"})
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # delete schedule
    sid = data[0]['id']
    r = client.delete(f'/partner/schedules/{sid}', headers={"X-Admin-Key": "admin-demo-key"})
    assert r.status_code == 200
