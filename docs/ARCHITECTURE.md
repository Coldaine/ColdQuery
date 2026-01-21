# ColdQuery Architecture

This document explains the system architecture and the **why** behind key design decisions.

## Overview

ColdQuery is an MCP (Model Context Protocol) server that exposes PostgreSQL operations as tools for AI assistants. It acts as a **gateway** between coding environments and PostgreSQL databases, deployed once and accessed from anywhere via Tailscale.

### Architecture Priorities

1. **Type safety** - Zod schemas validate all inputs at runtime
2. **Testability** - Executor abstraction enables mocking without a real database
3. **Extensibility** - Plugin pattern allows adding new tools without modifying core
4. **Security** - Default-Deny writes, identifier sanitization, network isolation

## System Architecture

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Claude Code      │  │ VS Code + Cline  │  │ Cursor           │
│ (laptop)         │  │ (desktop)        │  │ (wherever)       │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │ Tailscale (private network)
                               ▼
                    ┌─────────────────────────────────┐
                    │ Raspberry Pi                    │
                    │ ┌─────────────────────────────┐ │
                    │ │ ColdQuery                   │ │
                    │ │ - SSE / POST transport      │ │
                    │ │ - Session management        │ │
                    │ │ - Connection pooling        │ │
                    │ └──────────────┬──────────────┘ │
                    │                │ localhost      │
                    │ ┌──────────────▼──────────────┐ │
                    │ │ PostgreSQL                  │ │
                    │ │ - All databases             │ │
                    │ │ - All credentials here only │ │
                    │ └─────────────────────────────┘ │
                    └─────────────────────────────────┘
