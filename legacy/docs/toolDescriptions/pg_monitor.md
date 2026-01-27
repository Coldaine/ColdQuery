# Tool: pg_monitor

## Purpose

The `pg_monitor` tool provides database observability and health monitoring for PostgreSQL. It offers **read-only** visibility into database state for debugging, performance analysis, and capacity planning:

**Actions:**
- **health**: Quick database connectivity and version check
- **activity**: View currently running queries
- **connections**: Connection counts grouped by database and state
- **locks**: Active lock information for debugging contention
- **size**: Table sizes and database storage usage

This tool is completely **safe** and **read-only** - it only queries system views and cannot modify database state.

## Safety Considerations

### Read-Only Guarantee

All `pg_monitor` actions are read-only system queries:
- Cannot modify data or schema
- Cannot affect transaction state
- Safe to call at any time without side effects

### No Authentication Required

This tool queries PostgreSQL system views (`pg_stat_activity`, `pg_locks`, etc.) that are available to database users with appropriate privileges. No additional authentication beyond the configured database connection is needed.

### Performance Impact

Monitor queries are lightweight but may add minor load:
- `health`: Single query, negligible impact
- `activity`, `connections`, `locks`: Query system catalogs, minimal impact
- `size`: May be slower on databases with many tables

## Parameters

### Action: health

Quick database health check - verifies connectivity and returns basic info.

```json
{
  "action": "health"
}
```

**Parameters:** None required.

**Returns:**
```json
{
  "status": "healthy",
  "database": "coldquery",
  "version": "PostgreSQL 16.1 on aarch64-unknown-linux-gnu, compiled by gcc (GCC) 13.2.1 20231205, 64-bit",
  "server_time": "2025-01-21T14:30:00.000Z"
}
```

**Use Cases:**
- Verify database connectivity
- Check PostgreSQL version
- Confirm server is responding

### Action: activity

View currently running queries (excludes idle connections by default).

```json
{
  "action": "activity",
  "options": {
    "include_idle": false
  }
}
```

**Parameters:**
- **options** (optional):
  - **include_idle**: If `true`, include idle connections in results (default: `false`)

**Returns:**
```json
{
  "rows": [
    {
      "pid": 12345,
      "user": "postgres",
      "database": "coldquery",
      "state": "active",
      "query": "SELECT * FROM large_table WHERE ...",
      "query_start": "2025-01-21T14:29:45.000Z"
    },
    {
      "pid": 12346,
      "user": "app_user",
      "database": "coldquery",
      "state": "active",
      "query": "UPDATE orders SET status = ...",
      "query_start": "2025-01-21T14:29:50.000Z"
    }
  ],
  "rowCount": 2
}
```

**Fields:**
- **pid**: PostgreSQL process ID
- **user**: Database user running the query
- **database**: Database name
- **state**: Connection state (`active`, `idle`, `idle in transaction`, etc.)
- **query**: The SQL query being executed
- **query_start**: When the current query started

**Use Cases:**
- Find long-running queries
- Identify blocking operations
- Debug slow performance
- See what's currently executing

### Action: connections

View connection counts grouped by database and state.

```json
{
  "action": "connections",
  "options": {
    "include_idle": false
  }
}
```

**Parameters:**
- **options** (optional):
  - **include_idle**: If `true`, include idle connections in counts (default: `false`)

**Returns:**
```json
{
  "rows": [
    {
      "database": "coldquery",
      "count": 5,
      "state": "active"
    },
    {
      "database": "coldquery",
      "count": 2,
      "state": "idle in transaction"
    },
    {
      "database": "postgres",
      "count": 1,
      "state": "active"
    }
  ],
  "rowCount": 3
}
```

**Fields:**
- **database**: Database name
- **count**: Number of connections in this state
- **state**: Connection state

**Use Cases:**
- Monitor connection pool usage
- Identify connection leaks (`idle in transaction` buildup)
- Capacity planning
- Verify expected connection patterns

### Action: locks

View active locks for debugging contention issues.

```json
{
  "action": "locks"
}
```

**Parameters:** None required.

