#!/bin/bash
# scripts/setup-test-db.sh
# 
# Purpose: Idempotently ensure the test database is running and ready.
# Rationale: Docker startup can be slow, especially when seeding data.
# This script avoids arbitrary 'sleep' commands by polling the Docker health status.

# Start the database in the background
docker compose up -d

echo "Checking if PostgreSQL is healthy..."
MAX_RETRIES=30
RETRIES=0

# Polling loop: Wait for the container's healthcheck to pass.
# The healthcheck is defined in docker-compose.yml and runs 'pg_isready'.
until [ "$(docker inspect -f '{{.State.Health.Status}}' mcp-test-postgres 2>/dev/null)" == "healthy" ]; do
    if [ $RETRIES -eq $MAX_RETRIES ]; then
        echo "Error: Timed out waiting for database to become healthy"
        exit 1
    fi
    echo "Postgres status: $(docker inspect -f '{{.State.Health.Status}}' mcp-test-postgres 2>/dev/null)... waiting..."
    sleep 1
    RETRIES=$((RETRIES+1))
done

echo "PostgreSQL is healthy and ready!"
exit 0
