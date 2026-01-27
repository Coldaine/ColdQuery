# Tool: pg_admin

## Purpose

The `pg_admin` tool provides database maintenance and administration operations for PostgreSQL. It offers essential database management capabilities:

**Maintenance Operations:**
- **vacuum**: Reclaim storage space and update statistics
- **analyze**: Update query planner statistics for optimization
- **reindex**: Rebuild indexes to fix corruption or bloat

**Monitoring:**
- **stats**: View table activity statistics from `pg_stat_user_tables`

**Configuration:**
- **settings**: List, get, or set PostgreSQL configuration parameters

This tool is essential for database performance optimization, maintenance, and runtime configuration management.

## Safety Considerations

### Performance Impact

Maintenance operations can affect database performance:

- **vacuum**: Can lock tables briefly. Use `VACUUM FULL` with extreme caution (requires exclusive lock and rewrites entire table)
- **analyze**: Generally safe, minimal performance impact
- **reindex**: Locks the table during operation, blocking reads and writes

**Recommendation:** Run maintenance operations during low-traffic periods or maintenance windows.

### Default-Deny for Settings Modification

The `settings.set` subaction follows the **Default-Deny** policy:

- **Without session_id or autocommit:true**: Setting changes will fail with a safety error
- **With session_id**: Settings apply to the transaction session only
- **With autocommit:true**: Settings apply to the current database session

**Important:** PostgreSQL `SET` is session-local. Settings will NOT persist across connections or server restarts. Use `ALTER SYSTEM` (not currently supported) for persistent configuration changes.

### Read-Only Safety

The `stats` action and `settings.list`/`settings.get` are **always safe** and read-only.

## Parameters

### Action: vacuum

Reclaim storage space from deleted rows and update table statistics.

```json
{
  "action": "vacuum",
  "target": "users",
  "options": {
    "full": false,
    "verbose": true,
    "analyze": true
  }
}
```

**Parameters:**
- **target** (optional): Table name to vacuum. If omitted, vacuums all tables in the database.
- **options** (optional):
  - **full**: If `true`, use `VACUUM FULL` (completely rewrites table, requires exclusive lock). Use with caution.
  - **verbose**: If `true`, output detailed progress information
  - **analyze**: If `true`, run `ANALYZE` after `VACUUM` to update statistics

**Returns:**
```json
{
  "status": "success",
  "rowCount": 0
}
```

**Use Cases:**
- Reclaim disk space after large DELETE operations
- Update table statistics after bulk changes
- Regular maintenance to prevent table bloat

### Action: analyze

Update query planner statistics to improve query optimization.

```json
{
  "action": "analyze",
  "target": "orders",
  "options": {
    "verbose": true
  }
}
```

**Parameters:**
- **target** (optional): Table name to analyze. If omitted, analyzes all tables.
- **options** (optional):
  - **verbose**: If `true`, output detailed progress information

**Returns:**
```json
{
  "status": "success",
  "rowCount": 0
}
```

**Use Cases:**
- After bulk INSERT/UPDATE/DELETE operations
- When queries are using suboptimal execution plans
- Regular maintenance (weekly or after significant data changes)

### Action: reindex

Rebuild indexes to fix corruption, remove bloat, or improve performance.

```json
{
  "action": "reindex",
  "target": "users",
  "options": {
    "verbose": false
  }
}
```

**Parameters:**
- **target** (required): Table name to reindex. Cannot be omitted (unlike vacuum/analyze).
- **options** (optional):
  - **verbose**: If `true`, output detailed progress information

**Returns:**
```json
{
  "status": "success",
  "rowCount": 0
}
```

**WARNING:** `REINDEX` locks the table during operation, blocking all reads and writes.

**Use Cases:**
- Fix corrupted indexes
- Reduce index bloat after many updates
- Improve index performance after data distribution changes

### Action: stats

View table activity statistics from PostgreSQL's `pg_stat_user_tables`.

```json
{
  "action": "stats",
  "target": "users"
}
```

**Parameters:**
- **target** (optional): Specific table name. If omitted, returns top 20 tables by activity (inserts + updates + deletes).

**Returns (with target):**
```json
{
  "rows": [
    {
      "schemaname": "public",
      "relname": "users",
      "table_name": "users",
      "seq_scan": 142,
      "seq_tup_read": 14200,
      "idx_scan": 8563,
      "idx_tup_fetch": 8563,
      "n_tup_ins": 1500,
      "n_tup_upd": 320,
      "n_tup_del": 45,
      "n_live_tup": 1455,
      "n_dead_tup": 12,
      "last_vacuum": "2025-01-20T10:30:00Z",
      "last_autovacuum": "2025-01-21T03:15:00Z",
      "last_analyze": "2025-01-20T10:30:00Z",
      "last_autoanalyze": "2025-01-21T03:15:00Z"
    }
  ],
  "rowCount": 1
}
```

