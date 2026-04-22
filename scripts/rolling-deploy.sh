#!/bin/bash
set -e

HEALTH_CHECK_TIMEOUT=60
HEALTH_CHECK_INTERVAL=2

echo "Starting rolling deployment..."

docker compose pull

for service in api worker frontend; do
  echo "Deploying $service..."

  docker compose up -d --no-deps $service

  echo "Waiting for $service to become healthy (max ${HEALTH_CHECK_TIMEOUT}s)..."
  elapsed=0
  while [ $elapsed -lt $HEALTH_CHECK_TIMEOUT ]; do
    if docker compose ps $service | grep -q "healthy"; then
      echo "$service is healthy"
      break
    fi
    sleep $HEALTH_CHECK_INTERVAL
    elapsed=$((elapsed + HEALTH_CHECK_INTERVAL))
  done

  if [ $elapsed -ge $HEALTH_CHECK_TIMEOUT ]; then
    echo "ERROR: $service did not become healthy within ${HEALTH_CHECK_TIMEOUT}s"
    echo "Rolling back..."
    docker compose down
    exit 1
  fi
done

echo "Deployment completed successfully"
