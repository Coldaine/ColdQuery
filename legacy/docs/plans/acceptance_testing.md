# Acceptance Testing Plan

> See [Architecture](/docs/architecture.md) for the deployment model and design rationale.

## Purpose

Verify that the deployed MCP server works as a gateway for multiple coding environments to manage PostgreSQL.

This is **acceptance testing**: can the system do the job it was built for?
- Not integration testing (we don't spawn servers)
- Not smoke testing (we test real workflows, not just "is it up?")

## What We're Testing

The production deployment model:

```
┌──────────────────┐  ┌──────────────────┐
│ Test Runner      │  │ Other Clients    │
│ (vitest)         │  │ (Claude, Cursor) │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         └──────────┬──────────┘
                    │ Tailscale / HTTP
                    ▼
         ┌─────────────────────┐
         │ MCP Server (Pi)     │
         │ - Session routing   │
         │ - Connection pool   │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │ PostgreSQL (Pi)     │
         └─────────────────────┘
```

| Question | How We Answer It |
|----------|------------------|
| Can an agent create schemas? | DDL through `pg_schema` |
| Can an agent CRUD data? | Insert, read, update, delete through `pg_query` |
| Do transactions work? | Multi-step workflow with `pg_tx` |
| Does the server stay healthy? | `pg_monitor` checks |
| Do multiple clients work? | Session isolation tests |

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transport | Streamable HTTP | MCP 2025-11-25 spec, production deployment model |
| Session model | Stateful transport | Multiple concurrent clients need session isolation |
| Test isolation | Hybrid | Persistent `acceptance_test` schema + ephemeral tables per test |
| Security | Origin validation + Tailscale | DNS rebinding protection, network-level auth |

### Session Model

Two distinct session concepts:

| Layer | What It Tracks | Implementation |
|-------|----------------|----------------|
| **MCP Transport** | Client identity across HTTP requests | `Mcp-Session-Id` header, session routing Map |
| **PostgreSQL Transactions** | `BEGIN`...`COMMIT` state | `session_id` parameter from `pg_tx` |

The MCP server maintains a session Map to route requests from different clients to their respective transport instances. This enables:
- Multiple concurrent clients (Claude Code, Cursor, VS Code)
- Proper client isolation
- Server-initiated notifications (future)

## Test Isolation Strategy

**Hybrid approach:**
1. **Persistent schema**: `acceptance_test` schema created in `beforeAll`, dropped in `afterAll`
2. **Ephemeral tables**: Each test uses `test_${testId}` table names
3. **Defense in depth**: `afterEach` cleans up test tables, `afterAll` drops entire schema

## Test Suites

### Health
- Server health check via `pg_monitor`

### Schema Management
- List schemas
- Create and list tables
- Describe table columns

### CRUD Operations
- Full insert, read, update, delete cycle

### Transactions
- Rollback uncommitted changes
- Commit and persist changes

### Error Handling
- Invalid SQL syntax detection
- Non-existent table errors
- Safety check enforcement (require session_id or autocommit)

## Execution

### Prerequisites

1. MCP server deployed and running on Pi (see [Architecture](/docs/architecture.md))
2. Server accessible via Tailscale at `https://<your-hostname>.tailnet.ts.net/mcp`
3. PostgreSQL running locally on Pi

> **Note:** Replace `<your-hostname>` with your actual Tailscale machine name (run `tailscale status` to find it).

### Run Tests

```bash
# From dev machine (on same Tailnet)
# Replace <your-hostname> with your actual Tailscale machine name
export MCP_TEST_URL="https://<your-hostname>.tailnet.ts.net/mcp"
./scripts/run-e2e-tests.sh
```

### Server Startup (on Pi)

```bash
# Environment
export PGHOST=localhost
export PGUSER=postgres
export PGPASSWORD=<secret>
export PGDATABASE=postgres
export MCP_ALLOWED_ORIGINS="https://<your-hostname>.tailnet.ts.net"

# Start server
PORT=3000 node dist/packages/core/src/server.js --transport http

# Expose via Tailscale (separate terminal)
tailscale serve https:443 / http://127.0.0.1:3000
```

## Success Criteria

| Metric | Target |
|--------|--------|
| All workflows complete | 100% |
| No internal imports in test code | 0 imports from `src/` |
| Uses Streamable HTTP transport | Production transport |
| Tests actual deployed server | Not spawned |

## Future Improvements

- Concurrent client stress testing
- Session isolation verification (multiple clients simultaneously)
- Pagination for large result sets
- Performance benchmarks
- Bulk import tests (when file operations land)

## Open Questions

1. **Auth**: When we add API keys, how do tests get credentials?
2. **CI**: How to run acceptance tests in GitHub Actions against Pi?
