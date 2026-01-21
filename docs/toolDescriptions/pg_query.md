# Tool: pg_query

## Purpose

The `pg_query` tool executes SQL queries for data manipulation (DML) and raw read/write operations. It provides four distinct actions to handle different query scenarios:

- **read**: Execute SELECT queries (safe, read-only)
- **write**: Execute INSERT/UPDATE/DELETE statements
- **explain**: Analyze query execution plans with EXPLAIN
- **transaction**: Execute multiple statements atomically in a stateless batch

This tool is the primary interface for interacting with PostgreSQL data, designed to support both simple queries and complex multi-statement operations while enforcing safety policies.

## Safety Considerations

### Default-Deny Policy for Writes

Write operations (`write` and `transaction` actions) follow the **Default-Deny** policy to prevent accidental data corruption:

- **Without session_id or autocommit:true**: Writes will fail with a safety error
- **With session_id**: Writes execute within a transaction managed by `pg_tx`
- **With autocommit:true**: Writes execute immediately and commit automatically (use with caution)

### Read Operations

The `read` action is **always safe** and read-only. It cannot modify data under any circumstances.

### Query Timeouts

All actions support optional `timeout_ms` to prevent long-running queries from blocking resources.

## Parameters

### Common Parameters

All actions share these base parameters:

- **action** (required): The action to perform (`"read"`, `"write"`, `"explain"`, or `"transaction"`)
- **session_id** (optional): Session ID returned by `pg_tx begin`. Required for reading uncommitted data or performing writes within a transaction.

### Action: read

Execute SELECT queries to retrieve data.

```json
{
  "action": "read",
  "sql": "SELECT * FROM users WHERE active = $1 LIMIT $2",
  "params": [true, 10],
  "session_id": "optional_session_id",
  "options": {
    "timeout_ms": 5000
  }
}
```

**Parameters:**
- **sql** (required): SQL SELECT query to execute
- **params** (optional): Array of values for parameterized queries (use `$1`, `$2`, etc. in SQL)
- **session_id** (optional): Use to read uncommitted data within a transaction
- **options** (optional):
  - **timeout_ms**: Query timeout in milliseconds

**Returns:**
```json
{
  "rows": [
    {"id": 1, "name": "Alice", "active": true},
    {"id": 2, "name": "Bob", "active": true}
  ],
  "rowCount": 2,
  "fields": [
    {"name": "id", "dataTypeID": 23},
    {"name": "name", "dataTypeID": 1043},
    {"name": "active", "dataTypeID": 16}
  ]
}
```

### Action: write

Execute INSERT, UPDATE, or DELETE statements.

```json
{
  "action": "write",
  "sql": "UPDATE users SET last_login = NOW() WHERE id = $1",
  "params": [123],
  "session_id": "required_for_transaction",
  "autocommit": false,
  "options": {
    "timeout_ms": 3000
  }
}
```

**Parameters:**
- **sql** (required): SQL INSERT/UPDATE/DELETE statement
- **params** (optional): Array of values for parameterized queries
- **session_id** (optional): Session ID for transaction context. If omitted, must use `autocommit: true`
- **autocommit** (optional): If `true`, immediately execute and commit. If `false` or omitted, requires `session_id`
- **options** (optional):
  - **timeout_ms**: Query timeout in milliseconds

**Safety requirement:** MUST provide either `session_id` OR `autocommit: true`, or the operation will fail.

**Returns:**
```json
{
  "rowCount": 1,
  "command": "UPDATE"
}
```

### Action: explain

Analyze query execution plans to optimize performance.

```json
{
  "action": "explain",
  "sql": "SELECT * FROM users WHERE email = $1",
  "params": ["user@example.com"],
  "analyze": true,
  "session_id": "optional_session_id",
  "options": {
    "timeout_ms": 10000
  }
}
```

**Parameters:**
- **sql** (required): SQL query to analyze
- **params** (optional): Array of values for parameterized queries
- **analyze** (optional): If `true`, use `EXPLAIN ANALYZE` (executes the query). If `false` or omitted, use `EXPLAIN` (planning only)
- **session_id** (optional): Session context for analysis
- **options** (optional):
  - **timeout_ms**: Query timeout in milliseconds

**Warning:** `EXPLAIN ANALYZE` executes the query, including any side effects from writes. Use cautiously with INSERT/UPDATE/DELETE.

**Returns:**
```json
{
  "plan": "Seq Scan on users  (cost=0.00..15.50 rows=1 width=100) (actual time=0.023..0.024 rows=1 loops=1)\n  Filter: (email = 'user@example.com'::text)\nPlanning Time: 0.082 ms\nExecution Time: 0.045 ms"
}
```

### Action: transaction

Execute multiple SQL statements atomically in a stateless batch transaction.

```json
{
  "action": "transaction",
  "operations": [
    {
      "sql": "INSERT INTO users (name, email) VALUES ($1, $2) RETURNING id",
      "params": ["Charlie", "charlie@example.com"]
    },
    {
      "sql": "INSERT INTO audit_log (action, user_email) VALUES ($1, $2)",
      "params": ["user_created", "charlie@example.com"]
    }
  ],
  "options": {
    "timeout_ms": 5000
  }
}
```

**Parameters:**
- **operations** (required): Array of SQL operations to execute atomically
  - Each operation has:
    - **sql** (required): SQL statement
    - **params** (optional): Array of values for parameterized query
- **options** (optional):
  - **timeout_ms**: Transaction timeout in milliseconds

