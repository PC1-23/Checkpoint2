#!/usr/bin/env zsh
# Demo script: Steps 2-6 for tactics demo (auth fail, validation, rate-limit, payment resilience, DB rollback)
# Run this from the repo root while the app is running (PYTHONPATH=. python -m src.app)

# Adjust these if your environment differs
CSV_PATH="/Users/wuyanlin/Desktop/checkpoint2/products_error.csv"
DB_PATH="app.sqlite"
API_KEY="test-key"
ADMIN_KEY="admin-demo-key"

echo "=== Demo: Steps 2-6 (auth fail, validation, rate-limit, payment resilience, rollback) ==="

echo "\n--- Step 2: Auth failure (no API key) ---"
echo "Command: curl -i -X POST http://127.0.0.1:5000/partner/ingest -H 'Content-Type: application/json' --data '[]'"
curl -i -X POST http://127.0.0.1:5000/partner/ingest -H "Content-Type: application/json" --data '[]' || true

echo "\n--- Step 3: Upload validation (invalid CSV, sync) ---"
echo "Command: curl -s -X POST \"http://127.0.0.1:5000/partner/ingest?async=0\" -H \"X-API-Key: $API_KEY\" -H \"Content-Type: text/csv\" --data-binary @${CSV_PATH}"
if command -v jq >/dev/null 2>&1; then
  curl -s -X POST "http://127.0.0.1:5000/partner/ingest?async=0" -H "X-API-Key: $API_KEY" -H "Content-Type: text/csv" --data-binary @"${CSV_PATH}" | jq . || true
else
  curl -s -X POST "http://127.0.0.1:5000/partner/ingest?async=0" -H "X-API-Key: $API_KEY" -H "Content-Type: text/csv" --data-binary @"${CSV_PATH}" | python -m json.tool || true
fi

echo "\n--- Step 4: Rate limit burst (prints HTTP codes, look for 429) ---"
echo "Command: loop 40 curl calls (may trigger rate limiter)"
for i in {1..40}; do
  curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $API_KEY" http://127.0.0.1:5000/partner/ingest &
done
wait

echo "\nRecent partner ingest audit entries (last 5):"
sqlite3 "$DB_PATH" "SELECT id, action, created_at FROM partner_ingest_audit ORDER BY id DESC LIMIT 5;"

echo "\n--- Step 5: Payment resilience (retry + circuit breaker demo) ---"
echo "This runs a small Python snippet that calls the resilient wrapper and prints the circuit state."
PYTHONPATH=. python - <<'PY'
from src.flash_sales.payment_resilience import process_payment_resilient, payment_circuit_breaker
print('Normal call (CARD, 100):', process_payment_resilient('CARD', 100))
print('\nSimulate repeated DECLINED calls to trigger/open circuit:')
for i in range(6):
    status, ref = process_payment_resilient('DECLINE_TEST', 100)
    print(f"attempt={i} -> status={status}, ref={ref}, breaker={payment_circuit_breaker.get_state().value}")
PY

echo "\n--- Step 6: No partial writes demonstration (sale count before/after a DECLINED attempt) ---"
BEFORE=$(sqlite3 "$DB_PATH" "SELECT COUNT(1) FROM sale;")
echo "Sale count before: $BEFORE"

echo "Trigger a DECLINED payment via resilience wrapper (no DB writes expected):"
PYTHONPATH=. python - <<'PY'
from src.flash_sales.payment_resilience import process_payment_resilient
print('Triggering DECLINE_TEST ->', process_payment_resilient('DECLINE_TEST', 100))
PY

AFTER=$(sqlite3 "$DB_PATH" "SELECT COUNT(1) FROM sale;")
echo "Sale count after: $AFTER"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "No new sale recorded -> rollback/no partial writes confirmed."
else
  echo "Sale count changed ($BEFORE -> $AFTER) — investigate."
fi

echo "\n=== Demo script finished ==="
