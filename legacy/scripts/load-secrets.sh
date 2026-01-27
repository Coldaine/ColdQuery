#!/usr/bin/env bash
# ColdQuery Secret Injection Helper
# 
# This script fetches secrets from Bitwarden Secrets Manager and exports them
# as environment variables for VS Code MCP integration.
#
# Usage:
#   1. Install Bitwarden Secrets CLI: https://bitwarden.com/help/secrets-manager-cli/
#   2. Set BWS_ACCESS_TOKEN in your shell environment
#   3. Source this script before launching VS Code:
#      source scripts/load-secrets.sh && code .

set -euo pipefail

# Determine if the script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    EXIT_CMD="return"
else
    EXIT_CMD="exit"
fi

# Check if bws is installed
if ! command -v bws &> /dev/null; then
    echo "Error: Bitwarden Secrets CLI (bws) not found. Install from:"
    echo "  https://github.com/bitwarden/sdk/releases"
    $EXIT_CMD 1
fi

# Check if BWS_ACCESS_TOKEN is set
if [[ -z "${BWS_ACCESS_TOKEN:-}" ]]; then
    echo "Error: BWS_ACCESS_TOKEN environment variable not set."
    echo "Create a machine account and access token at:"
    echo "  https://vault.bitwarden.com/"
    $EXIT_CMD 1
fi

# Fetch PostgreSQL password from Bitwarden Secrets Manager
# Replace <secret-id-or-key> with your actual secret ID/key
SECRET_ID="${COLDQUERY_PG_SECRET_ID:-}"

if [[ -z "$SECRET_ID" ]]; then
    echo "Warning: COLDQUERY_PG_SECRET_ID not set. Using example key 'postgres-password'."
    echo "Set COLDQUERY_PG_SECRET_ID to your actual Bitwarden secret ID."
    SECRET_ID="postgres-password"
fi

echo "Fetching PostgreSQL password from Bitwarden Secrets Manager..."
if ! PGPASSWORD=$(bws secret get "$SECRET_ID" 2>/dev/null | jq -r '.value'); then
    echo "Error: Failed to fetch secret '$SECRET_ID'. Check that:"
    echo "  1. The secret exists in your Bitwarden vault"
    echo "  2. Your machine account has permission to access it"
    echo "  3. BWS_ACCESS_TOKEN is valid"
    exit 1
fi

# Export for child processes (VS Code)
export PGPASSWORD

echo "✓ PGPASSWORD loaded from Bitwarden Secrets Manager"
echo "You can now launch VS Code with: code ."
