#!/usr/bin/env python3
"""
End-to-end demo script for local Checkpoint2 app.

Usage:
  PYTHONPATH=. python scripts/run_demo.py --seed --partner-sync

Options implemented in script:
 - --seed : run src/seed.py to ensure demo data exists
 - --partner-sync : run a synchronous partner ingest
 - --partner-async : run an async partner ingest and poll job status
 - --contract-validate : call contract validate endpoint
 - --onboard : call partner onboarding (admin) and return new api key
 - --flash-checkout : simulate a user logging in, adding item to cart, and checking out

The script assumes the app is already running at http://127.0.0.1:5000
and that `test-key` is seeded as the partner API key (seed step ensures this).

It prints JSON responses for each step.
"""

import argparse
import subprocess
import sys
import time
import json
from pathlib import Path
import requests

BASE = "http://127.0.0.1:5000"

session = requests.Session()


def run_seed():
    print("Running DB seed...")
    res = subprocess.run([sys.executable, "-m", "src.seed"], capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        raise SystemExit("Seeding failed")


def partner_contract():
    print("GET /partner/contract")
    r = requests.get(f"{BASE}/partner/contract")
    print(r.status_code, r.text)


def partner_onboard():
    print("POST /partner/onboard (admin)")
    payload = {"name": "Demo Onboard", "format": "json", "description": "from demo script"}
    r = requests.post(f"{BASE}/partner/onboard", json=payload, headers={"X-Admin-Key": "admin-demo-key"})
    print(r.status_code, r.text)
    return r.json() if r.ok else None


def partner_sync_ingest(api_key="test-key"):
    print("POST /partner/ingest?async=0 (sync)")
    data = [{"sku": "demo-sync-1", "name": "Demo Sync", "price_cents": 1999, "stock": 5}]
    r = requests.post(f"{BASE}/partner/ingest?async=0", json=data, headers={"X-API-Key": api_key})
    print(r.status_code, r.text)
    return r


def partner_async_ingest(api_key="test-key"):
    print("POST /partner/ingest (async)")
    data = [{"sku": "demo-async-1", "name": "Demo Async", "price_cents": 1299, "stock": 3}]
    r = requests.post(f"{BASE}/partner/ingest?async=1", json=data, headers={"X-API-Key": api_key})
    print(r.status_code, r.text)
    if r.status_code == 202:
        try:
            j = r.json()
            return j.get("job_id")
        except Exception:
            return None
    return None


def poll_job(job_id, api_key="test-key", timeout=30):
    print(f"Polling job {job_id} ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{BASE}/partner/jobs/{job_id}", headers={"X-API-Key": api_key})
        if r.status_code == 200:
            j = r.json()
            print(json.dumps(j, indent=2))
            if j.get("status") in ("done", "failed"):
                return j
        else:
            print(r.status_code, r.text)
        time.sleep(2)
    raise SystemExit("Job did not complete in time")


def fetch_diagnostics(diag_id, api_key="test-key"):
    print(f"GET /partner/diagnostics/{diag_id}")
    r = requests.get(f"{BASE}/partner/diagnostics/{diag_id}", headers={"X-API-Key": api_key})
    print(r.status_code, r.text)
    return r


def contract_validate():
    print("POST /partner/contract/validate")
    data = [{"sku": "sample-1", "name": "Sample", "price_cents": 1000, "stock": 1}]
    r = requests.post(f"{BASE}/partner/contract/validate", json=data)
    print(r.status_code, r.text)
    return r


def flash_sale_checkout():
    print("Simulate user login, add product to cart, checkout")
    # login to obtain session
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": "john", "password": "password123"}, allow_redirects=True)
    print("login", r.status_code)
    # add product id 1 to cart
    r = s.post(f"{BASE}/cart/add", data={"product_id": 1, "qty": 1}, allow_redirects=True)
    print("add to cart", r.status_code)
    # checkout
    r = s.post(f"{BASE}/checkout", data={"payment_method": "CARD"}, allow_redirects=True)
    print("checkout", r.status_code)
    # print receipt page snippet
    print(r.text[:1000])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", action="store_true", help="Run DB seed")
    p.add_argument("--partner-sync", action="store_true")
    p.add_argument("--partner-async", action="store_true")
    p.add_argument("--contract-validate", action="store_true")
    p.add_argument("--onboard", action="store_true")
    p.add_argument("--flash-checkout", action="store_true")
    args = p.parse_args()

    if args.seed:
        run_seed()
    if args.onboard:
        partner_onboard()
    if args.partner_sync:
        partner_sync_ingest()
    if args.partner_async:
        jid = partner_async_ingest()
        if jid:
            poll_job(jid)
    if args.contract_validate:
        contract_validate()
    if args.flash_checkout:
        flash_sale_checkout()

    print("Done")
