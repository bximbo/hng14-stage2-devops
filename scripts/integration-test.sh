#!/bin/bash
set -euo pipefail

TIMEOUT=${TIMEOUT:-60}
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

cleanup() {
  echo "=== docker compose logs ==="
  docker compose logs || true
  echo "=== Tearing down ==="
  docker compose down -v || true
}
trap cleanup EXIT

if [ ! -f .env ]; then
  cat > .env <<EOF
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=integration-$(date +%s)
API_URL=http://api:8000
PORT=3000
EOF
fi

echo "Starting services..."
docker compose up -d --wait --timeout "$TIMEOUT"

echo "Waiting for frontend health (timeout ${TIMEOUT}s)..."
elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  if curl -fs "${FRONTEND_URL}/health" >/dev/null; then
    echo "Frontend is healthy"
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done
if [ "$elapsed" -ge "$TIMEOUT" ]; then
  echo "ERROR: frontend did not become healthy within ${TIMEOUT}s"
  exit 1
fi

echo "Submitting job..."
JOB_ID=$(curl -fs -X POST "${FRONTEND_URL}/submit" | jq -r '.job_id')
if [ -z "$JOB_ID" ] || [ "$JOB_ID" = "null" ]; then
  echo "ERROR: failed to obtain job_id"
  exit 1
fi
echo "Submitted job: $JOB_ID"

echo "Polling job status (timeout ${TIMEOUT}s)..."
elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  STATUS=$(curl -fs "${FRONTEND_URL}/status/${JOB_ID}" | jq -r '.status')
  echo "  status=$STATUS"
  if [ "$STATUS" = "completed" ]; then
    echo "Integration test passed"
    exit 0
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

echo "ERROR: job did not complete within ${TIMEOUT}s"
exit 1