**Returns:**
```json
{
  "rows": [
    {
      "relname": "users",
      "locktype": "relation",
      "mode": "AccessShareLock",
      "granted": true,
      "query": "SELECT * FROM users WHERE id = 1",
      "query_start": "2025-01-21T14:29:55.000Z"
    },
    {
      "relname": "users",
      "locktype": "relation",
      "mode": "RowExclusiveLock",
      "granted": false,
      "query": "UPDATE users SET name = 'Bob' WHERE id = 1",
      "query_start": "2025-01-21T14:29:56.000Z"
    }
  ],
  "rowCount": 2
}
```

**Fields:**
- **relname**: Table name being locked (may be null for non-relation locks)
- **locktype**: Type of lock (`relation`, `tuple`, `transactionid`, etc.)
- **mode**: Lock mode (`AccessShareLock`, `RowExclusiveLock`, `AccessExclusiveLock`, etc.)
- **granted**: `true` if lock is held, `false` if waiting
- **query**: The query holding or waiting for the lock
- **query_start**: When the query started

**Use Cases:**
- Debug deadlocks
- Find blocking queries (`granted: false` waiting on `granted: true`)
- Identify lock contention patterns
- Understand why queries are slow

### Action: size

View table sizes (top 20) or specific database size.

**For table sizes:**
```json
{
  "action": "size"
}
```

**For specific database size:**
```json
{
  "action": "size",
  "options": {
    "database": "coldquery"
  }
}
```

**Parameters:**
- **options** (optional):
  - **database**: Database name to get total size. If omitted, returns top 20 tables by size.

**Returns (table sizes):**
```json
{
  "rows": [
    {"name": "large_events", "size": "2458 MB"},
    {"name": "user_sessions", "size": "856 MB"},
    {"name": "audit_logs", "size": "423 MB"},
    {"name": "users", "size": "12 MB"},
    {"name": "products", "size": "8192 kB"}
  ],
  "rowCount": 5
}
```

**Returns (database size):**
```json
{
  "rows": [
    {"name": "coldquery", "size": "3847 MB"}
  ],
  "rowCount": 1
}
```

**Use Cases:**
- Identify large tables for optimization
- Monitor storage growth
- Capacity planning
- Find candidates for archival/cleanup

## Examples

### Example 1: Health Check

Verify database connectivity:

```json
{"action": "health"}

// Response:
{
  "status": "healthy",
  "database": "production",
  "version": "PostgreSQL 16.1 ...",
  "server_time": "2025-01-21T14:30:00.000Z"
}
```

### Example 2: Find Long-Running Queries

Identify queries that might be causing slowdowns:

```json
{"action": "activity"}

// Look for queries with old query_start timestamps
// or queries in "idle in transaction" state
```

### Example 3: Include Idle Connections

See all connections including idle ones:

```json
{
  "action": "activity",
  "options": {
    "include_idle": true
  }
}
```

### Example 4: Monitor Connection Pool

Check connection usage patterns:

```json
{"action": "connections"}

// High "idle in transaction" count = potential connection leak
// High "active" count = heavy load or slow queries
```

### Example 5: Debug Lock Contention

Find what's blocking queries:

```json
{"action": "locks"}

// Look for rows where granted: false
// The corresponding granted: true row shows the blocker
```

### Example 6: Find Largest Tables

Identify storage-heavy tables:

```json
{"action": "size"}

// Returns top 20 tables by size
// Good candidates for:
// - Partitioning
// - Archival
// - Index optimization
```

### Example 7: Check Database Total Size

Get overall database storage:

```json
{
  "action": "size",
  "options": {
    "database": "production"
  }
}

// Response:
{
  "rows": [{"name": "production", "size": "15 GB"}],
  "rowCount": 1
}
```

## Common Patterns

### Pattern 1: Troubleshooting Slow Performance

Systematic approach to diagnose slowdowns:

```json
// Step 1: Verify database is healthy
{"action": "health"}

// Step 2: Check for long-running queries
{"action": "activity"}

// Step 3: Look for lock contention
{"action": "locks"}

// Step 4: Check connection saturation
{"action": "connections"}

// Step 5: Review table sizes (large tables = slow scans)
{"action": "size"}
```

### Pattern 2: Connection Leak Detection

Find and diagnose connection leaks:

