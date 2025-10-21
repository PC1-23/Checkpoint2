import os
import json
import time
import sqlite3
import importlib
from pathlib import Path


def setup_db(tmp_path):
    dbfile = tmp_path / "test_app.sqlite"
    sql = Path("db/init.sql").read_text()
    conn = sqlite3.connect(str(dbfile))
    conn.executescript(sql)
    cur = conn.cursor()
    cur.execute("INSERT INTO partner (name, format, endpoint) VALUES (?, ?, ?)", ("WorkerPartner", "json", "/"))
    pid = cur.lastrowid
    cur.execute("INSERT INTO partner_api_keys (partner_id, api_key) VALUES (?, ?)", (pid, "test-key"))
    conn.commit()
    conn.close()
    return str(dbfile), pid


def test_worker_processes_enqueued_job(tmp_path):
    db_path, pid = setup_db(tmp_path)
    os.environ["APP_DB_PATH"] = db_path

    import src.partners.routes as routes
    import src.partners.ingest_queue as iq
    importlib.reload(routes)
    importlib.reload(iq)

    app = routes.app
    client = app.test_client()

    payload = [{"sku": "sku-worker-1", "name": "WorkerProduct", "price": 2.5, "stock": 3}]
    # call async endpoint which enqueues job to DB
    resp = client.post("/partner/ingest?async=1", data=json.dumps(payload), content_type="application/json", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 202

    # start worker against the test DB
    stop = iq.start_worker(db_path)

    # wait up to 3 seconds for job to be processed
    for _ in range(30):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT status FROM partner_ingest_jobs ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row and row[0] == 'done':
            break
        time.sleep(0.1)

    # verify product inserted
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, price_cents FROM product WHERE name = ?", ("WorkerProduct",))
    rows = cur.fetchall()
    assert len(rows) == 1

    # cleanup
    iq.stop_worker()


def test_metrics_endpoint_updates(tmp_path):
    db_path, pid = setup_db(tmp_path)
    os.environ["APP_DB_PATH"] = db_path

    import src.partners.routes as routes
    import src.partners.ingest_queue as iq
    importlib.reload(routes)
    importlib.reload(iq)

    app = routes.app
    client = app.test_client()

    # initial metrics
    r = client.get('/partner/metrics')
    assert r.status_code == 200
    before = r.get_json()

    payload = [{"sku": "sku-metrics-1", "name": "MetricsProduct", "price": 2.5, "stock": 3}]
    resp = client.post("/partner/ingest?async=1", data=json.dumps(payload), content_type="application/json", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 202

    # start worker
    iq.start_worker(db_path)
    # wait for processing
    import time
    for _ in range(30):
        r = client.get('/partner/metrics')
        data = r.get_json()
        if data.get('processed', 0) > before.get('processed', 0):
            break
        time.sleep(0.1)

    r = client.get('/partner/metrics')
    data = r.get_json()
    assert data.get('enqueued', 0) >= 1
    assert data.get('processed', 0) >= 1


def test_requeue_failed_job(tmp_path):
    db_path, pid = setup_db(tmp_path)
    os.environ["APP_DB_PATH"] = db_path

    import src.partners.routes as routes
    import src.partners.ingest_queue as iq
    importlib.reload(routes)
    importlib.reload(iq)

    app = routes.app
    client = app.test_client()

    # create a job with invalid payload that will fail validation (empty name)
    bad_payload = [{"sku": "sku-bad", "name": "", "price": 1.0, "stock": 1}]
    resp = client.post("/partner/ingest?async=1", data=json.dumps(bad_payload), content_type="application/json", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 202

    # run worker to process and wait for failed job
    iq.start_worker(db_path)
    import time
    job_id = None
    for _ in range(50):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM partner_ingest_jobs WHERE status = 'failed' LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            job_id = row[0]
            break
        time.sleep(0.1)
    assert job_id is not None

    # requeue the failed job using API key
    r = client.post(f"/partner/jobs/{job_id}/requeue", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200

    # start worker and ensure it processes (it should fail again on validation but status will be failed)
    # ensure worker has had time to reprocess the job
    import time
    st = None
    for _ in range(60):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT status FROM partner_ingest_jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            st = row[0]
            if st in ("failed", "done"):
                break
        time.sleep(0.1)
    assert st in ("failed", "done")
