# ColdQuery MCP Tool Reference

This document contains the **verbatim tool descriptions and input schemas** exactly as exposed by the MCP server. LLM agents receive these descriptions when they connect.

> **Note:** Tool descriptions now include detailed action lists, safety hints, and usage examples directly in the MCP metadata.

---

## pg_query

**Description:**
```
Execute SQL queries for data manipulation (DML) and raw read/write operations.

Actions:
  • read: Execute SELECT queries (safe, read-only)
  • write: Execute INSERT/UPDATE/DELETE (requires session_id OR autocommit:true)
  • explain: Analyze query execution plans (supports EXPLAIN ANALYZE)
  • transaction: Execute multiple statements atomically (stateless batch)

Safety: Write operations use Default-Deny policy to prevent accidental data corruption.
Without session_id or autocommit:true, writes will fail with a safety error.

Examples:
  {"action": "read", "sql": "SELECT id, status, order_date FROM test_orders ORDER BY order_date DESC LIMIT 5"}
  {"action": "write", "sql": "UPDATE test_orders SET status = 'pending' WHERE id = 1", "autocommit": true}
  {"action": "transaction", "operations": [{"sql": "..."}]}
```

**Hints:** `destructiveHint: true` (contains write actions that can modify data)

### Input Schema (discriminatedUnion on `action`)

#### action: "read"
```json
{
  "action": "read",
  "sql": "<string>",
  "params": ["<optional array of values>"],
  "session_id": "<optional string> Session ID returned by pg_tx 'begin'. Use to read uncommitted data within a transaction.",
  "options": {
    "timeout_ms": "<optional number>"
  }
}
```

#### action: "write"
```json
{
  "action": "write",
  "sql": "<string>",
  "params": ["<optional array of values>"],
  "session_id": "<optional string> Session ID returned by pg_tx 'begin'. REQUIRED for transactional writes.",
  "autocommit": "<optional boolean> Set to true to execute a single-statement write immediately without a transaction. REQUIRED if session_id is not provided.",
  "options": {
    "timeout_ms": "<optional number>"
  }
}
```

**Safety:** Writes fail without `session_id` OR `autocommit: true`:
```
"Safety Check Failed: Write operations require either a valid 'session_id' (for transactions) or 'autocommit: true' (for immediate execution)."
```

#### action: "explain"
```json
{
  "action": "explain",
  "sql": "<string>",
  "params": ["<optional array of values>"],
  "session_id": "<optional string> Session ID returned by pg_tx 'begin'. Required if checking plan for uncommitted changes.",
  "options": {
    "explain_analyze": "<optional boolean>",
    "explain_format": "<optional 'text' | 'json'>",
    "timeout_ms": "<optional number>"
  }
}
```

#### action: "transaction"
```json
{
  "action": "transaction",
  "operations": [
    {"sql": "<string> SQL statement to execute", "params": ["<optional array> Query parameters"]},
    {"sql": "...", "params": ["..."]}
  ]
}
```
*Array of SQL statements to execute atomically in a single transaction. Min 1 operation.*

### Examples (mcp_test database)

```json
{"action": "read", "sql": "SELECT id, status, order_date FROM test_orders ORDER BY order_date DESC LIMIT 5"}
```

```json
{"action": "read", "sql": "SELECT status, COUNT(*)::int AS count FROM test_orders GROUP BY status ORDER BY count DESC"}
```

```json
{"action": "write", "sql": "INSERT INTO test_query_write (name) VALUES ($1)", "params": ["toolref write example"], "autocommit": true}
```

```json
{"action": "transaction", "operations": [
  {"sql": "INSERT INTO test_query_write (name) VALUES ($1)", "params": ["batch_start"]},
  {"sql": "UPDATE test_orders SET status = 'pending' WHERE id = 1"}
]}
```

```json
{"action": "explain", "sql": "SELECT * FROM test_orders WHERE status = $1", "params": ["pending"], "options": {"explain_analyze": true, "explain_format": "json"}}
```

---

## pg_schema

