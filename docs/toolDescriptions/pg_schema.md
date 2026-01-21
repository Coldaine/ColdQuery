# Tool: pg_schema

## Purpose

The `pg_schema` tool manages database structure and schema objects using Data Definition Language (DDL). It provides both read-only introspection and write operations for database schemas:

**Read-only actions (safe):**
- **list**: Enumerate schemas, tables, views, functions, triggers, sequences, constraints
- **describe**: Get detailed structure of tables including columns and indexes

**Write actions (require safety confirmation):**
- **create**: Create new tables, indexes, views
- **alter**: Modify existing table structures
- **drop**: Remove database objects with optional CASCADE

This tool is essential for understanding database structure before writing queries and for managing schema evolution.

## Safety Considerations

### Default-Deny Policy for DDL Operations

DDL mutations (`create`, `alter`, `drop`) follow the **Default-Deny** policy to prevent accidental schema changes:

- **Without session_id or autocommit:true**: DDL operations will fail with a safety error
- **With session_id**: DDL executes within a transaction managed by `pg_tx`
- **With autocommit:true**: DDL executes immediately and commits automatically

### Read-Only Safety

The `list` and `describe` actions are **always safe** and read-only. They only inspect metadata and cannot modify database structure.

### Drop Operation Warning

The `drop` action permanently removes database objects. Use with extreme caution, especially with the `cascade` option which removes dependent objects.

### Transaction Support

DDL operations support session_id to allow schema changes within transactions. This enables:
- Creating tables and immediately querying them in the same transaction
- Rolling back schema changes if validation fails
- Atomic multi-step schema migrations

## Parameters

### Action: list

Enumerate database objects by type.

```json
{
  "action": "list",
  "target": "table",
  "schema": "public",
  "session_id": "optional_session_id",
  "options": {
    "include_sizes": false,
    "limit": 100,
    "offset": 0
  }
}
```

**Parameters:**
- **target** (required): Type of database object to list
  - `"database"`: List all databases (not yet implemented)
  - `"schema"`: List all schemas (excluding system schemas)
  - `"table"`: List tables in a schema
  - `"column"`: List columns (not yet implemented)
  - `"index"`: List indexes (not yet implemented)
  - `"view"`: List views (including materialized views)
  - `"function"`: List user-defined functions
  - `"trigger"`: List triggers
  - `"sequence"`: List sequences
  - `"constraint"`: List constraints (primary keys, foreign keys, unique, check)
- **schema** (optional): Filter by schema name (defaults to 'public' for tables)
- **table** (optional): Filter by table name (for constraints, triggers, columns)
- **session_id** (optional): Include objects created in uncommitted transactions
- **options** (optional):
  - **include_sizes**: Include size information for tables (not yet implemented)
  - **include_materialized**: Include materialized views when listing views (default: true)
  - **limit**: Maximum number of results to return
  - **offset**: Number of results to skip (for pagination)

**Returns (example for tables):**
```json
{
  "rows": [
    {
      "schema": "public",
      "name": "users",
      "owner": "postgres",
      "has_indexes": true
    },
    {
      "schema": "public",
      "name": "orders",
      "owner": "postgres",
      "has_indexes": true
    }
  ],
  "rowCount": 2
}
```

### Action: describe

Get detailed structure of a database object.

```json
{
  "action": "describe",
  "target": "table",
  "name": "users",
  "schema": "public",
  "session_id": "optional_session_id"
}
```

**Parameters:**
- **target** (required): Type of object to describe
  - `"table"`: Describe table structure (columns and indexes)
  - `"view"`, `"function"`, `"trigger"`, `"sequence"`: Not yet implemented
- **name** (required): Name of the object to describe
- **schema** (optional): Schema where the object resides (defaults to 'public')
- **session_id** (optional): Required to describe objects created in uncommitted transactions

**Returns (for table):**
```json
{
  "name": "users",
  "schema": "public",
  "columns": [
    {
      "name": "id",
      "type": "integer",
      "nullable": "NO",
      "default_value": "nextval('users_id_seq'::regclass)"
    },
    {
      "name": "email",
      "type": "character varying",
      "nullable": "NO",
      "default_value": null
    },
    {
      "name": "created_at",
      "type": "timestamp without time zone",
      "nullable": "YES",
      "default_value": "CURRENT_TIMESTAMP"
    }
  ],
  "indexes": [
    {
      "name": "users_pkey",
      "definition": "CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)"
    },
    {
      "name": "users_email_idx",
      "definition": "CREATE UNIQUE INDEX users_email_idx ON public.users USING btree (email)"
    }
  ]
}
```

### Action: create

Create new database objects (tables, indexes, views).

```json
{
  "action": "create",
  "target": "table",
  "name": "logs",
  "definition": "id SERIAL PRIMARY KEY, event TEXT NOT NULL, timestamp TIMESTAMPTZ DEFAULT NOW()",
  "session_id": "optional_session_id",
  "autocommit": false
}
```

