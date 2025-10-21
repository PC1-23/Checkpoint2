import tempfile
import os
import sqlite3
import json
from pathlib import Path

from src.partners.testing import create_test_db, seed_partner_and_key
from src.partners.ingest_queue import enqueue_feed_db, process_next_job_once


def test_enqueue_and_process_job_once(tmp_path):
    db_file = str(tmp_path / "test_app.sqlite")
    create_test_db(db_file)

    partner_id = seed_partner_and_key(db_file, partner_name="t1", api_key="k1")

    products = [{"sku": "sku-test-1", "name": "Test Item", "price_cents": 1000, "stock": 2}]
    jid = enqueue_feed_db(db_file, partner_id, products, feed_hash="h1")
    assert jid is not None

    res = process_next_job_once(db_file)
    assert res is not None
    assert res.get("status") == "done"

    # verify product exists
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT name, price_cents, stock FROM product WHERE name = ?", ("Test Item",))
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "Test Item"
    assert row[1] == 1000
    assert row[2] == 2