**Description:**
```
Manage database structure and schema objects (DDL).

Actions:
  • list: Enumerate schemas, tables, views, functions, triggers, sequences, constraints (read-only)
  • describe: Get detailed structure of tables (columns, indexes) (read-only)
  • create: Create new tables, indexes, views (requires session_id OR autocommit:true)
  • alter: Modify existing tables (requires session_id OR autocommit:true)
  • drop: Remove objects with optional CASCADE (requires session_id OR autocommit:true)

Safety: DDL mutations (create/alter/drop) use Default-Deny policy.
Without session_id or autocommit:true, DDL will fail with a safety error.

Examples:
  {"action": "list", "target": "table"}
  {"action": "describe", "target": "table", "name": "users"}
  {"action": "create", "target": "table", "name": "logs", "definition": "id SERIAL PRIMARY KEY", "autocommit": true}
```

**Hints:** `destructiveHint: true` (contains create/alter/drop actions that can modify schema)

### Input Schema (discriminatedUnion on `action`)

#### action: "list"
```json
{
  "action": "list",
  "target": "<'database' | 'schema' | 'table' | 'column' | 'index' | 'view' | 'function' | 'trigger' | 'sequence' | 'constraint'>",
  "schema": "<optional string> Filter by schema name",
  "table": "<optional string> Filter by table name (only applies to some targets)",
  "session_id": "<optional string> Session ID. Required to list objects created in uncommitted transactions.",
  "options": {
    "include_sizes": "<optional boolean>",
    "include_materialized": "<optional boolean>",
    "limit": "<optional number>",
    "offset": "<optional number>"
  }
}
```

**Implemented targets:** `schema`, `table`, `view`, `function`, `trigger`, `sequence`, `constraint`
**Not yet implemented:** `database`, `column`, `index` (will throw error)

#### action: "describe"
```json
{
  "action": "describe",
  "target": "<'table' | 'view' | 'function' | 'trigger' | 'sequence'>",
  "name": "<string> Name of the object to describe",
  "schema": "<optional string> Schema where the object resides",
  "session_id": "<optional string> Session ID. Required to describe objects created in uncommitted transactions."
}
```

**Implemented targets:** `table` only
**Not yet implemented:** `view`, `function`, `trigger`, `sequence` (will throw error)

#### action: "create" | "alter" | "drop"
```json
{
  "action": "<'create' | 'alter' | 'drop'>",
  "target": "<'table' | 'index' | 'view' | 'function' | 'trigger' | 'schema'>",
  "name": "<string> Name of the object to create/alter/drop",
  "schema": "<optional string> Target schema name",
  "definition": "<optional string> Object definition SQL (e.g. column list for table, select for view)",
  "session_id": "<optional string> Session ID for transactional DDL. Required for schema changes within a transaction.",
  "autocommit": "<optional boolean> Set to true to execute DDL immediately without a transaction. Required if session_id is not provided.",
  "options": {
    "cascade": "<optional boolean>",
    "if_exists": "<optional boolean>",
    "if_not_exists": "<optional boolean>"
  }
}
```

**Safety:** DDL fails without `session_id` OR `autocommit: true`:
```
"Safety Check Failed: DDL operations require either a valid 'session_id' (for transactions) or 'autocommit: true' (for immediate execution). Example: { action: 'drop', target: 'table', name: 'old_table', autocommit: true }"
```

**Implementation status:**
- `create`: `table`, `index`, `view` only
- `alter`: `table` only
- `drop`: `table`, `view`, `index`, `schema` only
- Not yet implemented: `function`, `trigger` for any action

### Examples (mcp_test database)

```json
{"action": "list", "target": "table"}
```

```json
{"action": "list", "target": "table", "schema": "public"}
```

```json
{"action": "describe", "target": "table", "name": "test_orders"}
```

```json
{"action": "describe", "target": "table", "name": "test_products"}
```

```json
{"action": "create", "target": "table", "name": "toolref_tmp", "definition": "id SERIAL PRIMARY KEY, name TEXT", "options": {"if_not_exists": true}, "autocommit": true}
```

```json
{"action": "drop", "target": "table", "name": "toolref_tmp", "options": {"if_exists": true}, "autocommit": true}
```

---