```json
// Step 1: Get connection counts
{
  "action": "connections",
  "options": {"include_idle": true}
}

// Step 2: If high "idle in transaction" count, find the culprits
{"action": "activity", "options": {"include_idle": true}}

// Look for connections in "idle in transaction" state with old query_start
// These are likely abandoned transactions
```

### Pattern 3: Deadlock Investigation

Debug deadlock situations:

```json
// Step 1: Check locks
{"action": "locks"}

// Step 2: Find waiting locks (granted: false)
// Step 3: Find the PID of the blocker
// Step 4: Check what query the blocker is running
{"action": "activity"}

// Cross-reference PIDs to understand the lock chain
```

### Pattern 4: Capacity Planning

Monitor growth trends:

```json
// Check database total size
{"action": "size", "options": {"database": "production"}}

// Check individual table sizes
{"action": "size"}

// Track over time to understand growth patterns
```

### Pattern 5: Pre-Deployment Health Check

Verify system state before deploying:

```json
// Step 1: Verify connectivity
{"action": "health"}

// Step 2: Check for active transactions that might conflict
{"action": "activity"}

// Step 3: Ensure no unusual lock patterns
{"action": "locks"}

// Step 4: Verify connection headroom
{"action": "connections", "options": {"include_idle": true}}
```

## Error Handling

### Common Errors

**1. Connection refused**
```
Error: connect ECONNREFUSED 127.0.0.1:5432
```
**Cause:** Database server is not running or not accessible.
**Solution:** Verify PostgreSQL is running and connection settings are correct.

**2. Permission denied**
```
Error: permission denied for relation pg_stat_activity
```
**Cause:** Database user lacks privileges to query system views.
**Solution:** Grant appropriate privileges or use a superuser account.

**3. Database does not exist**
```
Error: database "nonexistent" does not exist
```
**Solution:** Verify database name with `health` action first.

### Best Practices

1. **Start with health** - Always verify connectivity before other operations
2. **Exclude idle by default** - Use `include_idle: false` to focus on active work
3. **Monitor regularly** - Set up periodic health checks for early problem detection
4. **Correlate metrics** - Combine activity, locks, and connections for full picture
5. **Track size trends** - Monitor storage growth over time, not just point-in-time
6. **Use during incidents** - pg_monitor is safe to call during production issues

## PostgreSQL System Views

This tool queries the following PostgreSQL system views:

| Action | View(s) Used | Documentation |
|--------|--------------|---------------|
| health | Direct queries (version(), current_database(), now()) | - |
| activity | `pg_stat_activity` | [pg_stat_activity](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW) |
| connections | `pg_stat_activity` | Same as above |
| locks | `pg_locks`, `pg_stat_activity`, `pg_class` | [pg_locks](https://www.postgresql.org/docs/current/view-pg-locks.html) |
| size | `pg_statio_user_tables`, `pg_database_size()` | [Database Size Functions](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADMIN-DBSIZE) |

## Lock Mode Reference

Common lock modes you'll see in the `locks` action:

| Mode | Conflicts With | Description |
|------|----------------|-------------|
| `AccessShareLock` | `AccessExclusiveLock` | Acquired by SELECT |
| `RowShareLock` | `ExclusiveLock`, `AccessExclusiveLock` | Acquired by SELECT FOR UPDATE/SHARE |
| `RowExclusiveLock` | `ShareLock`, `ShareRowExclusiveLock`, `ExclusiveLock`, `AccessExclusiveLock` | Acquired by UPDATE, DELETE, INSERT |
| `ShareLock` | `RowExclusiveLock`, `ShareUpdateExclusiveLock`, `ShareRowExclusiveLock`, `ExclusiveLock`, `AccessExclusiveLock` | Acquired by CREATE INDEX |
| `AccessExclusiveLock` | All locks | Acquired by ALTER TABLE, DROP TABLE, TRUNCATE, VACUUM FULL |

## Related Tools

- **pg_admin**: View table statistics (`stats` action) for usage patterns
- **pg_tx**: List active transaction sessions
- **pg_query**: Execute custom monitoring queries if built-in actions don't suffice
- **pg_schema**: Understand table structure for lock analysis