**Returns (without target - top 20 by activity):**
```json
{
  "rows": [
    {
      "schemaname": "public",
      "relname": "page_views",
      "table_name": "page_views",
      "seq_scan": 5,
      "seq_tup_read": 500,
      "idx_scan": 95000,
      "idx_tup_fetch": 95000,
      "n_tup_ins": 50000,
      "n_tup_upd": 0,
      "n_tup_del": 10000
    },
    // ... 19 more rows
  ],
  "rowCount": 20
}
```

**Use Cases:**
- Identify tables needing vacuum/analyze (high `n_dead_tup`)
- Detect missing indexes (high `seq_scan` on large tables)
- Monitor table activity patterns
- Verify autovacuum is running (`last_autovacuum` timestamp)

### Action: settings

List, get, or modify PostgreSQL configuration parameters.

#### Subaction: list

Browse all PostgreSQL settings or filter by category.

```json
{
  "action": "settings",
  "subaction": "list",
  "target": "memory"
}
```

**Parameters:**
- **subaction**: Must be `"list"`
- **target** (optional): Category filter pattern (e.g., "memory", "planner", "autovacuum")

**Returns:**
```json
{
  "rows": [
    {
      "name": "work_mem",
      "setting": "4096",
      "unit": "kB",
      "short_desc": "Sets the maximum memory to be used for query workspaces"
    },
    {
      "name": "shared_buffers",
      "setting": "131072",
      "unit": "8kB",
      "short_desc": "Sets the number of shared memory buffers used by the server"
    }
  ],
  "rowCount": 2
}
```

#### Subaction: get

Retrieve a specific configuration parameter.

```json
{
  "action": "settings",
  "subaction": "get",
  "target": "max_connections"
}
```

**Parameters:**
- **subaction**: Must be `"get"`
- **target** (required): Setting name (e.g., "max_connections", "work_mem")

**Returns:**
```json
{
  "rows": [
    {
      "name": "max_connections",
      "setting": "100",
      "unit": null,
      "category": "Connections and Authentication / Connection Settings",
      "short_desc": "Sets the maximum number of concurrent connections"
    }
  ],
  "rowCount": 1
}
```

#### Subaction: set

Modify a configuration parameter for the current session.

```json
{
  "action": "settings",
  "subaction": "set",
  "target": "work_mem",
  "value": "16MB",
  "session_id": "tx_abc123"
}
```

**Parameters:**
- **subaction**: Must be `"set"`
- **target** (required): Setting name to modify
- **value** (required): New value for the setting
- **session_id** (optional): Session ID for transaction-scoped setting
- **autocommit** (optional): If `true`, apply immediately

**Safety requirement:** MUST provide either `session_id` OR `autocommit: true`.

**Important:** PostgreSQL `SET` changes are **session-local only**. They do NOT persist across connections or server restarts.

**Returns:**
```json
{
  "status": "success",
  "message": "Setting work_mem updated to 16MB"
}
```

## Examples

### Example 1: Vacuum Table After Bulk Delete

Reclaim storage after removing old records:

```json
{
  "action": "vacuum",
  "target": "audit_logs",
  "options": {
    "analyze": true,
    "verbose": true
  }
}
```

### Example 2: Vacuum All Tables

Database-wide vacuum (use with caution):

```json
{
  "action": "vacuum",
  "options": {
    "analyze": true
  }
}
```

### Example 3: Full Vacuum on Bloated Table

Complete table rewrite (requires exclusive lock):

```json
{
  "action": "vacuum",
  "target": "heavily_updated_table",
  "options": {
    "full": true,
    "analyze": true
  }
}
```

### Example 4: Update Statistics After Bulk Load

Optimize query plans after data import:

```json
{
  "action": "analyze",
  "target": "imported_data",
  "options": {
    "verbose": true
  }
}
```

### Example 5: Rebuild Corrupted Index

Fix index corruption or bloat:

```json
{
  "action": "reindex",
  "target": "user_sessions"
}
```

### Example 6: Identify Tables Needing Maintenance

Find tables with high dead tuple counts:

```json
{
  "action": "stats"
}
```

Look for rows with high `n_dead_tup` values in the results.

### Example 7: Check Specific Table Activity

Monitor query patterns on a table:

```json
{
  "action": "stats",
  "target": "orders"
}
```

Check `seq_scan` vs `idx_scan` ratio to identify missing indexes.

### Example 8: List Memory-Related Settings

Browse memory configuration:

```json
{
  "action": "settings",
  "subaction": "list",
  "target": "memory"
}
```

### Example 9: Get Current work_mem Setting

Check query workspace memory limit:

```json
{
  "action": "settings",
  "subaction": "get",
  "target": "work_mem"
}
```

### Example 10: Temporarily Increase work_mem for Heavy Query

Allocate more memory for a complex query session:

```json
{
  "action": "settings",
  "subaction": "set",
  "target": "work_mem",
  "value": "64MB",
  "session_id": "tx_analytics_123"
}
```

## Common Patterns

### Pattern 1: Post-Bulk-Operation Maintenance

After large data modifications, update statistics and reclaim space:

```json
// Step 1: Bulk operation (e.g., DELETE old records)
// ... data modification happens ...

// Step 2: Vacuum to reclaim space
{
  "action": "vacuum",
  "target": "target_table",
  "options": {"analyze": true}
}

// Step 3: Verify dead tuples are gone
{
  "action": "stats",
  "target": "target_table"
}
```