## pg_monitor

**Description:**
```
Database observability and health monitoring (read-only).

Actions:
  • health: Quick database health check (version, connection status, server time)
  • activity: View currently running queries (excludes idle by default)
  • connections: Connection counts grouped by database and state
  • locks: Active lock information for debugging contention
  • size: Table sizes (top 20) or specific database size

This tool is purely read-only and safe to call at any time.
Useful for debugging performance issues, monitoring activity, and capacity planning.

Examples:
  {"action": "health"}
  {"action": "activity"}
  {"action": "size"}
  {"action": "size", "options": {"database": "mydb"}}
```

**Hints:** `readOnlyHint: true`

### Input Schema (discriminatedUnion on `action`)

#### action: "health"
```json
{
  "action": "health"
}
```

#### action: "connections" | "locks" | "size" | "activity"
```json
{
  "action": "<'connections' | 'locks' | 'size' | 'activity'>",
  "options": {
    "database": "<optional string>",
    "schema": "<optional string>",
    "include_idle": "<optional boolean>"
  }
}
```

### Examples

```json
{"action": "health"}
```
*Returns: `{status, database, version, server_time}`*

```json
{"action": "activity"}
```
*Returns: Active (non-idle) queries with pid, user, database, state, query, query_start*

```json
{"action": "connections"}
```
*Returns: Connection counts grouped by database and state*

```json
{"action": "size"}
```
*Returns: Top 20 tables by size*

```json
{"action": "size", "options": {"database": "mcp_test"}}
```
*Returns: Size of specific database*

---

## pg_admin

**Description:**
```
Database maintenance and administration operations.

Actions:
  • vacuum: Reclaim storage and update statistics (can lock tables, use with care)
  • analyze: Update query planner statistics (safe, recommended after bulk changes)
  • reindex: Rebuild indexes (locks table during operation)
  • stats: View table activity statistics from pg_stat_user_tables (read-only)
  • settings: List/get/set PostgreSQL configuration parameters

Note: vacuum, analyze, reindex are maintenance operations that may affect performance.
The 'settings.set' action requires session_id OR autocommit:true.

Examples:
  {"action": "stats"}
  {"action": "stats", "target": "users"}
  {"action": "vacuum", "target": "users"}
  {"action": "settings", "subaction": "get", "target": "work_mem"}
```

**Hints:** `destructiveHint: true` (maintenance/settings can impact performance or settings)

### Input Schema (discriminatedUnion on `action`)

#### action: "vacuum" | "analyze" | "reindex"
```json
{
  "action": "<'vacuum' | 'analyze' | 'reindex'>",
  "target": "<optional string> Table name. If omitted, applies to all tables.",
  "options": {
    "full": "<optional boolean> For VACUUM FULL",
    "verbose": "<optional boolean> For verbose output",
    "analyze": "<optional boolean> For VACUUM ANALYZE"
  }
}
```

**Note:** `reindex` REQUIRES a target table. Omitting it will cause a SQL syntax error.

#### action: "stats"
```json
{
  "action": "stats",
  "target": "<optional string> Specific table name, or omit for top 20 tables by activity"
}
```

#### action: "settings"
```json
{
  "action": "settings",
  "subaction": "<'list' | 'get' | 'set'> Default: 'list'",
  "target": "<optional string> Setting name (for get/set) or category filter (for list)",
  "value": "<optional string> New value (required for set)",
  "session_id": "<optional string> Session ID for transactional settings. Use to set session-local variables.",
  "autocommit": "<optional boolean> Set to true to execute immediately. Required for 'set' if no session_id is provided."
}
```

### Examples

```json
{"action": "stats"}
```

```json
{"action": "stats", "target": "test_orders"}
```

```json
{"action": "vacuum", "target": "test_orders"}
```

```json
{"action": "analyze", "target": "test_orders"}
```

```json
{"action": "settings"}
```

```json
{"action": "settings", "subaction": "get", "target": "work_mem"}
```

---

## pg_tx