**Parameters:**
- **target** (required): Type of object to create (`"table"`, `"index"`, `"view"`)
- **name** (required): Name of the object to create
- **definition** (required): DDL definition (column definitions for tables, SQL for views)
- **session_id** (optional): Session ID for transaction context
- **autocommit** (optional): If `true`, immediately execute and commit

**Safety requirement:** MUST provide either `session_id` OR `autocommit: true`.

**Returns:**
```json
{
  "success": true,
  "object_type": "table",
  "object_name": "logs"
}
```

### Action: alter

Modify existing database objects.

```json
{
  "action": "alter",
  "target": "table",
  "name": "users",
  "changes": "ADD COLUMN last_login TIMESTAMPTZ",
  "session_id": "optional_session_id",
  "autocommit": false
}
```

**Parameters:**
- **target** (required): Type of object to alter (`"table"`)
- **name** (required): Name of the object to modify
- **changes** (required): ALTER statement clause (e.g., "ADD COLUMN ...", "DROP COLUMN ...")
- **session_id** (optional): Session ID for transaction context
- **autocommit** (optional): If `true`, immediately execute and commit

**Safety requirement:** MUST provide either `session_id` OR `autocommit: true`.

**Returns:**
```json
{
  "success": true,
  "object_type": "table",
  "object_name": "users"
}
```

### Action: drop

Remove database objects with optional CASCADE.

```json
{
  "action": "drop",
  "target": "table",
  "name": "old_logs",
  "cascade": false,
  "session_id": "optional_session_id",
  "autocommit": false
}
```

**Parameters:**
- **target** (required): Type of object to drop (`"table"`, `"view"`, `"index"`, `"sequence"`, `"function"`, `"trigger"`)
- **name** (required): Name of the object to remove
- **cascade** (optional): If `true`, remove dependent objects (default: false)
- **session_id** (optional): Session ID for transaction context
- **autocommit** (optional): If `true`, immediately execute and commit

**Safety requirement:** MUST provide either `session_id` OR `autocommit: true`.

**WARNING:** This operation is irreversible. Data will be permanently deleted.

**Returns:**
```json
{
  "success": true,
  "object_type": "table",
  "object_name": "old_logs"
}
```

## Examples

### Example 1: List All Tables

Get all tables in the public schema:

```json
{
  "action": "list",
  "target": "table",
  "schema": "public"
}
```

### Example 2: List Views with Pagination

Retrieve views 10 at a time:

```json
{
  "action": "list",
  "target": "view",
  "options": {
    "limit": 10,
    "offset": 0,
    "include_materialized": true
  }
}
```

### Example 3: List Constraints for Specific Table

Find all constraints on the users table:

```json
{
  "action": "list",
  "target": "constraint",
  "schema": "public",
  "table": "users"
}
```

### Example 4: Describe Table Structure

Get detailed information about the orders table:

```json
{
  "action": "describe",
  "target": "table",
  "name": "orders",
  "schema": "public"
}
```

### Example 5: Create Table with Autocommit

Create a simple logging table immediately:

```json
{
  "action": "create",
  "target": "table",
  "name": "api_logs",
  "definition": "id SERIAL PRIMARY KEY, endpoint TEXT NOT NULL, status_code INT, timestamp TIMESTAMPTZ DEFAULT NOW()",
  "autocommit": true
}
```

### Example 6: Create Table in Transaction

Create table within a managed transaction:

```json
{
  "action": "create",
  "target": "table",
  "name": "temp_analysis",
  "definition": "user_id INT, metric_value NUMERIC(10,2), calculated_at TIMESTAMPTZ",
  "session_id": "tx_abc123"
}
```

### Example 7: Add Column to Existing Table

Extend users table with a new field:

```json
{
  "action": "alter",
  "target": "table",
  "name": "users",
  "changes": "ADD COLUMN phone VARCHAR(20)",
  "autocommit": true
}
```

### Example 8: Drop Table with CASCADE

Remove table and all dependent views:

```json
{
  "action": "drop",
  "target": "table",
  "name": "deprecated_data",
  "cascade": true,
  "autocommit": true
}
```

### Example 9: List Functions in Custom Schema

Enumerate stored procedures:

```json
{
  "action": "list",
  "target": "function",
  "schema": "analytics"
}
```

### Example 10: Describe Uncommitted Table

Verify structure of a table created in current transaction:

```json
// First, create table in transaction
{
  "action": "create",
  "target": "table",
  "name": "staging_data",
  "definition": "id INT, data JSONB",
  "session_id": "tx_xyz789"
}

// Then describe it before committing
{
  "action": "describe",
  "target": "table",
  "name": "staging_data",
  "session_id": "tx_xyz789"
}
```

