#!/usr/bin/env bash

set -e

BASE_URL="http://127.0.0.1:8000"
STUDENT_ID="2024001"
TEACHER_ID="T001"
ASSIGNMENT_ID="home_smoke_$(date +%s)"
WORK_DIR="/tmp/module_b_smoke_test"
PACKAGE_PATH="${WORK_DIR}/${STUDENT_ID}_${ASSIGNMENT_ID}.tar.gz"

echo "========== Module B Smoke Test =========="
echo "[1/8] Health check..."
curl -s "${BASE_URL}/health"
echo
echo

echo "[2/8] Create assignment..."
curl -s -X POST "${BASE_URL}/v1/assignments" \
  -H "Content-Type: application/json" \
  -d "{
    \"action\": \"CREATE_ASSIGNMENT\",
    \"timestamp\": $(date +%s),
    \"payload\": {
      \"teacher_id\": \"${TEACHER_ID}\",
      \"assignment_id\": \"${ASSIGNMENT_ID}\",
      \"title\": \"Smoke Test Assignment\",
      \"description\": \"This assignment is created by smoke_test.sh\",
      \"deadline\": \"2026-06-01 23:59:59\"
    }
  }"
echo
echo

echo "[3/8] List open assignments..."
curl -s "${BASE_URL}/v1/assignments/open"
echo
echo

echo "[4/8] Create fake homework package..."
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}/${ASSIGNMENT_ID}"
echo "hello from smoke test" > "${WORK_DIR}/${ASSIGNMENT_ID}/answer.txt"
tar -czf "${PACKAGE_PATH}" -C "${WORK_DIR}" "${ASSIGNMENT_ID}"
MD5=$(md5sum "${PACKAGE_PATH}" | awk '{print $1}')
echo "package: ${PACKAGE_PATH}"
echo "md5: ${MD5}"
echo

echo "[5/8] Submit homework package..."
SUBMIT_RESPONSE=$(curl -s -X POST "${BASE_URL}/v1/submissions" \
  -F "metadata={\"action\":\"SUBMIT\",\"timestamp\":$(date +%s),\"payload\":{\"student_id\":\"${STUDENT_ID}\",\"assignment_id\":\"${ASSIGNMENT_ID}\",\"md5\":\"${MD5}\"}}" \
  -F "file=@${PACKAGE_PATH}")

echo "${SUBMIT_RESPONSE}"
echo

SUBMISSION_ID=$(python3 - <<PY
import json
data = json.loads('''${SUBMIT_RESPONSE}''')
print(data["payload"]["submission_id"])
PY
)

echo "submission_id: ${SUBMISSION_ID}"
echo

echo "[6/8] List pending submissions..."
curl -s "${BASE_URL}/v1/submissions/pending"
echo
echo

echo "[7/8] Grade submission..."
curl -s -X POST "${BASE_URL}/v1/submissions/grade" \
  -H "Content-Type: application/json" \
  -d "{
    \"action\": \"GRADE\",
    \"timestamp\": $(date +%s),
    \"payload\": {
      \"submission_id\": ${SUBMISSION_ID},
      \"teacher_id\": \"${TEACHER_ID}\",
      \"score\": 95,
      \"comment\": \"Smoke test passed. Module B submit, archive, grade and feedback flow works.\",
      \"status\": \"graded\"
    }
  }"
echo
echo

echo "[8/8] Query feedback..."
curl -s "${BASE_URL}/v1/feedback/${STUDENT_ID}"
echo
echo

echo "========== Smoke Test Finished =========="