```

### Problem Statement

Managing PostgreSQL from multiple development environments is painful:

1. **Credential sprawl**: Every machine needs PostgreSQL credentials configured
2. **Connection management**: Each environment opens its own connections
3. **No unified interface**: Different tools, different CLIs
4. **Security surface**: Database credentials on every laptop and device

### Solution

A single MCP server that acts as a gateway to PostgreSQL, deployed once and accessed from anywhere via Tailscale.

## Design Principles

### 1. Single Point of Configuration

PostgreSQL credentials live in ONE place: the deployment target. No credentials on laptops, desktops, or other devices.

### 2. Network Security via Tailscale

Instead of exposing PostgreSQL to the network:
- MCP server binds to localhost or internal network
- Accessed via Tailscale (encrypted overlay network)
- Access controlled by Tailnet ACLs
- No public internet exposure

### 3. Multiple Clients, One Server

The MCP server handles concurrent connections from different coding environments through the HTTP/SSE transport layer.

### 4. Stateful Sessions for Client Isolation

Each coding environment gets its own MCP session:
- Session ID assigned at initialization
- Requests routed to correct session
- PostgreSQL transactions isolated per client
- Clean disconnect handling

---

## Executor Interface Pattern

**Location:** `shared/executor/`

### Why Two Executor Classes?

```
PostgresExecutor (pool-based) → for stateless queries
PostgresSessionExecutor (dedicated connection) → for transactions
```

**The problem:** PostgreSQL transactions require all statements to execute on the same connection. Connection pools return different connections per query.

**The solution:** `createSession()` returns a dedicated connection wrapper that maintains transaction state. The two classes share the same interface so callers don't need to know which they're using.

**Why `PostgresSessionExecutor.createSession()` returns `this`:**
This allows uniform code paths. A caller can always call `createSession()` regardless of whether they already have a session - if they do, they get the same session back.

### Why Wrap PoolClient?

The `pg` library's `PoolClient` has methods like `release()` that, if called incorrectly, cause connection leaks or double-release errors. The wrapper hides these footguns and exposes only safe operations.

---

## Tool/Action Separation

**Location:** `packages/core/src/tools/` and `packages/core/src/actions/`

### Why Separate Directories?

```
tools/     → MCP protocol layer (schema, registration)
actions/   → Business logic (SQL generation, execution)
```

**The problem:** MCP tools require specific response formats (`{ content: [...] }`). Mixing protocol concerns with SQL logic creates tight coupling.

**The solution:** Actions are pure functions that return domain objects. Tools wrap actions and handle MCP serialization. This allows:
- Testing actions without MCP infrastructure
- Reusing actions in non-MCP contexts (CLI, REST API)
- Changing MCP response format in one place

### Why Discriminated Unions for Actions?

Each tool (pg_query, pg_schema, etc.) bundles related actions via a discriminated union:

```typescript
z.discriminatedUnion("action", [ReadSchema, WriteSchema, ExplainSchema])
```

**Trade-off considered:** We could register each action as a separate MCP tool. But:
- Fewer tools = less cognitive load for the AI
- Related actions share context (e.g., all query operations together)
- Single tool with `action` field mirrors PostgreSQL's own command groupings

---

## Plugin Registration Pattern

**Location:** `packages/core/src/server.ts`

### Why Curried Handlers?

```typescript
handler: (context) => (params) => pgQueryHandler(params, context)
```

**The problem:** Tools need access to shared context (executor, logger) but tool definitions are static.

**The solution:** Currying delays context binding until registration time. The tool definition is a factory that produces a handler when given context. This enables:
- Defining tools without knowing context ahead of time
- Testing tools with mock context
- Potentially swapping context at runtime

### Why a Registration Loop?

```typescript
for (const tool of tools) {
    server.registerTool(tool.name, tool.config, async (params) => {...});
}
```

**Alternative considered:** Auto-discovery via filesystem scanning.

**Why we chose explicit registration:**
- All tools visible in one place (easier to audit)
- No magic - what you see is what runs
- Build errors if a tool import fails (vs runtime errors with auto-discovery)

---

## Multi-Client Gateway Pattern

**Location:** `packages/core/src/transports/http.ts`, `packages/core/src/server.ts`

### Why This Architecture?

To operate as a persistent network gateway, we must handle multiple independent clients (IDE windows, CLI instances) without mixing state or requiring multiple server processes.

### Key Implementation Details:

1. **SSE (Server-Sent Events) Transport:** Replaced the generic Streamable HTTP transport with explicit SSE `/mcp` endpoint and POST message routing. This is more robust for high-latency connections over Tailscale.

2. **Server Factory Pattern:** Instead of a single `McpServer` instance, we use `createMcpServer()` to instantiate a new server object **per incoming connection**.

3. **Session Map:** The HTTP layer maintains a `Map` of session IDs to active transport/server pairs, ensuring messages are routed to the correct isolated instance.

4. **Isolated Cleanup:** When an SSE connection drops, the associated `McpServer` and its transport are discarded, ensuring no resource leaks or stale sessions.

### Why Not stdio?

The stdio transport (MCP default) spawns a server per client:

```
❌ Each client needs PostgreSQL credentials
❌ Each client spawns its own process
❌ No central management
❌ Credential sprawl
```

### Why SSE / POST?

```
✓ One server, many clients (Gateway pattern)
✓ Credentials in one place
✓ Central connection pooling
✓ Tailscale handles encryption/auth
✓ Robust "handshake" via SSE endpoints
```

---

## Identifier Sanitization Strategy

**Location:** `shared/security/identifiers.ts`

### Security Model

DDL operations (CREATE TABLE, etc.) cannot use parameterized queries for identifiers - only for values. This creates SQL injection risk.

**Our approach:**
1. **Validate** - Reject identifiers that don't match PostgreSQL naming rules
2. **Escape** - Double any embedded quotes (`"` → `""`)
3. **Quote** - Always wrap in double quotes (`name` → `"name"`)

### Why Validate AND Escape?

**Validation catches mistakes:** A table name like `users; DROP TABLE users--` fails validation immediately with a clear error.

**Escaping handles edge cases:** A legitimate table name like `"weird""name"` (yes, PostgreSQL allows this) gets escaped correctly.

**Defense in depth:** Even if validation has a bug, escaping prevents injection. Even if escaping has a bug, validation blocks most attacks.

---

## Session Model

Two distinct session concepts:

| Layer | Purpose | Implementation |
|-------|---------|----------------|
| **MCP Transport** | Client identity across HTTP requests | `Mcp-Session-Id` header, managed by SDK |
| **PostgreSQL Transactions** | `BEGIN`...`COMMIT` state | `session_id` parameter from `pg_tx` |

These are independent:
- An MCP session can have multiple PostgreSQL transactions
- A PostgreSQL transaction belongs to one MCP session

---

## Logging to stderr

**Location:** `packages/core/src/logger.ts`

### Why All Logs Go to console.error?

MCP servers communicate with clients via **stdout**. Any stray `console.log()` corrupts the protocol stream.

