#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

echo "Starting Oscar API..."
python app/crawler-api/main.py &
API_PID=$!

cleanup() {
  echo "Stopping Oscar API (pid=${API_PID})"
  kill "${API_PID}" 2>/dev/null || true
}
trap cleanup EXIT

sleep 2

echo "Triggering crawl job..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/crawl/oscar \
  -H "Content-Type: application/json" -d '{}')
echo "POST /crawl/oscar response:"
echo "${JOB_RESPONSE}"

JOB_ID=$(printf '%s' "${JOB_RESPONSE}" | python -c 'import sys, json; print(json.load(sys.stdin)["job_id"])')

echo
echo "Polling /results/${JOB_ID} until status=completed..."

while true; do
  RESULT=$(curl -s "http://localhost:8000/results/${JOB_ID}")
  STATUS=$(printf '%s' "${RESULT}" | python -c 'import sys, json; print(json.load(sys.stdin)["status"])')

  echo
  echo "Current status: ${STATUS}"

  if [ "${STATUS}" = "completed" ] || [ "${STATUS}" = "failed" ]; then
    echo
    echo "Final /results/${JOB_ID} response:"
    curl -s "http://localhost:8000/results/${JOB_ID}"
    echo
    break
  fi

  sleep 3
done