**Behavior:**
- All operations execute within a single transaction
- If ANY operation fails, ALL are rolled back
- Does NOT require `session_id` (stateless batch)
- Automatically commits on success

**Returns:**
```json
{
  "results": [
    {
      "rows": [{"id": 456}],
      "rowCount": 1,
      "command": "INSERT"
    },
    {
      "rowCount": 1,
      "command": "INSERT"
    }
  ]
}
```

## Examples

### Example 1: Simple SELECT Query

Retrieve active users with pagination:

```json
{
  "action": "read",
  "sql": "SELECT id, name, email FROM users WHERE active = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
  "params": [true, 25, 0]
}
```

### Example 2: JOIN Query

Fetch users with their order counts:

```json
{
  "action": "read",
  "sql": "SELECT u.id, u.name, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE u.active = $1 GROUP BY u.id, u.name ORDER BY order_count DESC",
  "params": [true]
}
```

### Example 3: Autocommit Write

Update a single record immediately (use sparingly):

```json
{
  "action": "write",
  "sql": "UPDATE users SET last_seen = NOW() WHERE id = $1",
  "params": [789],
  "autocommit": true
}
```

### Example 4: Transaction-Based Write

Update within a managed transaction (recommended):

```json
{
  "action": "write",
  "sql": "DELETE FROM sessions WHERE user_id = $1 AND expired = true",
  "params": [123],
  "session_id": "tx_abc123"
}
```

### Example 5: Query Performance Analysis

Analyze index usage:

```json
{
  "action": "explain",
  "sql": "SELECT * FROM users WHERE email = $1",
  "params": ["test@example.com"],
  "analyze": true
}
```

### Example 6: Atomic Batch Transaction

Create user and log action atomically:

```json
{
  "action": "transaction",
  "operations": [
    {
      "sql": "INSERT INTO users (name, email, password_hash) VALUES ($1, $2, $3) RETURNING id",
      "params": ["Dana", "dana@example.com", "hashed_password"]
    },
    {
      "sql": "INSERT INTO audit_log (event_type, details, timestamp) VALUES ($1, $2, NOW())",
      "params": ["user_registration", "{\"email\": \"dana@example.com\"}"]
    }
  ]
}
```

## Common Patterns

### Pattern 1: Safe Reads

For all SELECT queries, use the `read` action without any special safety parameters:

```json
{
  "action": "read",
  "sql": "SELECT * FROM products WHERE category = $1",
  "params": ["electronics"]
}
```

### Pattern 2: Transactional Writes

For writes that are part of a larger transaction, use `pg_tx begin` first:

```json
// Step 1: Begin transaction with pg_tx
{"action": "begin"}

// Step 2: Execute writes with session_id
{
  "action": "write",
  "sql": "UPDATE inventory SET quantity = quantity - $1 WHERE product_id = $2",
  "params": [5, 42],
  "session_id": "tx_xyz789"
}

// Step 3: Commit or rollback with pg_tx
{"action": "commit", "session_id": "tx_xyz789"}
```

### Pattern 3: Quick Autocommit

For standalone writes that don't need coordination:

```json
{
  "action": "write",
  "sql": "INSERT INTO page_views (url, timestamp) VALUES ($1, NOW())",
  "params": ["/products/42"],
  "autocommit": true
}
```

### Pattern 4: Multi-Statement Atomic Batch

For related writes that must succeed or fail together:

```json
{
  "action": "transaction",
  "operations": [
    {"sql": "UPDATE accounts SET balance = balance - $1 WHERE id = $2", "params": [100, 1]},
    {"sql": "UPDATE accounts SET balance = balance + $1 WHERE id = $2", "params": [100, 2]},
    {"sql": "INSERT INTO transfers (from_account, to_account, amount) VALUES ($1, $2, $3)", "params": [1, 2, 100]}
  ]
}
```

## Error Handling

### Common Errors

**1. Write without session_id or autocommit**
```
Error: Write operations require either session_id or autocommit:true for safety
```
**Solution:** Add `"autocommit": true` or use `pg_tx begin` to get a `session_id`.

**2. SQL syntax error**
```
Error: syntax error at or near "FORM"
```
**Solution:** Verify SQL syntax. Use parameterized queries for values.

**3. Query timeout**
```
Error: Query timeout after 5000ms
```
**Solution:** Increase `timeout_ms` or optimize the query (use `explain` action).

**4. Invalid session_id**
```
Error: Session not found: tx_invalid
```
**Solution:** Verify session exists with `pg_monitor` or begin a new transaction.

**5. Transaction rollback**
```
Error: current transaction is aborted, commands ignored until end of transaction block
```
**Solution:** A previous statement in the transaction failed. Use `pg_tx rollback` and start fresh.

### Best Practices

1. **Always use parameterized queries** to prevent SQL injection
2. **Set timeout_ms** for expensive queries to prevent resource exhaustion
3. **Use transactions** for related writes that must be atomic
4. **Prefer read action** for SELECT queries (clearer intent, better safety)
5. **Test with explain** before running potentially expensive queries
6. **Use autocommit sparingly** - prefer explicit transaction management with `pg_tx`

## Related Tools

- **pg_tx**: Manage transaction lifecycle (begin/commit/rollback)
- **pg_schema**: Inspect database structure before writing queries
- **pg_monitor**: Debug session state and connection issues
- **pg_admin**: Create/alter/drop tables (DDL operations)