**The rule:** stdout is sacred (protocol only), stderr is for humans (logs, errors).

This is why ESLint is configured to forbid `console.log` - it would break MCP communication.

---

## Read vs Write Handler Similarity

**Location:** `packages/core/src/actions/query/`

### Why Separate Handlers If They're Identical?

The `readHandler` and `writeHandler` have identical implementations:

```typescript
return await context.executor.execute(params.sql, params.params, options);
```

**Why keep them separate:**

1. **Semantic intent** - The AI knows whether it's reading or mutating
2. **Audit trail** - Logs can distinguish reads from writes
3. **Future extensibility** - We may add:
   - Read replicas (route reads to replicas, writes to primary)
   - Permission checks (allow reads but not writes)
   - Rate limiting (different limits for reads vs writes)

**We chose not to enforce** read-only at the handler level because:
- PostgreSQL functions can have side effects even in SELECT
- CTEs with mutations exist
- The database itself is the source of truth for permissions

---

## Timeout Implementation

**Location:** `shared/executor/postgres.ts`

### Why SET statement_timeout?

```typescript
await this.client.query(`SET statement_timeout = ${options.timeout_ms}`);
```

**Alternatives considered:**
- `pg` library's query timeout option - doesn't exist for all query types
- Connection-level timeout - affects all queries, not configurable per-query
- Application-level timeout with cancellation - complex, race conditions

**Why SET statement_timeout works:**
- PostgreSQL enforces it server-side (reliable)
- Session-local (doesn't affect other connections)
- Supported for all query types

**Why swallow reset errors:**
```typescript
.catch(() => { })
```

If the main query failed, we still try to reset the timeout. If the reset also fails (connection dead), there's nothing useful to do - the connection will be discarded anyway. Throwing here would mask the original error.

---

## DDL and Raw SQL

**Location:** `packages/core/src/actions/schema/ddl.ts`

### Why Allow Raw SQL in Definition?

```typescript
sql = `CREATE TABLE ${name} (${params.definition})`;
```

The `definition` parameter accepts raw SQL (e.g., `id SERIAL PRIMARY KEY, name TEXT`).

**Why not parse/validate it:**
- PostgreSQL column definitions are complex (constraints, defaults, generated columns)
- Parsing SQL is error-prone and always incomplete
- The AI needs full PostgreSQL syntax access

**Security assumption:** The AI is trusted to generate valid DDL. This tool is not meant for untrusted user input. If you need to accept user input, validate it before passing to this tool.

---

## Testing Architecture

The project uses a live PostgreSQL container for integration testing to ensure real-world compatibility and verify agent reliability features (like transactions).

### Database Lifecycle
- **Spin Up:** Managed by `scripts/setup-test-db.sh`. This script is idempotent; it starts the container if not running and waits for the Docker healthcheck to signal "healthy" (ensuring seeding is complete) before allowing tests to proceed.
- **Automated Teardown:** The `test:ci` script in `package.json` executes `docker compose down` after Vitest finishes, ensuring no orphaned containers are left running.
- **Rationale:** We use a healthcheck-based wait rather than fixed sleeps to provide the fastest possible startup time.

### Tools
- **Vitest:** Primary test runner.
- **Docker Compose:** Manages the isolated test environment and seeding.

---

## Security Layers

| Layer | Mechanism | What it protects against |
|-------|-----------|-------------------------|
| Network | Tailscale | Public internet, unauthorized networks |
| Transport | Origin validation | DNS rebinding attacks |
| Application | Default-Deny writes | Accidental data corruption |

See [SECURITY.md](SECURITY.md) for detailed security model documentation.

---

## Trade-offs

| Benefit | Cost |
|---------|------|
| Centralized credentials | Single point of failure (server) |
| One server to update | Must keep server running |
| Tailscale security | Requires Tailscale on all devices |
| Connection pooling | Slightly higher latency than local |

For a home lab / personal infrastructure setup, the benefits far outweigh the costs.

---

## Future Considerations

### Potential Additions

- **pg_vector** - Vector similarity search extension
- **Structured logging** - Consistent logging format across all handlers
- **Connection health checks** - Automatic reconnection on failure
- **API keys** - Multi-tenant or fine-grained access control

### Potential Improvements

- Consistent use of `sanitizeIdentifier()` in all DDL operations
- Read replica routing for high-traffic scenarios
- Rate limiting per client/operation type
