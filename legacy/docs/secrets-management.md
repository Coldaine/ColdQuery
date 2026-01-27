# Secret Management for VS Code MCP

The [.vscode/mcp.json](.vscode/mcp.json) configuration uses `${env:PGPASSWORD}` to fetch the PostgreSQL password from your shell environment at runtime. This avoids committing credentials to version control.

## Quick Start (Local Development)

For local testing, export the password directly:

```bash
export PGPASSWORD="mcp"
code .
```

## Production: Bitwarden Secrets Manager

For secure secret management, use the Bitwarden Secrets Manager CLI:

### 1. Install BWS CLI

```bash
# Download from https://github.com/bitwarden/sdk/releases
# Or install via npm:
npm install -g @bitwarden/sdk-cli
```

### 2. Create a Secret in Bitwarden

1. Go to [Bitwarden Secrets Manager](https://vault.bitwarden.com/)
2. Create a new secret with key `postgres-password` and your database password as the value
3. Create a machine account and grant it access to the secret
4. Generate an access token for the machine account

### 3. Set Environment Variables

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export BWS_ACCESS_TOKEN="your-bitwarden-access-token"
export COLDQUERY_PG_SECRET_ID="postgres-password"  # or your secret ID
```

### 4. Load Secrets and Launch VS Code

```bash
source scripts/load-secrets.sh && code .
```

The script fetches the password from Bitwarden and exports `PGPASSWORD` so VS Code can inject it into the MCP server environment.

## Alternative: PostgreSQL .pgpass File

You can also use the standard PostgreSQL password file:

1. Create `~/.pgpass`:
   ```
   localhost:5433:mcp_test:mcp:your-password
   ```

2. Set permissions:
   ```bash
   chmod 600 ~/.pgpass
   ```

3. Remove `PGPASSWORD` from [.vscode/mcp.json](.vscode/mcp.json) entirely (libpq will auto-detect `.pgpass`)

## CI/CD Integration

For automated workflows, set `PGPASSWORD` in your CI environment variables or use a secrets management service integrated with your pipeline.
