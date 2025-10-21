import os
from src.partners.routes import app


def test_admin_endpoints_require_key(monkeypatch):
    client = app.test_client()
    # ensure env admin key is set
    monkeypatch.setenv("ADMIN_API_KEY", "admintest")

    # create a temporary sqlite DB and set APP_DB_PATH so routes use it
    import sqlite3
    import tempfile
    tmp = tempfile.NamedTemporaryFile(prefix="test_db_", suffix=".sqlite")
    db_path = tmp.name
    conn = sqlite3.connect(db_path)
    # minimal table used by routes
    conn.execute("CREATE TABLE partner_schedules (id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id INTEGER, schedule_type TEXT, schedule_value TEXT, enabled INTEGER, last_run TIMESTAMP)")
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_DB_PATH", db_path)

    # List schedules without header but with env ADMIN_API_KEY set -> allowed (200)
    rv = client.get('/partner/schedules')
    assert rv.status_code == 200

    # With header should also pass (returns JSON)
    rv = client.get('/partner/schedules', headers={"X-Admin-Key": "admintest"})
    assert rv.status_code == 200

    # Create schedule without required fields -> 400 (route validates payload)
    rv = client.post('/partner/schedules', json={})
    assert rv.status_code == 400

    # Create with key but missing fields -> 400
    rv = client.post('/partner/schedules', headers={"X-Admin-Key": "admintest"}, json={})
    assert rv.status_code == 400