## Common Patterns

### Pattern 1: Schema Discovery Workflow

Before writing queries, inspect the database structure:

```json
// Step 1: List all schemas
{"action": "list", "target": "schema"}

// Step 2: List tables in public schema
{"action": "list", "target": "table", "schema": "public"}

// Step 3: Describe interesting tables
{"action": "describe", "target": "table", "name": "users"}
{"action": "describe", "target": "table", "name": "orders"}

// Step 4: Check relationships
{"action": "list", "target": "constraint", "schema": "public"}
```

### Pattern 2: Safe Schema Migration

Create and verify schema changes before committing:

```json
// Step 1: Begin transaction
{"action": "begin"} // pg_tx

// Step 2: Create new table
{
  "action": "create",
  "target": "table",
  "name": "users_v2",
  "definition": "id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW()",
  "session_id": "tx_abc123"
}

// Step 3: Verify structure
{
  "action": "describe",
  "target": "table",
  "name": "users_v2",
  "session_id": "tx_abc123"
}

// Step 4: If satisfied, commit; otherwise rollback
{"action": "commit", "session_id": "tx_abc123"} // pg_tx
```

### Pattern 3: Quick Autocommit DDL

For simple schema changes outside transactions:

```json
{
  "action": "create",
  "target": "table",
  "name": "feature_flags",
  "definition": "flag_name TEXT PRIMARY KEY, enabled BOOLEAN DEFAULT false",
  "autocommit": true
}
```

### Pattern 4: Safe Drop with Verification

Check dependencies before dropping:

```json
// Step 1: List constraints that might depend on this table
{"action": "list", "target": "constraint", "table": "old_table"}

// Step 2: List views that reference this table (requires manual query)

// Step 3: Drop with CASCADE if dependencies exist
{
  "action": "drop",
  "target": "table",
  "name": "old_table",
  "cascade": true,
  "autocommit": true
}
```

## Error Handling

### Common Errors

**1. DDL without session_id or autocommit**
```
Error: DDL operations require either session_id or autocommit:true for safety
```
**Solution:** Add `"autocommit": true` or use `pg_tx begin` to get a `session_id`.

**2. Table/object does not exist**
```
Error: relation "nonexistent_table" does not exist
```
**Solution:** Verify object name with `list` action first.

**3. Constraint violation on drop**
```
Error: cannot drop table "users" because other objects depend on it
```
**Solution:** Use `"cascade": true` or remove dependencies first.

**4. Invalid session_id**
```
Error: Session not found: tx_invalid
```
**Solution:** Verify session exists with `pg_monitor` or begin a new transaction.

**5. Invalid DDL syntax**
```
Error: syntax error at or near "CLOUMN"
```
**Solution:** Verify SQL syntax in `definition` or `changes` parameter.

**6. Permission denied**
```
Error: permission denied for schema public
```
**Solution:** Verify database user has CREATE/ALTER/DROP privileges.

### Best Practices

1. **Always list before describe** - Use `list` to discover object names, then `describe` for details
2. **Use transactions for complex DDL** - Allows rollback if something goes wrong
3. **Verify structure after creation** - Use `describe` to confirm table was created correctly
4. **Check constraints before dropping** - Use `list` with target=constraint to find dependencies
5. **Avoid CASCADE unless necessary** - Explicitly drop dependent objects for clarity
6. **Use autocommit for simple standalone DDL** - Faster for one-off schema changes
7. **Filter lists with schema parameter** - Avoid retrieving system objects unnecessarily

## Related Tools

- **pg_query**: Execute SELECT queries after inspecting schema with `pg_schema`
- **pg_admin**: Alternative tool for DDL operations (handles CREATE/ALTER/DROP for tables)
- **pg_tx**: Manage transaction lifecycle for DDL operations
- **pg_monitor**: Debug session state when working with transactional DDL

## Implementation Notes

### Currently Implemented Targets

**list action:**
- ✓ schema
- ✓ table
- ✓ view
- ✓ function
- ✓ trigger
- ✓ sequence
- ✓ constraint
- ✗ database (not yet implemented)
- ✗ column (not yet implemented)
- ✗ index (not yet implemented)

**describe action:**
- ✓ table (with columns and indexes)
- ✗ view, function, trigger, sequence (not yet implemented)

**create/alter/drop actions:**
- ✓ All targets supported via DDL handler
- Implementation delegates to `pg_admin` tool for actual execution

### Session Support Rationale

Session support allows AI agents to create objects in a transaction and immediately inspect them before committing. Without this, `describe` would query global state and fail to find uncommitted objects.

Example workflow:
1. Begin transaction → get session_id
2. Create table with session_id
3. Describe table with same session_id → sees uncommitted structure
4. Verify columns are correct
5. Commit or rollback based on validation
