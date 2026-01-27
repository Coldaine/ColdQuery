# Security Model

ColdQuery is designed with security as a core principle, providing multiple layers of protection for PostgreSQL database access through the MCP protocol.

## Security Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Security Layers                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer 1: Network Access Control (Tailscale)                   │  │
│  │ - Private overlay network                                     │  │
│  │ - Origin validation (MCP_ALLOWED_ORIGINS)                     │  │
│  │ - No public internet exposure                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              ↓                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer 2: Default-Deny Write Policy                            │  │
│  │ - Write operations blocked by default                         │  │
│  │ - Requires explicit session_id OR autocommit:true             │  │
│  │ - Prevents accidental data corruption                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              ↓                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer 3: Session Isolation                                    │  │
│  │ - Dedicated connections per transaction                       │  │
│  │ - Connection destroyed on close (no state leakage)            │  │
│  │ - Automatic TTL cleanup (30 min)                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              ↓                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer 4: Input Validation                                     │  │
│  │ - Parameterized queries (SQL injection prevention)            │  │
│  │ - Identifier sanitization                                     │  │
│  │ - Schema validation (Zod)                                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Default-Deny Write Policy

### Rationale

AI agents can make mistakes. Without guardrails, a simple oversight (forgetting `session_id`) could lead to:
- Unintended data modifications
- Lost data changes (no transaction to rollback)
- Silent failures that are hard to debug

The **Default-Deny** policy makes write operations fail-safe:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Write Operation Decision                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Is session_id provided?                                         │
│      │                                                           │
│      ├── YES ──→ Execute within transaction ✓                   │
│      │                                                           │
│      └── NO ──→ Is autocommit:true?                             │
│                    │                                             │
│                    ├── YES ──→ Execute with autocommit ✓        │
│                    │                                             │
│                    └── NO ──→ REJECT with safety error ✗        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Protected Operations

| Tool | Actions | Protection |
|------|---------|------------|
| `pg_query` | `write`, `transaction` | Requires session_id OR autocommit |
| `pg_schema` | `create`, `alter`, `drop` | Requires session_id OR autocommit |
| `pg_admin` | `settings.set` | Requires session_id OR autocommit |

### Safe Operations (No Protection Needed)

| Tool | Actions | Why Safe |
|------|---------|----------|
| `pg_query` | `read`, `explain` | Read-only |
| `pg_schema` | `list`, `describe` | Read-only metadata |
| `pg_admin` | `stats`, `settings.list/get` | Read-only |
| `pg_monitor` | All actions | Read-only observability |
| `pg_tx` | All actions | Transaction control |

## Session Security

### Isolation Guarantees

Each transaction session provides:

1. **Connection Dedication**: Session gets its own database connection, separate from the pool
2. **State Isolation**: Changes invisible to other connections until commit
3. **Automatic Cleanup**: Connection destroyed (not returned to pool) on close

### Resource Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| Max concurrent sessions | 10 | Prevent connection exhaustion |
| Session TTL | 30 minutes | Prevent abandoned sessions |
| Connection destruction | On close | Prevent state leakage |

### Session Lifecycle Security

```
begin
  └── Creates dedicated connection
       └── Session ID (UUID) generated
            └── Operations use same connection
                 └── commit/rollback
                      └── Connection DESTROYED (not returned to pool)
                           └── Session ID invalidated
```

**Why destroy connections?**
- Temporary tables are automatically dropped
- Session variables are cleared
- Prepared statements are removed
- No state can leak between users

## Input Validation

### SQL Injection Prevention

**All user-provided values MUST go through parameterized queries:**

```typescript
// SAFE: Parameterized query
await executor.execute(
  "SELECT * FROM users WHERE id = $1",
  [userId]
);

// UNSAFE: String concatenation (never do this)
await executor.execute(
  `SELECT * FROM users WHERE id = ${userId}`
);
```

### Identifier Sanitization

For dynamic identifiers (table names, column names), ColdQuery uses sanitization:

```typescript
import { sanitizeIdentifier } from "@pg-mcp/shared/security/identifiers.js";

// Sanitizes and quotes identifier
const safeName = sanitizeIdentifier(tableName);
await executor.execute(`SELECT * FROM ${safeName}`);
```

