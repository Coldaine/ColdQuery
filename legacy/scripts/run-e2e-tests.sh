#!/bin/bash
# scripts/run-e2e-tests.sh
#
# Run End-to-End (E2E) tests against a running MCP server.
# This is the "True Deployment Test" that verifies the service over Streamable HTTP.
#
# Usage:
#   export MCP_TEST_URL="http://100.65.198.61:3000/mcp"
#   ./scripts/run-e2e-tests.sh

set -e

if [ -z "$MCP_TEST_URL" ]; then
    echo "Error: MCP_TEST_URL is not set."
    echo "Please set it to the Streamable HTTP endpoint of your deployed server."
    echo "Example: export MCP_TEST_URL='http://100.65.198.61:3000/mcp'"
    exit 1
fi

echo "============================================"
echo "E2E Acceptance Tests"
echo "============================================"
echo "Target: $MCP_TEST_URL"
echo "Transport: Streamable HTTP (MCP 2025-11-25 spec)"
echo "============================================"

# Run the E2E test suite
npx vitest run packages/core/test/e2e/remote-http.test.ts
