#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
STUDENT_ID="2024001"
TEACHER_ID="T001"
STUDENT_EMAIL="${SMOKE_STUDENT_EMAIL:-student@example.com}"
TEACHER_EMAIL="${SMOKE_TEACHER_EMAIL:-teacher@example.com}"
STUDENT_TOKEN="${SMOKE_STUDENT_TOKEN:-}"
TEACHER_TOKEN="${SMOKE_TEACHER_TOKEN:-}"
ASSIGNMENT_ID="home_smoke_$(date +%s)"
SMOKE_DEADLINE="${SMOKE_DEADLINE:-2099-12-31 23:59:59}"
WORK_DIR="/tmp/module_b_smoke_test"
PACKAGE_PATH="${WORK_DIR}/${STUDENT_ID}_${ASSIGNMENT_ID}.tar.gz"
HEALTH_RESPONSE=""

json_get() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

raw = sys.argv[1]
expr = sys.argv[2].split(".")
data = json.loads(raw)
for key in expr:
    if key == "":
        continue
    if isinstance(data, dict):
        data = data.get(key)
    else:
        data = None
        break
print("" if data is None else data)
PY
}

build_auth_header() {
  local token="$1"
  if [[ -n "${token}" ]]; then
    printf 'Authorization: Bearer %s' "${token}"
  fi
}

login_with_dev_code() {
  local role="$1"
  local email="$2"
  local display_id="$3"

  local request_response
  request_response=$(curl -s -X POST "${BASE_URL}/v1/auth/request-code" \
    -H "Content-Type: application/json" \
    -d "{
      \"action\": \"REQUEST_LOGIN_CODE\",
      \"timestamp\": $(date +%s),
      \"payload\": {
        \"email\": \"${email}\",
        \"role\": \"${role}\",
        \"display_id\": \"${display_id}\"
      }
    }")

  local code
  code="$(json_get "${request_response}" "payload.dev_code")"
  if [[ -z "${code}" ]]; then
    echo "SMOKE ERROR: auth is required but no dev_code returned for ${role}. Set SMOKE_${role^^}_TOKEN or enable MODULE_B_DEV_VERIFICATION_LOG=true." >&2
    echo "request response: ${request_response}" >&2
    exit 1
  fi

  local login_response
  login_response=$(curl -s -X POST "${BASE_URL}/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{
      \"action\": \"LOGIN_WITH_CODE\",
      \"timestamp\": $(date +%s),
      \"payload\": {
        \"email\": \"${email}\",
        \"role\": \"${role}\",
        \"display_id\": \"${display_id}\",
        \"code\": \"${code}\"
      }
    }")

  local token
  token="$(json_get "${login_response}" "payload.token")"
  if [[ -z "${token}" ]]; then
    echo "SMOKE ERROR: login failed for ${role}" >&2
    echo "login response: ${login_response}" >&2
    exit 1
  fi

  printf '%s' "${token}"
}

echo "========== Module B Smoke Test =========="
echo "[1/8] Health check..."
HEALTH_RESPONSE="$(curl -s "${BASE_URL}/health")"
echo "${HEALTH_RESPONSE}"
echo
echo

if [[ "$(json_get "${HEALTH_RESPONSE}" "auth_required")" == "True" ]] || [[ "$(json_get "${HEALTH_RESPONSE}" "auth_required")" == "true" ]]; then
  echo "[Auth] Module B requires authorization."
  if [[ -z "${TEACHER_TOKEN}" ]]; then
    TEACHER_TOKEN="$(login_with_dev_code "teacher" "${TEACHER_EMAIL}" "${TEACHER_ID}")"
  fi
  if [[ -z "${STUDENT_TOKEN}" ]]; then
    STUDENT_TOKEN="$(login_with_dev_code "student" "${STUDENT_EMAIL}" "${STUDENT_ID}")"
  fi
  echo "[Auth] Teacher and student tokens are ready."
  echo
fi

echo "[2/8] Create assignment..."
if [[ -n "${TEACHER_TOKEN}" ]]; then
  curl -s -X POST "${BASE_URL}/v1/assignments" \
    -H "$(build_auth_header "${TEACHER_TOKEN}")" \
    -H "Content-Type: application/json" \
    -d "{
      \"action\": \"CREATE_ASSIGNMENT\",
      \"timestamp\": $(date +%s),
      \"payload\": {
        \"teacher_id\": \"${TEACHER_ID}\",
        \"assignment_id\": \"${ASSIGNMENT_ID}\",
        \"title\": \"Smoke Test Assignment\",
        \"description\": \"This assignment is created by smoke_test.sh\",
        \"deadline\": \"${SMOKE_DEADLINE}\"
      }
    }"
else
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
        \"deadline\": \"${SMOKE_DEADLINE}\"
      }
    }"
fi
echo
echo

echo "[3/8] List open assignments..."
if [[ -n "${STUDENT_TOKEN}" ]]; then
  curl -s "${BASE_URL}/v1/assignments/open" -H "$(build_auth_header "${STUDENT_TOKEN}")"
else
  curl -s "${BASE_URL}/v1/assignments/open"
fi
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
if [[ -n "${STUDENT_TOKEN}" ]]; then
  SUBMIT_RESPONSE=$(curl -s -X POST "${BASE_URL}/v1/submissions" \
    -H "$(build_auth_header "${STUDENT_TOKEN}")" \
    -F "metadata={\"action\":\"SUBMIT\",\"timestamp\":$(date +%s),\"payload\":{\"student_id\":\"${STUDENT_ID}\",\"assignment_id\":\"${ASSIGNMENT_ID}\",\"md5\":\"${MD5}\"}}" \
    -F "file=@${PACKAGE_PATH}")
else
  SUBMIT_RESPONSE=$(curl -s -X POST "${BASE_URL}/v1/submissions" \
    -F "metadata={\"action\":\"SUBMIT\",\"timestamp\":$(date +%s),\"payload\":{\"student_id\":\"${STUDENT_ID}\",\"assignment_id\":\"${ASSIGNMENT_ID}\",\"md5\":\"${MD5}\"}}" \
    -F "file=@${PACKAGE_PATH}")
fi

echo "${SUBMIT_RESPONSE}"
echo

SUBMISSION_ID=$(python3 - <<PY
import json
data = json.loads('''${SUBMIT_RESPONSE}''')
if "payload" not in data:
    raise SystemExit(f"submit failed: {data}")
print(data["payload"]["submission_id"])
PY
)

echo "submission_id: ${SUBMISSION_ID}"
echo

echo "[6/8] List pending submissions..."
if [[ -n "${TEACHER_TOKEN}" ]]; then
  curl -s "${BASE_URL}/v1/submissions/pending" -H "$(build_auth_header "${TEACHER_TOKEN}")"
else
  curl -s "${BASE_URL}/v1/submissions/pending"
fi
echo
echo

echo "[7/8] Grade submission..."
if [[ -n "${TEACHER_TOKEN}" ]]; then
  curl -s -X POST "${BASE_URL}/v1/submissions/grade" \
  -H "$(build_auth_header "${TEACHER_TOKEN}")" \
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
else
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
fi
echo
echo

echo "[8/8] Query feedback..."
if [[ -n "${STUDENT_TOKEN}" ]]; then
  curl -s "${BASE_URL}/v1/feedback/${STUDENT_ID}" -H "$(build_auth_header "${STUDENT_TOKEN}")"
else
  curl -s "${BASE_URL}/v1/feedback/${STUDENT_ID}"
fi
echo
echo

echo "========== Smoke Test Finished =========="
