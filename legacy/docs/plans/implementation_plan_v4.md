# Implementation Plan v4: Secure Session Architecture with LLM Ergonomics

## 1. Overview

This plan defines the architecture for a **secure, stateful PostgreSQL MCP server** optimized for Agentic AI workflows. It addresses two core challenges:

1. **Silent Failures:** Agents forgetting `session_id` and accidentally running queries outside transactions
2. **Context Loss:** LLMs losing track of active sessions across conversation turns

### Design Philosophy

| Use Case | Solution | Complexity |
|----------|----------|------------|
| Simple CRUD operations | `autocommit: true` | Low |
| Known atomic batch operations | `pg_transaction` tool | Medium |
| Multi-step reasoning with decisions | Session-based with `session_id` | Advanced |

## 2. Key Decisions & Rationale

### A. "Default-Deny" Write Policy
- **Decision:** Write tools MUST receive either `session_id` OR `autocommit: true`. Missing both = error.
- **Rationale:** Eliminates silent failures where LLM intends transaction but forgets ID.

### B. Batch Transaction Tool
- **Decision:** Add `pg_transaction` tool for atomic multi-statement operations.
- **Rationale:** Covers 80% of transaction use cases without session management burden.

### C. Conditional Session Echo
- **Decision:** Tool responses include session info only when relevant (write operations or near-expiry sessions).
- **Rationale:** Reduces noise on read queries while still reminding LLMs about active transactions when it matters.

### D. Destructive Session Cleanup
- **Decision:** On session close, connection is destroyed (`client.release(true)`), not pooled.
- **Rationale:** Zero trust - no state leakage between sessions.

### E. Session Limits
- **Decision:** Enforce maximum concurrent sessions (default: 10).
- **Rationale:** Prevents runaway agents from exhausting connection pool.

### F. Write Detection Strategy
- **Decision:** Write operations are determined by **tool schema**, not SQL parsing.
- **Rationale:** SQL parsing is complex and error-prone (CTEs, `SELECT FOR UPDATE`, multi-statement injection). Instead:
  - `pg_query` with `action: 'write'` → write operation
  - `pg_schema` DDL operations → write operation
  - `pg_query` with `action: 'read'` → read operation (no guard)
- The tool schema is the source of truth, not the SQL content.

## 3. Architecture

### A. Session Management (`SessionManager`)

```typescript
interface Session {
    id: string;              // UUIDv4
    executor: QueryExecutor; // Dedicated PG Client
    lastActive: number;      // Timestamp for TTL
    timeoutTimer: NodeJS.Timeout;
}

interface SessionManagerConfig {
    ttlMs: number;           // Default: 30 minutes
    maxSessions: number;     // Default: 10
}
```

- **TTL:** 30 minutes (sliding window, resets on activity)
- **Max Sessions:** 10 concurrent (configurable)
- **Cleanup:** Auto-rollback and connection destruction on timeout

### B. Tool Hierarchy

```
pg_transaction (NEW)     → Atomic batch operations, no session management
    ↓
pg_tx                    → Session factory (begin/commit/rollback/list)
    ↓
pg_query / pg_schema     → Session-aware with autocommit fallback
```

### C. Conditional Response Envelope

Session info included only when relevant:

```typescript
interface ToolResponse {
    result: any;
    // Only included for write operations OR when session expires in < 5 minutes
    active_session?: {
        id: string;
        started_at: string;
        expires_in: string;
        hint: string;  // "Use session_id: 'abc' for subsequent queries"
    };
}

// Logic:
function shouldIncludeSessionInfo(session: Session, isWriteOp: boolean): boolean {
    if (!session) return false;
    const expiresInMinutes = (session.lastActive + TTL_MS - Date.now()) / 60000;
    return isWriteOp || expiresInMinutes < 5;
}
```

## 4. Tool Specifications

### A. `pg_transaction` (NEW - Batch Operations)

**Purpose:** Execute multiple statements atomically without session management.

```typescript
const TransactionSchema = z.object({
    action: z.literal("transaction"),
    operations: z.array(z.object({
        sql: z.string(),
        params: z.array(z.unknown()).optional(),
    })).min(1).describe("Array of SQL statements to execute atomically"),
});
```

**Behavior:**
1. Checkout connection from pool
2. BEGIN
3. Execute each operation in order
4. If all succeed: COMMIT
5. If any fails: ROLLBACK, return error with failed index
6. Release connection (destroy)

