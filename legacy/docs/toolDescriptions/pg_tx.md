# Tool: pg_tx

## Purpose

The `pg_tx` tool provides transaction lifecycle management for multi-step database operations. It enables coordinated changes across multiple tools while maintaining ACID guarantees:

**Actions:**
- **begin**: Start a new transaction and receive a session_id
- **commit**: Finalize all changes in the transaction
- **rollback**: Discard all changes in the transaction
- **savepoint**: Create a named checkpoint within the transaction
- **release**: Remove a savepoint (keep changes up to that point)
- **list**: Show all active sessions for debugging

This tool is the foundation for safe multi-step data operations, ensuring that related changes either all succeed or all fail together.

## Safety Considerations

### Session Isolation

Each transaction gets a **dedicated database connection** separate from the connection pool:
- Changes are isolated until commit
- Other clients cannot see uncommitted data
- Connection state is completely independent

### Automatic Resource Management

**TTL (Time-to-Live):** Sessions automatically rollback and close after **30 minutes of inactivity**.

**Session Limit:** Maximum **10 concurrent sessions** to prevent resource exhaustion.

**Cleanup on Completion:** Connections are destroyed (not returned to pool) after commit/rollback to prevent state leakage.

### Default-Deny Integration

When you have a `session_id`, you can use it with other tools (`pg_query`, `pg_schema`, `pg_admin`) to perform write operations within the transaction context. This satisfies the Default-Deny policy requirement.

### Error Recovery

If an operation fails within a transaction:
- The session remains open
- You can attempt a `rollback` to clean up
- The session will auto-close after TTL expires if abandoned

## Parameters

### Action: begin

Start a new transaction and receive a session_id.

```json
{
  "action": "begin",
  "options": {
    "isolation_level": "read_committed"
  }
}
```

**Parameters:**
- **options** (optional):
  - **isolation_level**: Transaction isolation level
    - `"read_uncommitted"`: Lowest isolation (rarely used in PostgreSQL)
    - `"read_committed"`: Default level, sees committed data
    - `"repeatable_read"`: Consistent snapshots within transaction
    - `"serializable"`: Highest isolation, serializable execution

**Returns:**
```json
{
  "status": "success",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Transaction started. Use session_id for all subsequent queries in this transaction."
}
```

**Important:** Store the `session_id` - you'll need it for all subsequent operations in this transaction.

### Action: commit

Finalize all changes in the transaction and release the session.

