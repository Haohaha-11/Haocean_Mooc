#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
STUDENT_ID="${STUDENT_ID:-2024001}"
TEACHER_ID="${TEACHER_ID:-T001}"
ASSIGNMENT_ID="module_d_verify_$(date +%s)"
SERVER_LOG="${ROOT_DIR}/module_d_ops/module_b_verify.log"
WORKSPACE_DIR="$(mktemp -d)"
CACHE_DIR="$(mktemp -d)"
FEEDBACK_DIR="$(mktemp -d)"

cd "${ROOT_DIR}"

echo "[Module_D] [1/7] Running module tests"
make test

echo "[Module_D] [2/7] Starting Module B server"
cd "${ROOT_DIR}/module_b_server"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > "${SERVER_LOG}" 2>&1 &
SERVER_PID=$!
trap 'kill "${SERVER_PID}" >/dev/null 2>&1 || true; rm -rf "${WORKSPACE_DIR}" "${CACHE_DIR}" "${FEEDBACK_DIR}"' EXIT

for _ in {1..30}; do
  if curl -fsS "${BASE_URL}/health" >/dev/null; then
    break
  fi
  sleep 1
done
curl -fsS "${BASE_URL}/health" >/dev/null

echo "[Module_D] [3/7] Running Module B smoke test"
bash scripts/smoke_test.sh

echo "[Module_D] [4/7] Creating assignment for Module A integration"
curl -fsS -X POST "${BASE_URL}/v1/assignments" \
  -H "Content-Type: application/json" \
  -d "{
    \"action\": \"CREATE_ASSIGNMENT\",
    \"timestamp\": $(date +%s),
    \"payload\": {
      \"teacher_id\": \"${TEACHER_ID}\",
      \"assignment_id\": \"${ASSIGNMENT_ID}\",
      \"title\": \"Module D Verify\",
      \"description\": \"Created by module D verification.\",
      \"deadline\": \"2026-06-01 23:59:59\"
    }
  }" >/dev/null

echo "[Module_D] [5/7] Submitting with Module A"
cd "${ROOT_DIR}/module_a_client"
mkdir -p "${WORKSPACE_DIR}/${ASSIGNMENT_ID}"
printf 'module D integration answer\n' > "${WORKSPACE_DIR}/${ASSIGNMENT_ID}/answer.txt"
MODULE_A_STUDENT_ID="${STUDENT_ID}" \
MODULE_A_WORKSPACE_DIR="${WORKSPACE_DIR}" \
MODULE_A_CACHE_DIR="${CACHE_DIR}" \
MODULE_A_FEEDBACK_DIR="${FEEDBACK_DIR}" \
MODULE_A_DEBOUNCE_SECONDS=0 \
MODULE_A_POLL_INTERVAL_SECONDS=0 \
MODULE_A_RETRY_BACKOFF_SECONDS=0 \
python3 -B scripts/run_client.py once

echo "[Module_D] [6/7] Checking pending submission"
PENDING_RESPONSE="$(curl -fsS "${BASE_URL}/v1/submissions/pending")"
python3 - "${ASSIGNMENT_ID}" "${PENDING_RESPONSE}" <<'PY'
import json
import sys

assignment_id = sys.argv[1]
data = json.loads(sys.argv[2])
submissions = data["payload"]["submissions"]
if not any(item["assignment_id"] == assignment_id for item in submissions):
    raise SystemExit(f"pending submission not found for {assignment_id}")
PY

echo "[Module_D] [7/7] Verification completed"
