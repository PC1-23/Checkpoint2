#!/usr/bin/env bash
# demo_run_tests.sh
# Run all tests with explanation snippets for a demo video.
# Usage: ./tools/demo_run_tests.sh

set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# Ensure the repository root is on PYTHONPATH so tests can import the `src` package
export PYTHONPATH="$ROOT":${PYTHONPATH-}

# Each entry: test path and a one-line description used in demo narration.
declare -a TESTS=()
declare -a DESC=()

TESTS+=("tests/test_migrations.py")
DESC+=("DB schema and migration checks")

TESTS+=("tests/test_testability_integration.py")
DESC+=("Project testability and helpers")

TESTS+=("tests/test_partner_adapters.py")
DESC+=("Adapter parsing (CSV/JSON) behavior")

TESTS+=("tests/test_concurrent_checkout.py")
DESC+=("Concurrency test for checkout flow")

TESTS+=("tests/test_scheduler_crud.py")
DESC+=("Scheduler CRUD operations")

TESTS+=("tests/test_product_repo.py")
DESC+=("Product repository unit tests")

TESTS+=("tests/test_usability_endpoints.py")
DESC+=("Usability endpoints and error shaping (ADR 0013)")

TESTS+=("tests/test_worker_end_to_end.py")
DESC+=("End-to-end worker + enqueue processing")

TESTS+=("tests/test_audit_entries.py")
DESC+=("Audit table writes and masking behavior")

TESTS+=("tests/test_admin_auth.py")
DESC+=("Admin authentication behaviour (session-only) and login")

TESTS+=("tests/unit_test.py")
DESC+=("Misc small unit tests")

TESTS+=("tests/test_integration_partner_ingest.py")
DESC+=("Integration tests for partner ingest flow")

TESTS+=("tests/test_validation.py")
DESC+=("Validation logic for feeds")

TESTS+=("tests/test_rate_limiting.py")
DESC+=("Rate limiting and throttling behavior")

# flash_sales tests (group)
TESTS+=("tests/flash_sales/test_circuit_breaker.py")
DESC+=("Flash sales: circuit breaker tests")

TESTS+=("tests/flash_sales/test_flash_sale_manager.py")
DESC+=("Flash sale manager logic")

TESTS+=("tests/flash_sales/test_retry.py")
DESC+=("Retry and resilience tests for payments")

# summary counters
TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0

# Run tests in sequence with per-file output
for i in "${!TESTS[@]}"; do
  TEST_PATH=${TESTS[$i]}
  TEST_DESC=${DESC[$i]}
  ((TOTAL++))
  echo
  echo "============================================================"
  echo "Running test [$TOTAL/${#TESTS[@]}]: $TEST_PATH"
  echo "Description: $TEST_DESC"
  echo "------------------------------------------------------------"
  # run pytest for this file only, show verbose output
  if pytest -q "$TEST_PATH"; then
    echo "[PASS] $TEST_PATH"
    ((PASSED++))
  else
    echo "[FAIL] $TEST_PATH"
    ((FAILED++))
  fi
done

# Run any remaining tests not listed (safety)
echo
echo "============================================================"
echo "Running full pytest -q to catch any additional tests (optional)"
if pytest -q; then
  echo "[PASS] full pytest"
else
  echo "[FAIL] full pytest"
fi

# Summary
echo
echo "============================================================"
echo "TEST SUMMARY: total=$TOTAL passed=$PASSED failed=$FAILED"
if [ "$FAILED" -eq 0 ]; then
  echo "ALL LISTED TESTS PASSED"
else
  echo "SOME TESTS FAILED: inspect pytest output above"
fi

exit 0