### Pattern 2: Performance Investigation

Diagnose slow queries by checking statistics:

```json
// Step 1: Get table statistics
{"action": "stats", "target": "slow_table"}

// Step 2: Check if indexes are being used
// Look for high seq_scan on large tables

// Step 3: If needed, rebuild indexes
{"action": "reindex", "target": "slow_table"}

// Step 4: Update planner statistics
{"action": "analyze", "target": "slow_table"}
```

### Pattern 3: Session-Specific Query Tuning

Optimize settings for a specific workload:

```json
// Step 1: Begin transaction
{"action": "begin"} // pg_tx

// Step 2: Set session parameters
{
  "action": "settings",
  "subaction": "set",
  "target": "work_mem",
  "value": "128MB",
  "session_id": "tx_heavy_query"
}

// Step 3: Run expensive query with optimized settings
// ... query execution ...

// Step 4: Commit/rollback
{"action": "commit", "session_id": "tx_heavy_query"}
```

### Pattern 4: Regular Maintenance Routine

Weekly maintenance workflow:

```json
// Step 1: Identify tables needing vacuum
{"action": "stats"}
// Look for high n_dead_tup values

// Step 2: Vacuum and analyze top candidates
{"action": "vacuum", "target": "table_name", "options": {"analyze": true}}

// Step 3: Verify cleanup
{"action": "stats", "target": "table_name"}
```

## Error Handling

### Common Errors

**1. REINDEX without target**
```
Error: Target table name is required for 'reindex'
```
**Solution:** Provide a specific table name. Database-wide reindex is not supported via this parameter.

**2. SET without session_id or autocommit**
```
Error: Safety Check Failed: 'set' operation requires either a valid 'session_id' or 'autocommit: true'
```
**Solution:** Add `"autocommit": true` or use `pg_tx begin` to get a `session_id`.

**3. Lock timeout during maintenance**
```
Error: canceling statement due to lock timeout
```
**Solution:** Run maintenance during low-traffic periods or increase `lock_timeout` setting.

**4. Invalid setting name**
```
Error: unrecognized configuration parameter "invalid_setting"
```
**Solution:** Use `settings.list` to browse valid parameter names.

**5. Invalid setting value**
```
Error: invalid value for parameter "work_mem": "not_a_number"
```
**Solution:** Verify value format matches parameter type (number, boolean, string, etc.).

**6. VACUUM FULL on large table**
```
Error: could not extend file: No space left on device
```
**Solution:** `VACUUM FULL` requires disk space equal to table size. Use regular `VACUUM` instead.

### Best Practices

1. **Run maintenance during off-hours** - Minimize impact on active workloads
2. **Use ANALYZE after bulk changes** - Ensure query planner has current statistics
3. **Avoid VACUUM FULL on production** - Use regular `VACUUM` unless table bloat is extreme
4. **Monitor stats regularly** - Watch for high `n_dead_tup` and low index usage
5. **Test REINDEX impact** - Verify table size and plan for downtime window
6. **Use session_id for temporary settings** - Avoid polluting database-wide configuration
7. **Check autovacuum settings** - Ensure autovacuum is running (verify `last_autovacuum` in stats)
8. **Document setting changes** - Track which settings were modified and why

## Performance Considerations

### VACUUM vs VACUUM FULL

| Operation | Locks | Disk Space | Duration | Use Case |
|-----------|-------|------------|----------|----------|
| VACUUM | Brief lock | Minimal | Fast | Regular maintenance |
| VACUUM FULL | Exclusive lock | Requires table size | Slow | Extreme bloat only |

**Recommendation:** Use regular `VACUUM` for routine maintenance. Reserve `VACUUM FULL` for emergencies.

### When to ANALYZE

Run `ANALYZE` when:
- After bulk INSERT/UPDATE/DELETE (>10% of table modified)
- Before complex queries on newly loaded data
- When query plans seem suboptimal
- After CREATE INDEX (autovacuum may not trigger immediately)

### REINDEX Considerations

REINDEX is expensive and locks the table. Consider alternatives:
- CREATE INDEX CONCURRENTLY (for new indexes)
- Regular VACUUM to prevent index bloat
- Autovacuum tuning to maintain indexes automatically

## Related Tools

- **pg_query**: Execute queries after optimizing with `pg_admin`
- **pg_tx**: Manage session lifecycle for session-scoped settings
- **pg_monitor**: Monitor active connections and session state
- **pg_schema**: Inspect table structure to identify optimization opportunities

## PostgreSQL Documentation References

For detailed information on these operations, consult:
- [VACUUM documentation](https://www.postgresql.org/docs/current/sql-vacuum.html)
- [ANALYZE documentation](https://www.postgresql.org/docs/current/sql-analyze.html)
- [REINDEX documentation](https://www.postgresql.org/docs/current/sql-reindex.html)
- [pg_stat_user_tables view](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-ALL-TABLES-VIEW)
- [Server configuration parameters](https://www.postgresql.org/docs/current/runtime-config.html)