```json
{
  "action": "commit",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters:**
- **session_id** (required): The session ID returned by `begin`

**Returns:**
```json
{
  "status": "success",
  "rowCount": 0
}
```

**Effect:**
- All changes become permanent and visible to other connections
- The session is closed and the connection is destroyed
- The session_id becomes invalid

### Action: rollback

Discard all changes in the transaction and release the session.

```json
{
  "action": "rollback",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters:**
- **session_id** (required): The session ID returned by `begin`

**Returns:**
```json
{
  "status": "success",
  "rowCount": 0
}
```

**Effect:**
- All uncommitted changes are discarded
- The database state returns to what it was before `begin`
- The session is closed and the connection is destroyed
- The session_id becomes invalid

### Action: savepoint

Create a named checkpoint within the transaction for partial rollback.

```json
{
  "action": "savepoint",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "before_risky_operation"
}
```

**Parameters:**
- **session_id** (required): The session ID returned by `begin`
- **name** (required): Identifier for the savepoint (alphanumeric, underscores)

**Returns:**
```json
{
  "status": "success",
  "rowCount": 0
}
```

**Use Case:** Create checkpoints before risky operations. If something goes wrong, you can rollback to the savepoint instead of rolling back the entire transaction.

### Action: release

Remove a savepoint (the changes up to that point are kept).

```json
{
  "action": "release",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "before_risky_operation"
}
```

**Parameters:**
- **session_id** (required): The session ID returned by `begin`
- **name** (required): Identifier of the savepoint to release

**Returns:**
```json
{
  "status": "success",
  "rowCount": 0
}
```

**Effect:** The savepoint is removed. Changes made before and after the savepoint are all kept. Use this when the risky operation succeeded and you no longer need the checkpoint.

### Action: list

Show all active sessions for debugging and monitoring.

```json
{
  "action": "list"
}
```

**Parameters:** None required.

**Returns:**
```json
{
  "status": "success",
  "sessions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "idle_time": "45s",
      "expires_in": "29m"
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "idle_time": "120s",
      "expires_in": "28m"
    }
  ]
}
```

**Fields:**
- **id**: The session UUID
- **idle_time**: Time since last activity on this session
- **expires_in**: Time remaining before automatic rollback and cleanup

## Examples

### Example 1: Basic Transaction Workflow

Complete a transaction with commit:

```json
// Step 1: Begin transaction
{"action": "begin"}
// Response: {"session_id": "tx-abc123", ...}

// Step 2: Execute operations with session_id (using pg_query)
{
  "action": "write",
  "sql": "INSERT INTO users (name, email) VALUES ($1, $2)",
  "params": ["Alice", "alice@example.com"],
  "session_id": "tx-abc123"
}

// Step 3: Commit changes
{"action": "commit", "session_id": "tx-abc123"}
```

### Example 2: Rollback on Error

Discard changes when something goes wrong:

```json
// Step 1: Begin transaction
{"action": "begin"}
// Response: {"session_id": "tx-def456", ...}

// Step 2: First operation succeeds
{
  "action": "write",
  "sql": "INSERT INTO orders (user_id, total) VALUES ($1, $2)",
  "params": [1, 99.99],
  "session_id": "tx-def456"
}

// Step 3: Second operation fails (validation error detected)
// Decision: Roll everything back
{"action": "rollback", "session_id": "tx-def456"}
// Both the order insert and any other changes are discarded
```

### Example 3: Using Savepoints for Partial Rollback

Checkpoint before risky operations:

```json
// Step 1: Begin transaction
{"action": "begin"}
// Response: {"session_id": "tx-ghi789", ...}

// Step 2: Insert main record
{
  "action": "write",
  "sql": "INSERT INTO invoices (customer_id, amount) VALUES ($1, $2) RETURNING id",
  "params": [100, 500.00],
  "session_id": "tx-ghi789"
}

// Step 3: Create savepoint before risky operation
{"action": "savepoint", "session_id": "tx-ghi789", "name": "before_line_items"}

// Step 4: Try to insert line items (might fail)
{
  "action": "write",
  "sql": "INSERT INTO invoice_items (invoice_id, product_id, qty) VALUES ($1, $2, $3)",
  "params": [1, 999, 10],
  "session_id": "tx-ghi789"
}
// This fails: product_id 999 doesn't exist

// Step 5: Rollback to savepoint (keeps the invoice, discards line items)
// Note: This would be done with pg_query using ROLLBACK TO SAVEPOINT
{
  "action": "write",
  "sql": "ROLLBACK TO SAVEPOINT before_line_items",
  "session_id": "tx-ghi789"
}

// Step 6: Try again with valid data
{
  "action": "write",
  "sql": "INSERT INTO invoice_items (invoice_id, product_id, qty) VALUES ($1, $2, $3)",
  "params": [1, 42, 10],
  "session_id": "tx-ghi789"
}

// Step 7: Commit
{"action": "commit", "session_id": "tx-ghi789"}
```

### Example 4: Serializable Isolation for Critical Operations

Highest isolation for financial transactions:

```json
// Step 1: Begin with serializable isolation
{
  "action": "begin",
  "options": {
    "isolation_level": "serializable"
  }
}
// Response: {"session_id": "tx-serial123", ...}

// Step 2: Read balance
{
  "action": "read",
  "sql": "SELECT balance FROM accounts WHERE id = $1 FOR UPDATE",
  "params": [1],
  "session_id": "tx-serial123"
}

// Step 3: Update balance
{
  "action": "write",
  "sql": "UPDATE accounts SET balance = balance - 100 WHERE id = $1",
  "params": [1],
  "session_id": "tx-serial123"
}

// Step 4: Commit
{"action": "commit", "session_id": "tx-serial123"}
```

### Example 5: Check Active Sessions

Monitor transaction state:

```json
{"action": "list"}

// Response:
{
  "status": "success",
  "sessions": [
    {"id": "tx-abc123", "idle_time": "30s", "expires_in": "29m"},
    {"id": "tx-def456", "idle_time": "5m", "expires_in": "25m"}
  ]
}
```

### Example 6: Schema Change in Transaction

Create table and verify before committing:

```json
// Step 1: Begin transaction
{"action": "begin"}
// Response: {"session_id": "tx-schema99", ...}

// Step 2: Create table (using pg_schema)
{
  "action": "create",
  "target": "table",
  "name": "new_feature_table",
  "definition": "id SERIAL PRIMARY KEY, name TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW()",
  "session_id": "tx-schema99"
}

// Step 3: Verify structure (using pg_schema)
{
  "action": "describe",
  "target": "table",
  "name": "new_feature_table",
  "session_id": "tx-schema99"
}

// Step 4: If structure is correct, commit; otherwise rollback
{"action": "commit", "session_id": "tx-schema99"}
```

## Common Patterns

### Pattern 1: Standard CRUD Transaction

The most common pattern for data modifications:

```
1. begin → get session_id
2. pg_query.read (with session_id) → verify preconditions
3. pg_query.write (with session_id) → make changes
4. commit (or rollback if error)
```

### Pattern 2: Multi-Table Atomic Update

Ensure related changes across tables succeed or fail together:

```
1. begin
2. UPDATE table_a (with session_id)
3. UPDATE table_b (with session_id)
4. INSERT INTO table_c (with session_id)
5. commit
```

If any step fails, rollback discards all changes.

### Pattern 3: Optimistic Validation Pattern

Read, validate, then write within the same transaction:

```
1. begin
2. SELECT ... FOR UPDATE (lock row)
3. Validate in application logic
4. If valid: UPDATE ... → commit
5. If invalid: rollback
```

### Pattern 4: Savepoint for Optional Operations

Try optional operations without risking main changes:

```
1. begin
2. Core INSERT (must succeed)
3. savepoint "optional_step"
4. Try optional INSERT
5. If fails: ROLLBACK TO SAVEPOINT optional_step
6. commit (core change saved regardless)
```

### Pattern 5: Session Discovery and Cleanup

For debugging orphaned sessions:

```
1. pg_tx list → see all sessions
2. Identify stale sessions (high idle_time)
3. Note: Sessions auto-cleanup after 30min, but you can manually rollback if needed
```

## Error Handling

### Common Errors

**1. Missing session_id**
```
Error: Action 'commit' requires a valid session_id returned by 'begin'
```
**Solution:** All actions except `begin` and `list` require a `session_id`.

**2. Maximum sessions reached**
```
Error: Maximum session limit (10) reached. Please close an existing session before creating a new one.
```
**Solution:** Commit or rollback existing transactions. Use `list` to see active sessions.

**3. Invalid session_id**
```
Error: Session not found: tx_invalid123
```
**Causes:**
- Session was already committed or rolled back
- Session timed out (30 minute TTL)
- Session ID is incorrect

**Solution:** Begin a new transaction.

**4. Transaction aborted state**
```
Error: current transaction is aborted, commands ignored until end of transaction block
```
**Cause:** A previous command in the transaction failed.
**Solution:** Execute `rollback` to clean up, then start a new transaction.

**5. Savepoint not found**
```
Error: savepoint "nonexistent" does not exist
```
**Solution:** Verify savepoint name. Savepoints are case-sensitive.

**6. Connection closed unexpectedly**
```
Error: Connection terminated unexpectedly
```
**Cause:** Database server restart, network issue, or admin intervention.
**Solution:** Begin a new transaction. Previous uncommitted changes are lost.

### Best Practices

1. **Always commit or rollback** - Don't abandon transactions; they consume resources
2. **Use short-lived transactions** - Long transactions increase lock contention
3. **Handle errors gracefully** - Always rollback on failure to release resources
4. **Use appropriate isolation levels** - `read_committed` is sufficient for most cases
5. **Monitor with list action** - Check for orphaned sessions during debugging
6. **Use savepoints for complex workflows** - Enables partial rollback without losing all work
7. **Keep session_id secure** - Treat it like a session token

## Session Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                       SESSION LIFECYCLE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────┐     ┌──────────────┐     ┌────────┐                    │
│  │begin│────▶│ Active       │────▶│ commit │────▶ Session Closed│
│  └─────┘     │ Transaction  │     └────────┘                    │
│              │              │                                    │
│              │ (uses        │     ┌──────────┐                  │
│              │  session_id) │────▶│ rollback │────▶ Session Closed
│              │              │     └──────────┘                  │
│              │              │                                    │
│              │              │     ┌─────────────┐                │
│              │              │────▶│ TTL Timeout │────▶ Auto-rollback
│              └──────────────┘     │ (30 min)    │    ────▶ Closed│
│                                   └─────────────┘                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Within Active Transaction:                                │   │
│  │  • pg_query with session_id                               │   │
│  │  • pg_schema with session_id                              │   │
│  │  • pg_admin.settings with session_id                      │   │
│  │  • savepoint/release for nested checkpoints               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Technical Details

### Why Dedicated Connections?

In a connection pool, `BEGIN` and `COMMIT` could execute on different connections, which would break transaction semantics. The session manager ensures:

1. `begin` acquires a dedicated connection from the pool
2. All operations with that `session_id` use the same connection
3. `commit`/`rollback` releases and **destroys** the connection (no state leakage)

### Connection Destruction

After `commit` or `rollback`, the connection is destroyed rather than returned to the pool. This prevents:
- Session variable pollution
- Temporary table leakage
- Prepared statement conflicts

### Resource Limits

| Resource | Limit | Rationale |
|----------|-------|-----------|
| Max concurrent sessions | 10 | Prevent connection exhaustion |
| Session TTL | 30 minutes | Balance between workflow needs and resource cleanup |

These limits are configurable in the server configuration.

## Related Tools

- **pg_query**: Execute queries within transaction context using `session_id`
- **pg_schema**: Perform DDL operations within transactions
- **pg_admin**: Set session-local settings with `session_id`
- **pg_monitor**: Monitor database activity (doesn't require sessions)
