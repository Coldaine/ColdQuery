# PostgreSQL MCP Server

A secure, stateful PostgreSQL Model Context Protocol (MCP) server optimized for Agentic AI workflows.

## Key Features

- **Transactional Safety:** "Default-Deny" write policy prevents accidental data corruption.
- **Stateful Sessions:** Persistent database connections for multi-step reasoning.
- **Batch Operations:** Atomic multi-statement execution via `pg_transaction`.
- **LLM Ergonomics:** Active session hints and discovery (`pg_tx:list`).
- **Secure by Design:** Destructive session cleanup and connection pooling.

## Transactional Safety Guide

To prevent silent failures where an AI agent intends to use a transaction but forgets the `session_id`, this server enforces a **Default-Deny** policy for all write operations.

### 1. Simple Writes (Autocommit)
For single-statement updates where a transaction isn't needed, you MUST explicitly set `autocommit: true`.
```json
{
  "action": "write",
  "sql": "UPDATE users SET status = 'active' WHERE id = 1",
  "autocommit": true
}
```

### 2. Multi-Step Transactions (Sessions)
For complex workflows involving multiple queries:
1. Call `pg_tx` with `action: "begin"` to get a `session_id`.
2. Pass the `session_id` to all subsequent `pg_query`, `pg_schema`, or `pg_admin` calls.
3. Call `pg_tx` with `action: "commit"` or `"rollback"` using the same `session_id`.

### 3. Atomic Batch Writes
For multiple statements that should succeed or fail together without session management:
```json
{
  "action": "transaction",
  "operations": [
    { "sql": "INSERT INTO logs (msg) VALUES ($1)", "params": ["started"] },
    { "sql": "UPDATE status SET val = $1", "params": ["running"] }
  ]
}
```

## Tooling Overview

| Tool | Action | Purpose | Safety |
|------|--------|---------|--------|
| `pg_query` | `read` | Fetch data | Session-aware (optional) |
| `pg_query` | `write` | Modify data | **Requires** `session_id` OR `autocommit: true` |
| `pg_query` | `transaction` | Batch atomic | Atomic (Stateless) |
| `pg_schema` | `ddl` | Schema changes | **Requires** `session_id` OR `autocommit: true` |
| `pg_tx` | `begin` | Start session | Returns `session_id` |
| `pg_tx` | `list` | Discover | List active sessions |

## Session Lifecycle

- **TTL:** Sessions automatically rollback and close after 30 minutes of inactivity.
- **Limits:** Maximum 10 concurrent sessions allowed by default.
- **Cleanup:** Connections are destroyed on close (`client.release(true)`) to ensure zero state leakage (temp tables, session vars).

## Testing

To run tests with an automated database lifecycle (start container, test, stop container):
```bash
npm run test:ci
```

If you prefer to manage the database manually:
```bash
docker compose up -d
npm test
docker compose down
```