### Schema Validation

All tool inputs are validated using Zod schemas:

```typescript
const WriteSchema = z.object({
  action: z.literal("write"),
  sql: z.string(),
  params: z.array(z.unknown()).optional(),
  session_id: z.string().optional(),
  autocommit: z.boolean().optional(),
});
```

Invalid inputs are rejected before reaching the database.

## Network Security

### Tailscale Integration

ColdQuery is designed to run on a Tailscale network for:

1. **Private connectivity**: No public internet exposure
2. **Encrypted transport**: WireGuard encryption
3. **Identity-based access**: Tailscale ACLs control who can connect

### Origin Validation

For HTTP transport, the server validates the `Origin` header:

```typescript
// Set allowed origins via environment
MCP_ALLOWED_ORIGINS=https://claude.ai,http://localhost:3000
```

Requests from non-allowed origins are rejected.

### Transport Security

| Transport | Security | Use Case |
|-----------|----------|----------|
| stdio | Process isolation | Local MCP clients |
| HTTP/SSE | TLS + Origin validation | Remote MCP clients |

## Threat Model

### Considered Threats

| Threat | Mitigation |
|--------|------------|
| SQL Injection | Parameterized queries, identifier sanitization |
| Unauthorized writes | Default-Deny policy |
| Session hijacking | UUID session IDs, connection destruction |
| Resource exhaustion | Session limits (10 max), TTL (30 min) |
| State leakage | Connection destruction on close |
| Network interception | Tailscale encryption |
| Unauthorized access | Tailscale ACLs, origin validation |

### Out of Scope

ColdQuery does **not** protect against:

| Threat | Reason | Alternative |
|--------|--------|-------------|
| Database user compromise | Beyond MCP layer | Use PostgreSQL roles/permissions |
| Server host compromise | Infrastructure concern | OS/container hardening |
| Malicious admin with valid credentials | Authorized access | Audit logging |
| Denial of service via valid queries | Business logic | Query timeouts, rate limiting |

## Audit Trail

### Logging

ColdQuery logs operations for debugging and auditing:

```
[pg_query.write] params: {"action":"write","sql":"UPDATE users...","session_id":"tx_abc123"}
[pg_query.write] completed in 45ms
```

Enable verbose logging:
```bash
LOG_LEVEL=debug
```

### Session Tracking

Active sessions can be monitored:

```json
{"tool": "pg_tx", "params": {"action": "list"}}

// Response:
{
  "sessions": [
    {"id": "tx_abc123", "idle_time": "30s", "expires_in": "29m"}
  ]
}
```

### Database Activity

Monitor database activity with `pg_monitor`:

```json
{"tool": "pg_monitor", "params": {"action": "activity"}}
```

## Security Best Practices

### For Operators

1. **Use Tailscale** for network access control
2. **Set MCP_ALLOWED_ORIGINS** to restrict HTTP clients
3. **Use minimal database privileges** for the connection user
4. **Enable audit logging** in production
5. **Monitor session counts** for unusual activity
6. **Keep dependencies updated** for security patches

### For Developers

1. **Always use parameterized queries** - never string concatenation
2. **Validate inputs** with Zod schemas
3. **Use session_id for multi-step operations** - not autocommit
4. **Handle errors gracefully** - don't expose internal details
5. **Test with invalid inputs** - ensure proper rejection

### For AI Agents

1. **Use transactions** for related operations
2. **Commit or rollback explicitly** - don't abandon sessions
3. **Verify data before commit** - use read within transaction
4. **Handle errors** - rollback on failure
5. **Use autocommit sparingly** - prefer explicit transaction management

## Rate Limiting (Future)

Currently, ColdQuery does not implement rate limiting. Future versions may include:

- Request rate limiting per client
- Query complexity limits
- Connection rate limiting

For now, rely on PostgreSQL's built-in protections and network-level controls.

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT open a public issue**
2. Email the maintainer directly with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. Allow time for assessment and fix before disclosure

We take security seriously and will respond promptly to valid reports.
