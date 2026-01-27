#!/bin/bash
# scripts/run-deployment-tests.sh
#
# Run tests against real remote PostgreSQL instances (deployment tests).
# These tests verify the MCP server works in production-like environments.
#
# Usage:
#   ./scripts/run-deployment-tests.sh --host 10.0.0.1 --password secret
#   ./scripts/run-deployment-tests.sh --help

set -e

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Run deployment tests against a remote PostgreSQL instance.

Required:
  --host HOST          PostgreSQL host (or set DEPLOY_TEST_HOST)
  --password PASSWORD  PostgreSQL password (or set DEPLOY_TEST_PASSWORD)

Optional:
  --port PORT          PostgreSQL port (default: 5432)
  --user USER          PostgreSQL user (default: mcp_test)
  --database DATABASE  PostgreSQL database (default: mcp_test)
  --name NAME          Connection name for test output (default: remote-postgres)
  --help               Show this help message

Environment variables:
  DEPLOY_TEST_HOST      PostgreSQL host
  DEPLOY_TEST_PORT      PostgreSQL port
  DEPLOY_TEST_USER      PostgreSQL user
  DEPLOY_TEST_PASSWORD  PostgreSQL password
  DEPLOY_TEST_DATABASE  PostgreSQL database
  DEPLOY_TEST_NAME      Connection name for test output

Examples:
  $(basename "$0") --host 192.168.1.100 --password mypassword
  $(basename "$0") --host db.example.com --port 5433 --user admin --password secret
  DEPLOY_TEST_HOST=localhost DEPLOY_TEST_PASSWORD=test $(basename "$0")
EOF
}

# Default configuration (only for non-sensitive values)
DEPLOY_TEST_PORT="${DEPLOY_TEST_PORT:-5432}"
DEPLOY_TEST_USER="${DEPLOY_TEST_USER:-mcp_test}"
DEPLOY_TEST_DATABASE="${DEPLOY_TEST_DATABASE:-mcp_test}"
DEPLOY_TEST_NAME="${DEPLOY_TEST_NAME:-remote-postgres}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --host)
            DEPLOY_TEST_HOST="$2"
            shift 2
            ;;
        --port)
            DEPLOY_TEST_PORT="$2"
            shift 2
            ;;
        --user)
            DEPLOY_TEST_USER="$2"
            shift 2
            ;;
        --password)
            DEPLOY_TEST_PASSWORD="$2"
            shift 2
            ;;
        --database)
            DEPLOY_TEST_DATABASE="$2"
            shift 2
            ;;
        --name)
            DEPLOY_TEST_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required variables
missing=()
if [[ -z "$DEPLOY_TEST_HOST" ]]; then
    missing+=("DEPLOY_TEST_HOST (use --host or set env var)")
fi
if [[ -z "$DEPLOY_TEST_PASSWORD" ]]; then
    missing+=("DEPLOY_TEST_PASSWORD (use --password or set env var)")
fi

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "ERROR: Missing required configuration:"
    for var in "${missing[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Use --help for usage information"
    exit 1
fi

echo "============================================"
echo "Deployment Tests"
echo "============================================"
echo "Host:     $DEPLOY_TEST_HOST"
echo "Port:     $DEPLOY_TEST_PORT"
echo "User:     $DEPLOY_TEST_USER"
echo "Database: $DEPLOY_TEST_DATABASE"
echo "Name:     $DEPLOY_TEST_NAME"
echo "============================================"

# Check connectivity first
echo "Checking connectivity..."
if command -v nc >/dev/null 2>&1; then
    if ! nc -z -w5 "$DEPLOY_TEST_HOST" "$DEPLOY_TEST_PORT" 2>/dev/null; then
        echo "ERROR: Cannot connect to $DEPLOY_TEST_HOST:$DEPLOY_TEST_PORT"
        echo "Make sure the host is reachable (Tailscale connected?)"
        exit 1
    fi
    echo "Connection OK"
else
    echo "WARNING: 'nc' not found; skipping connectivity check"
    echo "Ensure $DEPLOY_TEST_HOST:$DEPLOY_TEST_PORT is reachable"
fi
echo ""

# Export environment variables for tests
export RUN_DEPLOYMENT_TESTS=true
export DEPLOY_TEST_HOST
export DEPLOY_TEST_PORT
export DEPLOY_TEST_USER
export DEPLOY_TEST_PASSWORD
export DEPLOY_TEST_DATABASE
export DEPLOY_TEST_NAME

# Run only deployment tests
echo "Running deployment tests..."
npx vitest run packages/core/test/deployment/

echo ""
echo "============================================"
echo "Deployment tests completed!"
echo "============================================"
