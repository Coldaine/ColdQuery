# pgEdge Postgres MCP Server — Setup Playbook

> **Purpose**: Replace ColdQuery with pgEdge Postgres MCP Server as a project-scoped
> MCP server for Claude Code and VS Code (Gemini). Multi-database, minimal config.
>
> **Repo**: https://github.com/pgEdge/pgedge-postgres-mcp
> **Version**: v1.0.0-beta3a (Go binary, pre-built for linux/arm64)

---

## Table of Contents

1. [Install the Binary](#1-install-the-binary)
2. [Create the Config File](#2-create-the-config-file)
3. [Configure Multiple Databases](#3-configure-multiple-databases)
4. [Disable Tools You Don't Need](#4-disable-tools-you-dont-need)
5. [Enable Multi-Database Switching](#5-enable-multi-database-switching)
6. [Where Secrets Go](#6-where-secrets-go)
7. [Register as MCP Server in Claude Code](#7-register-as-mcp-server-in-claude-code)
8. [Register as MCP Server in VS Code (Gemini)](#8-register-as-mcp-server-in-vs-code-gemini)
9. [Test It](#9-test-it)
10. [Tool Reference](#10-tool-reference)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Install the Binary

pgEdge publishes pre-built binaries. No Go toolchain needed.

```bash
# Pick a location for the binary
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

# Detect platform
OS=$(uname -s | tr '[:upper:]' '[:lower:]')     # linux or darwin
ARCH=$(uname -m)                                  # x86_64 or aarch64/arm64

# Normalize arch name for the download URL
case "$ARCH" in
    aarch64|arm64) ARCH_LABEL="arm64" ;;
    x86_64|amd64)  ARCH_LABEL="x86_64" ;;
    *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Download latest release
VERSION="v1.0.0-beta3a"
BINARY_NAME="pgedge-postgres-mcp_${OS}_${ARCH_LABEL}"
DOWNLOAD_URL="https://github.com/pgEdge/pgedge-postgres-mcp/releases/download/${VERSION}/${BINARY_NAME}"

curl -fSL "$DOWNLOAD_URL" -o "$INSTALL_DIR/pgedge-postgres-mcp"
chmod +x "$INSTALL_DIR/pgedge-postgres-mcp"

# Verify it runs
"$INSTALL_DIR/pgedge-postgres-mcp" --help
```

> **Raspberry Pi (ARM64)**: This works natively. The `linux_arm64` binary is published
> with each release. No Docker, no cross-compilation, no QEMU.

> **Alternative — Build from source** (only if you want bleeding edge):
> ```bash
> git clone https://github.com/pgEdge/pgedge-postgres-mcp.git
> cd pgedge-postgres-mcp
> make build
> # Binary at ./bin/pgedge-postgres-mcp
> ```

---

## 2. Create the Config File

Create a YAML config file. This is the **single source of truth** for databases,
tools, and features. Put it wherever makes sense — your home directory, the project
root, or `/etc/pgedge/`.

```bash
mkdir -p ~/.config/pgedge
touch ~/.config/pgedge/postgres-mcp.yaml
chmod 600 ~/.config/pgedge/postgres-mcp.yaml
```

Minimal config for a single database (stdio mode, no HTTP, no auth, no embeddings):

```yaml
# ~/.config/pgedge/postgres-mcp.yaml

databases:
    - name: "mydb"
      host: "localhost"
      port: 5432
      database: "mydb"
      user: "postgres"
      password: "your-password-here"
      sslmode: "prefer"
      allow_writes: false           # Read-only by default. Set true if needed.
      allow_llm_switching: true

# Disable features you don't need
embedding:
    enabled: false

llm:
    enabled: false

knowledgebase:
    enabled: false
```

That's it. This is enough to get started.

---

## 3. Configure Multiple Databases

Add more entries to the `databases` array. Each gets a unique `name`:

```yaml
databases:
    # ── Your main app database ──────────────────────────────────
    - name: "app-prod"
      host: "localhost"               # or Docker network hostname
      port: 5432
      database: "myapp"
      user: "readonly_user"
      password: "secret1"
      sslmode: "prefer"
      allow_writes: false
      allow_llm_switching: true

    # ── Analytics / warehouse ───────────────────────────────────
    - name: "analytics"
      host: "localhost"
      port: 5433                      # Different port if multiple PG containers
      database: "analytics"
      user: "analyst"
      password: "secret2"
      sslmode: "prefer"
      allow_writes: false
      allow_llm_switching: true

    # ── Staging (writes allowed) ────────────────────────────────
    - name: "app-staging"
      host: "localhost"
      port: 5434
      database: "myapp_staging"
      user: "admin"
      password: "secret3"
      sslmode: "prefer"
      allow_writes: true              # ⚠️ LLM can INSERT/UPDATE/DELETE
      allow_llm_switching: true

    # ── Sensitive DB (no LLM switching) ─────────────────────────
    - name: "secrets-db"
      host: "localhost"
      port: 5435
      database: "secrets"
      user: "readonly"
      password: "secret4"
      sslmode: "require"
      allow_writes: false
      allow_llm_switching: false      # LLM cannot switch to this DB on its own
```

> **Docker networking**: If your PostgreSQL containers are on the same Docker network,
> use the container name as the host (e.g., `host: "postgres-analytics"`). If you're
> running pgEdge as a native binary (not in Docker), use `localhost` with the
> published port.

### Alternative: Environment Variables for Multi-DB

If you prefer env vars over YAML (useful in Docker Compose):

```bash
# Database 1
PGEDGE_DB_1_NAME=app-prod
PGEDGE_DB_1_HOST=localhost
PGEDGE_DB_1_PORT=5432
PGEDGE_DB_1_DATABASE=myapp
PGEDGE_DB_1_USER=readonly_user
PGEDGE_DB_1_PASSWORD=secret1
PGEDGE_DB_1_SSLMODE=prefer
PGEDGE_DB_1_ALLOW_WRITES=false

# Database 2
PGEDGE_DB_2_NAME=analytics
PGEDGE_DB_2_HOST=localhost
PGEDGE_DB_2_PORT=5433
PGEDGE_DB_2_DATABASE=analytics
PGEDGE_DB_2_USER=analyst
PGEDGE_DB_2_PASSWORD=secret2
PGEDGE_DB_2_ALLOW_WRITES=false

# Enable LLM switching between databases
PGEDGE_LLM_DB_SWITCHING=true
```

---

## 4. Disable Tools You Don't Need

This is how you avoid tool bloat. The `builtins` section controls which tools the
LLM sees. **Disable everything you won't use:**

```yaml
builtins:
    tools:
        # ── KEEP THESE (core functionality) ─────────────────────
        query_database: true            # Run SQL queries
        get_schema_info: true           # Explore tables, columns, indexes
        execute_explain: true           # EXPLAIN ANALYZE for performance
        count_rows: true                # Quick row counts

        # ── DISABLE THESE (require extra infra) ─────────────────
        similarity_search: false        # Needs pgvector + embedding provider
        generate_embedding: false       # Needs OpenAI/Voyage/Ollama API key
        search_knowledgebase: false     # Needs pre-built KB SQLite database

        # ── ENABLE IF MULTI-DB (see section 5) ──────────────────
        llm_connection_selection: false  # list + select database tools
    resources:
        system_info: true
    prompts:
        explore_database: true
        setup_semantic_search: false
        diagnose_query_issue: true
        design_schema: true
```

**With this config, the LLM sees only 4 tools**: `query_database`, `get_schema_info`,
`execute_explain`, `count_rows`. Plus `read_resource` which is always on (harmless).

That's 5 tools total. Leaner than ColdQuery's 5 tools with 25 actions.

---

## 5. Enable Multi-Database Switching

If you have multiple databases configured and want the LLM to switch between them:

```yaml
builtins:
    tools:
        llm_connection_selection: true   # Adds 2 tools: list + select database
```

This exposes:
- `list_database_connections` — LLM can see available databases
- `select_database_connection` — LLM can switch active database

To prevent switching to a specific database, set `allow_llm_switching: false` on
that database entry.

**Total tools with multi-DB**: 7 (4 core + 2 switching + read_resource).

---

## 6. Where Secrets Go

### Option A: Passwords in YAML (simplest, local-only)

Put passwords directly in `postgres-mcp.yaml`. Make sure the file is `chmod 600`:

```yaml
databases:
    - name: "mydb"
      password: "my-secret-password"
```

### Option B: `.pgpass` file (standard PostgreSQL approach)

Create `~/.pgpass` with mode 0600:

```
# hostname:port:database:username:password
localhost:5432:myapp:readonly_user:secret1
localhost:5433:analytics:analyst:secret2
localhost:5434:myapp_staging:admin:secret3
```

```bash
chmod 600 ~/.pgpass
```

Then **omit** the `password` field in your YAML — pgx will pick it up automatically.

### Option C: Environment variables (for Docker/CI)

```bash
# Single database
PGEDGE_DB_PASSWORD=secret

# Multiple databases
PGEDGE_DB_1_PASSWORD=secret1
PGEDGE_DB_2_PASSWORD=secret2
```

### Option D: MCP config env block (per-project, Claude Code / VS Code)

Passwords can live in the `.mcp.json` / `.vscode/mcp.json` env block. These files
are local to the project and should be in `.gitignore`:

```json
{
  "mcpServers": {
    "pgedge": {
      "command": "/home/user/.local/bin/pgedge-postgres-mcp",
      "args": ["-config", "/home/user/.config/pgedge/postgres-mcp.yaml"],
      "env": {
        "PGEDGE_DB_1_PASSWORD": "secret1",
        "PGEDGE_DB_2_PASSWORD": "secret2"
      }
    }
  }
}
```

### API Keys (only if using embeddings/LLM proxy)

| Secret | Env Var | File-based alternative |
|--------|---------|----------------------|
| OpenAI API key | `OPENAI_API_KEY` | `~/.openai-api-key` |
| Voyage API key | `VOYAGE_API_KEY` | `~/.voyage-api-key` |
| Anthropic API key | `ANTHROPIC_API_KEY` | `~/.anthropic-api-key` |

You probably don't need any of these if you disabled embeddings and LLM proxy.

### What to .gitignore

```gitignore
# pgEdge MCP secrets
.mcp.json
.vscode/mcp.json
postgres-mcp.yaml
postgres-mcp-tokens.yaml
postgres-mcp-users.yaml
postgres-mcp.secret
.pgpass
```

---

## 7. Register as MCP Server in Claude Code

Create `.mcp.json` in the **project root** (project-scoped):

```json
{
  "mcpServers": {
    "postgres": {
      "command": "/home/user/.local/bin/pgedge-postgres-mcp",
      "args": [
        "-config",
        "/home/user/.config/pgedge/postgres-mcp.yaml"
      ]
    }
  }
}
```

> **IMPORTANT**: Use absolute paths for both the binary and config file.
> Claude Code launches the binary as a subprocess using stdio transport.
> No HTTP server needed.

**With env-var-based secrets** (passwords not in YAML):

```json
{
  "mcpServers": {
    "postgres": {
      "command": "/home/user/.local/bin/pgedge-postgres-mcp",
      "args": [
        "-config",
        "/home/user/.config/pgedge/postgres-mcp.yaml"
      ],
      "env": {
        "PGEDGE_DB_1_PASSWORD": "secret1",
        "PGEDGE_DB_2_PASSWORD": "secret2"
      }
    }
  }
}
```

**Minimal setup without a YAML file** (single database, all env vars):

```json
{
  "mcpServers": {
    "postgres": {
      "command": "/home/user/.local/bin/pgedge-postgres-mcp",
      "env": {
        "PGHOST": "localhost",
        "PGPORT": "5432",
        "PGDATABASE": "myapp",
        "PGUSER": "postgres",
        "PGPASSWORD": "secret"
      }
    }
  }
}
```

Add `.mcp.json` to `.gitignore` if it contains secrets.

### Verify in Claude Code

After creating `.mcp.json`, restart Claude Code or start a new session. Run:

```
/mcp
```

You should see `postgres` listed with the tools you enabled.

---

## 8. Register as MCP Server in VS Code (Gemini)

Create `.vscode/mcp.json` in the **project root**:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "/home/user/.local/bin/pgedge-postgres-mcp",
      "args": [
        "-config",
        "/home/user/.config/pgedge/postgres-mcp.yaml"
      ]
    }
  }
}
```

> Same format as Claude Code. Both use stdio transport with the same binary.

**Alternative — VS Code `settings.json`** (user-scoped, applies to all projects):

Add to your VS Code `settings.json` (`Cmd/Ctrl+Shift+P` → "Preferences: Open User Settings (JSON)"):

```json
{
  "mcp": {
    "servers": {
      "postgres": {
        "command": "/home/user/.local/bin/pgedge-postgres-mcp",
        "args": [
          "-config",
          "/home/user/.config/pgedge/postgres-mcp.yaml"
        ]
      }
    }
  }
}
```

Add `.vscode/mcp.json` to `.gitignore` if it contains secrets.

---

## 9. Test It

### Quick smoke test (command line)

```bash
# Test that the binary can connect to your database
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | \
    /home/user/.local/bin/pgedge-postgres-mcp \
    -config /home/user/.config/pgedge/postgres-mcp.yaml
```

You should see JSON output listing all enabled tools.

### Test a query

```bash
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"query_database","arguments":{"query":"SELECT version()"}}}' | \
    /home/user/.local/bin/pgedge-postgres-mcp \
    -config /home/user/.config/pgedge/postgres-mcp.yaml
```

### Test in Claude Code

Start a Claude Code session in a project with `.mcp.json` configured:

```
Ask: "What tables are in my database?"
```

The LLM should invoke `get_schema_info` and return your schema.

### Debug mode

If something isn't working:

```bash
/home/user/.local/bin/pgedge-postgres-mcp \
    -config /home/user/.config/pgedge/postgres-mcp.yaml \
    -debug \
    -trace-file /tmp/pgedge-trace.log
```

Then check `/tmp/pgedge-trace.log` for JSON-RPC request/response pairs.

---

## 10. Tool Reference

With the recommended config (section 4), these are the tools the LLM sees:

### `query_database`
Run SQL queries. Read-only by default unless `allow_writes: true` on the database.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | yes | — | SQL query to execute |
| `limit` | int | no | 100 | Max rows (max 1000) |
| `offset` | int | no | 0 | Row offset for pagination |

### `get_schema_info`
Explore database schema — tables, columns, types, PKs, FKs, indexes.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `schema_name` | string | no | — | Filter to specific schema |
| `table_name` | string | no | — | Filter to specific table (requires schema_name) |
| `vector_tables_only` | bool | no | false | Only show tables with vector columns |
| `compact` | bool | no | false | Compact output format |

### `execute_explain`
Run EXPLAIN ANALYZE with automatic performance analysis.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | yes | — | SELECT query to explain |
| `analyze` | bool | no | true | Run ANALYZE (actual execution) |
| `buffers` | bool | no | true | Include buffer usage |
| `format` | string | no | "text" | Output format: "text" or "json" |

### `count_rows`
Fast row counting with optional filter.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `table` | string | yes | — | Table name |
| `schema` | string | no | "public" | Schema name |
| `where` | string | no | — | WHERE clause filter |

### `list_database_connections` (if `llm_connection_selection: true`)
Lists available databases. No parameters.

### `select_database_connection` (if `llm_connection_selection: true`)
Switch active database.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Database name to switch to |

---

## 11. Troubleshooting

### "Connection refused" / "no such host"

- Check that your PostgreSQL container is running: `docker ps`
- Check the host/port in your config matches the published Docker port
- If running pgEdge as a native binary (not in Docker), use `localhost` + published port
- If running pgEdge inside Docker, use the Docker network hostname

### "SSL is not enabled on the server"

Set `sslmode: "disable"` for local Docker PostgreSQL instances that don't have SSL:

```yaml
databases:
    - name: "local"
      sslmode: "disable"
```

### Tools not showing up in Claude Code

- Check `.mcp.json` is in the project root
- Restart Claude Code (or run `/mcp` to check)
- Make sure the binary path is absolute
- Make sure the config path is absolute
- Test the binary manually (section 9)

### "permission denied" on binary

```bash
chmod +x /home/user/.local/bin/pgedge-postgres-mcp
```

### LLM tries to write but gets blocked

Either:
- Set `allow_writes: true` on the database entry, OR
- Tell the LLM the database is read-only (it should adapt)

### LLM can't switch databases

- Enable `llm_connection_selection: true` in `builtins.tools`
- Make sure target database has `allow_llm_switching: true`

### Want to see what's happening

```bash
# Add to your config:
# trace_file: "/tmp/pgedge-trace.log"

# Or pass as CLI flag in .mcp.json:
"args": ["-config", "/path/to/config.yaml", "-debug", "-trace-file", "/tmp/pgedge-trace.log"]
```

---

## Complete Example: Full Config File

Here's a complete, copy-paste-ready config for a typical multi-database setup
with bloat-free tool selection:

```yaml
# ~/.config/pgedge/postgres-mcp.yaml
#
# pgEdge Postgres MCP Server configuration
# Docs: https://github.com/pgEdge/pgedge-postgres-mcp

# ── Databases ───────────────────────────────────────────────────
databases:
    - name: "production"
      host: "localhost"
      port: 5432
      database: "myapp"
      user: "readonly"
      password: ""                      # Use .pgpass or env var
      sslmode: "prefer"
      allow_writes: false
      allow_llm_switching: true

    - name: "staging"
      host: "localhost"
      port: 5433
      database: "myapp_staging"
      user: "admin"
      password: ""
      sslmode: "prefer"
      allow_writes: true
      allow_llm_switching: true

# ── Tools (lean selection) ──────────────────────────────────────
builtins:
    tools:
        query_database: true
        get_schema_info: true
        execute_explain: true
        count_rows: true
        similarity_search: false
        generate_embedding: false
        search_knowledgebase: false
        llm_connection_selection: true   # Enable since we have multiple DBs
    resources:
        system_info: true
    prompts:
        explore_database: true
        setup_semantic_search: false
        diagnose_query_issue: true
        design_schema: true

# ── Disabled features ───────────────────────────────────────────
embedding:
    enabled: false

llm:
    enabled: false

knowledgebase:
    enabled: false
```

With this config: **6 active tools** (query, schema, explain, count, list DBs, select DB)
plus the always-on `read_resource`. Clean and focused.