**Description:**
```
Transaction lifecycle management for multi-step database operations.

Actions:
  • begin: Start a new transaction, returns session_id for subsequent calls
  • commit: Commit all changes in the transaction (releases session)
  • rollback: Discard all changes in the transaction (releases session)
  • savepoint: Create a named savepoint within the transaction
  • release: Release (remove) a savepoint
  • list: Show all active sessions (useful for discovery/debugging)

Workflow:
  1. Call begin → receive session_id
  2. Use session_id in pg_query/pg_schema calls
  3. Call commit or rollback with session_id

Session Lifecycle:
  • TTL: Sessions auto-rollback after 30 minutes of inactivity
  • Limit: Maximum 10 concurrent sessions (prevents resource exhaustion)
  • Cleanup: Connections are destroyed on close (no state leakage)

Examples:
  {"action": "list"}
  {"action": "begin"}
  {"action": "begin", "options": {"isolation_level": "serializable"}}
  {"action": "commit", "session_id": "<id>"}
```

**Hints:** `destructiveHint: true` (transaction control affects data state)

### Input Schema

```json
{
  "action": "<'begin' | 'commit' | 'rollback' | 'savepoint' | 'release' | 'list'>",
  "session_id": "<optional string> Transaction Session ID. REQUIRED for commit, rollback, savepoint, release. Use the ID returned by 'begin'.",
  "name": "<optional string> Savepoint identifier name (required for savepoint and release actions)",
  "options": {
    "isolation_level": "<optional 'read_uncommitted' | 'read_committed' | 'repeatable_read' | 'serializable'>"
  }
}
```
*options.isolation_level only used with 'begin' action*

### Examples

```json
{"action": "list"}
```
*Returns: `{status, sessions: [...]}`*

```json
{"action": "begin"}
```
*Returns: `{status, session_id, message}`*

```json
{"action": "begin", "options": {"isolation_level": "serializable"}}
```

```json
{"action": "commit", "session_id": "<id from begin>"}
```

```json
{"action": "rollback", "session_id": "<id from begin>"}
```

```json
{"action": "savepoint", "session_id": "<id from begin>", "name": "my_savepoint"}
```

```json
{"action": "release", "session_id": "<id from begin>", "name": "my_savepoint"}
```

---

## Quick Reference

| Tool | Description | Valid Actions | Hints |
|------|-------------|---------------|-------|
| `pg_query` | Execute SQL queries for data manipulation (DML) | `read`, `write`, `explain`, `transaction` | destructive |
| `pg_schema` | Manage database structure and schema objects (DDL) | `list`, `describe`, `create`, `alter`, `drop` | destructive |
| `pg_monitor` | Database observability (read-only) | `health`, `connections`, `locks`, `size`, `activity` | **readOnly** |
| `pg_admin` | Database maintenance operations | `vacuum`, `analyze`, `reindex`, `stats`, `settings` | destructive |
| `pg_tx` | Transaction lifecycle management | `begin`, `commit`, `rollback`, `savepoint`, `release`, `list` | destructive |

## Minimum Valid Calls

```json
pg_query:   {"action": "read", "sql": "SELECT 1"}
pg_schema:  {"action": "list", "target": "table"}
pg_monitor: {"action": "health"}
pg_admin:   {"action": "stats"}
pg_tx:      {"action": "list"}
```

## Current Database Tables (mcp_test)

| Table | Notes |
|-------|-------|
| `isolation_test` | Transaction isolation test table |
| `live_test_alter` | Table used by live alter tests |
| `live_test_table` | Table used by live DDL tests |
| `test_articles` | Sample articles + updates |
| `test_batch_fail` | Batch transaction failure test |
| `test_batch_tx` | Batch transaction success test |
| `test_events` | Parent for partition examples |
| `test_events_2024_q1` | Partition |
| `test_events_2024_q2` | Partition |
| `test_events_2024_q3` | Partition |
| `test_events_2024_q4` | Partition |
| `test_jsonb_docs` | JSONB query examples |
| `test_logs` | Logging table |
| `test_measurements` | Timeseries-ish measurements |
| `test_orders` | Orders (joins to test_products) |
| `test_products` | Product catalog |
| `test_query_write` | Safety / write tests |
| `ttl_test` | Session TTL tests |
