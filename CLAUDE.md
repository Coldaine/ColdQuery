# ColdQuery

Secure, stateful PostgreSQL MCP server built with FastMCP 3.0 (Python).

## Critical Gotchas

### 1. App vs Server Split (IMPORTANT)

**Always import `mcp` from `coldquery.app`, never from `coldquery.server`.**

```python
# CORRECT
from coldquery.app import mcp

# WRONG - causes duplicate FastMCP instances
from coldquery.server import mcp
```

**Why?** Circular imports create two `mcp` instances. Tools register with one, HTTP serves from the other (empty). This bug cost us days to debug - see `docs/reports/2026-02-01-deployment-investigation.md`.

### 2. Default-Deny Write Policy

All write operations require explicit authorization:
- `session_id` (transaction context), OR
- `autocommit=true` (single statement)

Without either, writes are blocked. This is intentional. Use `require_write_access()` in handlers.

### 3. SQL Identifier Sanitization

Never interpolate user input into SQL identifiers. Always use:
```python
from coldquery.security.identifiers import sanitize_identifier, sanitize_table_name
```

### 4. Ruff B008 Ignore

The `B008` rule (function call in default argument) is ignored because FastMCP's dependency injection pattern requires `CurrentActionContext()` as a default:
```python
async def my_tool(context: ActionContext = CurrentActionContext()):  # This is correct
```

## Documentation Index

| Doc | Purpose |
|-----|---------|
| `STATUS.md` | Current state, what's done, what's blocked |
| `TODO.md` | Task list and priorities |
| `CHANGELOG.md` | Version history ([Keep a Changelog](https://keepachangelog.com/) format) |
| `docs/DEPLOYMENT.md` | Production deployment (Pi, Tailscale, Docker) |
| `docs/DEVELOPMENT.md` | Local dev setup |
| `docs/fastmcp-api-patterns.md` | FastMCP 3.0 patterns used here |
| `docs/reports/` | Investigation reports for past bugs |

## Key Architecture

| File | Role |
|------|------|
| `coldquery/app.py` | FastMCP instance creation (**single source of truth**) |
| `coldquery/server.py` | Entry point, imports tools to register them |
| `coldquery/tools/` | MCP tools (pg_query, pg_tx, pg_schema, pg_admin, pg_monitor) |
| `coldquery/actions/` | Action handlers grouped by tool |
| `coldquery/security/` | Identifier sanitization, access control, auth |

## Testing

- **Unit tests**: `tests/unit/` - Fast, mocked, no DB required
- **Integration tests**: `tests/integration/` - Real PostgreSQL, currently have known failures (see TODO.md)

Pre-commit hooks run ruff and tests automatically. Config in `pyproject.toml` and `.pre-commit-config.yaml`.

## Deployment

Server runs on Raspberry Pi at `https://coldquery-server.tail4c911d.ts.net/`.
- Port 19002 (internal)
- Tailscale Serve for HTTPS
- Docker Compose stack at `/opt/coldquery/`