**Response:**
```json
{
    "status": "committed",
    "results": [
        { "rowCount": 1 },
        { "rows": [...] },
        { "rowCount": 1 }
    ]
}
```

### B. `pg_tx` (Session Factory)

Actions:
- `begin` → Creates session, returns `session_id`
- `commit` / `rollback` → Requires `session_id`, closes session
- `savepoint` / `release` → Requires `session_id`
- `list` → Returns all active sessions (for LLM discovery)

```typescript
const TxSchema = z.object({
    action: z.enum(["begin", "commit", "rollback", "savepoint", "release", "list"]),
    session_id: z.string().optional()
        .describe("Required for commit, rollback, savepoint, release. Use ID from 'begin'."),
    name: z.string().optional()
        .describe("Savepoint name (for savepoint/release actions)"),
});

// list response:
{
    "sessions": [
        { "id": "abc-123", "age": "2m 30s", "expires_in": "27m 30s" }
    ]
}
```

### C. `pg_query` / `pg_schema` / `pg_admin`

**Schema additions:**
```typescript
session_id: z.string().optional()
    .describe("Transaction session ID from pg_tx 'begin'. Required for transactional writes."),
autocommit: z.boolean().optional()
    .describe("Set to true for single-statement writes. Required if no session_id. Example: { sql: 'INSERT...', autocommit: true }"),
```

**Write handler logic:**
```typescript
// Only applied to write tools (pg_query:write, pg_schema:ddl, etc.)
if (!params.session_id && !params.autocommit) {
    throw new Error(
        "Write operations require either:\n" +
        "- 'session_id' from pg_tx('begin') for transactional writes, OR\n" +
        "- 'autocommit: true' for single-statement writes\n" +
        "Example: { sql: 'INSERT...', autocommit: true }\n" +
        "This prevents accidental commits outside transactions."
    );
}
```

## 5. Implementation Phases

### Phase 1: Infrastructure [COMPLETED]
- [x] `SessionManager` with 30m TTL
- [x] Destructive cleanup (`disconnect(true)`)
- [x] `resolveExecutor` helper

### Phase 2: Session Limits & List Action
- [ ] Add `maxSessions` config to `SessionManager`
- [ ] Reject `createSession()` when limit reached with clear error
- [ ] Add `list` action to `pg_tx`

### Phase 3: Core Tool Updates
- [ ] Add `autocommit` parameter to write schemas
- [ ] Implement default-deny guard in write handlers (schema-based detection)
- [ ] Update tool descriptions for LLM guidance

### Phase 4: Batch Transaction Tool
- [ ] Create `pg_transaction` handler
- [ ] Add to tool registry
- [ ] Write tests for atomic commit/rollback behavior

### Phase 5: Conditional Session Echo
- [ ] Create response wrapper utility
- [ ] Inject `active_session` only for writes or near-expiry
- [ ] Include helpful hints in session info

### Phase 6: Verification
- [ ] Test: Write without params → FAIL
- [ ] Test: Write with `autocommit: true` → SUCCESS
- [ ] Test: Write with `session_id` → SUCCESS
- [ ] Test: `pg_transaction` atomic commit
- [ ] Test: `pg_transaction` rollback on failure
- [ ] Test: Transaction isolation between sessions
- [ ] Test: Session TTL expiration → auto-rollback
- [ ] Test: Connection pool returns to baseline after 100 sessions
- [ ] Test: `maxSessions` limit enforced
- [ ] Test: `pg_tx({ action: 'list' })` returns active sessions

### Phase 7: Documentation
- [ ] README: Transactional safety guide
- [ ] README: When to use each approach (autocommit vs transaction vs session)

## 6. Success Metrics

1. **Zero Silent Failures:** All writes require explicit intent
2. **LLM Usability:** Simple operations work with just `autocommit: true`
3. **Context Recovery:** `pg_tx({ action: 'list' })` lets LLMs discover forgotten sessions
4. **Resource Efficiency:** Connections properly returned/destroyed, max sessions enforced
5. **Isolation Guarantee:** Concurrent sessions cannot see uncommitted data

## 7. Rollback Strategy

- **Code:** Git revert to pre-session commits
- **Runtime:** Server restart clears all sessions (MCP is stateless at protocol level)
- **Graceful:** Reduce TTL to 1 minute to quickly expire stuck sessions
