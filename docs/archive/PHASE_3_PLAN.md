# Phase 3: Complete Tool Suite + Resources + Prompts

Implement the remaining 4 tools (pg_tx, pg_schema, pg_admin, pg_monitor), MCP resources, and MCP prompts.

**Estimated Additions**: ~1,200 lines of code, ~80 tests

---

## Overview

### What This Phase Delivers

✅ **pg_tx tool** - Transaction lifecycle management (6 actions)
✅ **pg_schema tool** - Schema introspection and DDL (5 actions)
✅ **pg_admin tool** - Database maintenance (5 actions)
✅ **pg_monitor tool** - Observability and health (5 actions)
✅ **MCP Resources** - Schema and monitoring resources
✅ **MCP Prompts** - Guided analysis workflows

### Implementation Pattern

All tools follow the **same pattern as pg_query**:

```python
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.server import mcp

# Action registry
TOOL_ACTIONS = {
    "action1": handler1,
    "action2": handler2,
}

# Tool with decorator
@mcp.tool()
async def my_tool(
    action: Literal["action1", "action2"],
    param1: str | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Tool description."""
    handler = TOOL_ACTIONS.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    params = {"param1": param1}
    return await handler(params, context)
```

---

## Part 1: pg_tx Tool

**File**: `coldquery/tools/pg_tx.py`

### Actions

| Action | Description | Safety |
|--------|-------------|--------|
| `begin` | Create session, BEGIN transaction | Returns session_id |
| `commit` | COMMIT and close session | Requires session_id |
| `rollback` | ROLLBACK and close session | Requires session_id |
| `savepoint` | Create savepoint | Requires session_id, validates name |
| `release` | Release savepoint | Requires session_id, validates name |
| `list` | List active sessions | Read-only |

### Tool Implementation

```python
from typing import Literal
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.server import mcp
from coldquery.actions.tx.lifecycle import (
    begin_handler,
    commit_handler,
    rollback_handler,
    savepoint_handler,
    release_handler,
    list_handler,
)

TX_ACTIONS = {
    "begin": begin_handler,
    "commit": commit_handler,
    "rollback": rollback_handler,
    "savepoint": savepoint_handler,
    "release": release_handler,
    "list": list_handler,
}

@mcp.tool()
async def pg_tx(
    action: Literal["begin", "commit", "rollback", "savepoint", "release", "list"],
    session_id: str | None = None,
    isolation_level: str | None = None,
    savepoint_name: str | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Manage PostgreSQL transaction lifecycle.

    Actions:
    - begin: Start a new transaction, returns session_id
    - commit: Commit transaction and close session
    - rollback: Rollback transaction and close session
    - savepoint: Create a savepoint within a transaction
    - release: Release a savepoint
    - list: List all active sessions with metadata
    """
    handler = TX_ACTIONS.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    params = {
        "session_id": session_id,
        "isolation_level": isolation_level,
        "savepoint_name": savepoint_name,
    }

    return await handler(params, context)
```

### Action Handler: begin

**File**: `coldquery/actions/tx/lifecycle.py`

```python
import json
from typing import Dict, Any
from coldquery.core.context import ActionContext
from coldquery.middleware.session_echo import enrich_response

async def begin_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Begin a new transaction."""
    isolation_level = params.get("isolation_level")

    # Create session
    session_id = await context.session_manager.create_session()

    try:
        # Get session executor
        executor = context.session_manager.get_session_executor(session_id)
        if not executor:
            raise RuntimeError(f"Failed to create session: {session_id}")

        # BEGIN with optional isolation level
        if isolation_level:
            valid_levels = ["READ UNCOMMITTED", "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]
            if isolation_level.upper() not in valid_levels:
                raise ValueError(f"Invalid isolation level: {isolation_level}")
            await executor.execute(f"BEGIN ISOLATION LEVEL {isolation_level.upper()}")
        else:
            await executor.execute("BEGIN")

        result = {
            "session_id": session_id,
            "isolation_level": isolation_level or "READ COMMITTED",
            "status": "transaction started",
        }

        return enrich_response(result, session_id, context.session_manager)

    except Exception as e:
        # Cleanup on failure
        await context.session_manager.close_session(session_id)
        raise RuntimeError(f"Failed to begin transaction: {e}")
```

### Action Handler: commit

```python
async def commit_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Commit transaction and close session."""
    session_id = params.get("session_id")

    if not session_id:
        raise ValueError("session_id is required for commit action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ValueError(f"Invalid or expired session: {session_id}")

    try:
        await executor.execute("COMMIT")
        result = {"status": "transaction committed"}
        return json.dumps(result)
    finally:
        await context.session_manager.close_session(session_id)
```

### Action Handler: rollback

```python
async def rollback_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Rollback transaction and close session."""
    session_id = params.get("session_id")

    if not session_id:
        raise ValueError("session_id is required for rollback action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ValueError(f"Invalid or expired session: {session_id}")

    try:
        await executor.execute("ROLLBACK")
        result = {"status": "transaction rolled back"}
        return json.dumps(result)
    finally:
        await context.session_manager.close_session(session_id)
```

### Action Handler: savepoint

```python
from coldquery.security.identifiers import sanitize_identifier

async def savepoint_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Create a savepoint within a transaction."""
    session_id = params.get("session_id")
    savepoint_name = params.get("savepoint_name")

    if not session_id:
        raise ValueError("session_id is required for savepoint action")
    if not savepoint_name:
        raise ValueError("savepoint_name is required for savepoint action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ValueError(f"Invalid or expired session: {session_id}")

    # Sanitize savepoint name
    safe_name = sanitize_identifier(savepoint_name)

    await executor.execute(f"SAVEPOINT {safe_name}")

    result = {
        "status": "savepoint created",
        "savepoint_name": savepoint_name,
    }

    return enrich_response(result, session_id, context.session_manager)
```

### Action Handler: release

```python
async def release_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Release a savepoint."""
    session_id = params.get("session_id")
    savepoint_name = params.get("savepoint_name")

    if not session_id:
        raise ValueError("session_id is required for release action")
    if not savepoint_name:
        raise ValueError("savepoint_name is required for release action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ValueError(f"Invalid or expired session: {session_id}")

    # Sanitize savepoint name
    safe_name = sanitize_identifier(savepoint_name)

    await executor.execute(f"RELEASE SAVEPOINT {safe_name}")

    result = {
        "status": "savepoint released",
        "savepoint_name": savepoint_name,
    }

    return enrich_response(result, session_id, context.session_manager)
```

### Action Handler: list

```python
async def list_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """List all active sessions."""
    sessions = context.session_manager.list_sessions()

    result = {
        "sessions": sessions,
        "count": len(sessions),
    }

    return json.dumps(result)
```

### Tests

**File**: `tests/test_pg_tx.py`

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from coldquery.tools.pg_tx import pg_tx
from coldquery.core.context import ActionContext

@pytest.fixture
def mock_context():
    mock_executor = AsyncMock()
    mock_session_manager = MagicMock()
    mock_session_manager.create_session.return_value = "test-session-123"
    mock_session_manager.get_session_executor.return_value = mock_executor
    return ActionContext(executor=mock_executor, session_manager=mock_session_manager)

@pytest.mark.asyncio
async def test_begin_creates_session(mock_context):
    result = await pg_tx(action="begin", context=mock_context)
    assert "test-session-123" in result
    mock_context.session_manager.create_session.assert_called_once()

@pytest.mark.asyncio
async def test_commit_closes_session(mock_context):
    result = await pg_tx(action="commit", session_id="test-session", context=mock_context)
    mock_context.session_manager.close_session.assert_called_once_with("test-session")

@pytest.mark.asyncio
async def test_rollback_closes_session(mock_context):
    result = await pg_tx(action="rollback", session_id="test-session", context=mock_context)
    mock_context.session_manager.close_session.assert_called_once_with("test-session")

@pytest.mark.asyncio
async def test_savepoint_sanitizes_name(mock_context):
    executor = mock_context.session_manager.get_session_executor("test")
    await pg_tx(action="savepoint", session_id="test", savepoint_name="my_savepoint", context=mock_context)
    executor.execute.assert_called_with('SAVEPOINT "my_savepoint"')

@pytest.mark.asyncio
async def test_list_returns_sessions(mock_context):
    mock_context.session_manager.list_sessions.return_value = [
        {"id": "session-1", "idle_time": 10, "expires_in": 1790}
    ]
    result = await pg_tx(action="list", context=mock_context)
    assert "session-1" in result
```

---

## Part 2: pg_schema Tool

**File**: `coldquery/tools/pg_schema.py`

### Actions

| Action | Description | Safety |
|--------|-------------|--------|
| `list` | List database objects (tables, views, etc.) | Read-only |
| `describe` | Describe table structure | Read-only |
| `create` | Create database object | Requires session_id or autocommit |
| `alter` | Alter database object | Requires session_id or autocommit |
| `drop` | Drop database object | Requires session_id or autocommit |

### Tool Implementation

```python
from typing import Literal
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.server import mcp
from coldquery.actions.schema.list import list_handler
from coldquery.actions.schema.describe import describe_handler
from coldquery.actions.schema.ddl import create_handler, alter_handler, drop_handler

SCHEMA_ACTIONS = {
    "list": list_handler,
    "describe": describe_handler,
    "create": create_handler,
    "alter": alter_handler,
    "drop": drop_handler,
}

@mcp.tool()
async def pg_schema(
    action: Literal["list", "describe", "create", "alter", "drop"],
    target: str | None = None,  # table, view, schema, function, trigger, sequence, constraint
    name: str | None = None,
    schema: str | None = None,
    sql: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_sizes: bool = False,
    cascade: bool = False,
    if_exists: bool = False,
    if_not_exists: bool = False,
    session_id: str | None = None,
    autocommit: bool | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Manage database schema and introspection.

    Actions:
    - list: List database objects (tables, views, functions, etc.)
    - describe: Get detailed structure of a table
    - create: Create database objects with DDL
    - alter: Modify existing database objects
    - drop: Remove database objects
    """
    handler = SCHEMA_ACTIONS.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    params = {
        "target": target,
        "name": name,
        "schema": schema,
        "sql": sql,
        "limit": limit,
        "offset": offset,
        "include_sizes": include_sizes,
        "cascade": cascade,
        "if_exists": if_exists,
        "if_not_exists": if_not_exists,
        "session_id": session_id,
        "autocommit": autocommit,
    }

    return await handler(params, context)
```

### Action Handler: list

**File**: `coldquery/actions/schema/list.py`

```python
import json
from typing import Dict, Any
from coldquery.core.context import ActionContext
from coldquery.core.executor import resolve_executor

async def list_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """List database objects."""
    target = params.get("target", "table")
    schema = params.get("schema")
    limit = params.get("limit", 100)
    offset = params.get("offset", 0)
    include_sizes = params.get("include_sizes", False)
    session_id = params.get("session_id")

    executor = await resolve_executor(context, session_id)

    # Build query based on target type
    if target == "table":
        sql = """
            SELECT
                schemaname as schema,
                tablename as name,
                tableowner as owner
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename
            LIMIT $1 OFFSET $2
        """
        result = await executor.execute(sql, [limit, offset])

    elif target == "view":
        sql = """
            SELECT
                schemaname as schema,
                viewname as name,
                viewowner as owner
            FROM pg_views
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, viewname
            LIMIT $1 OFFSET $2
        """
        result = await executor.execute(sql, [limit, offset])

    elif target == "schema":
        sql = """
            SELECT
                schema_name as name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schema_name
            LIMIT $1 OFFSET $2
        """
        result = await executor.execute(sql, [limit, offset])

    else:
        raise ValueError(f"Unsupported target type: {target}")

    return json.dumps(result.to_dict())
```

### Action Handler: describe

**File**: `coldquery/actions/schema/describe.py`

```python
import json
from typing import Dict, Any
from coldquery.core.context import ActionContext
from coldquery.core.executor import resolve_executor

async def describe_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Describe table structure."""
    name = params.get("name")
    schema_name = params.get("schema", "public")
    session_id = params.get("session_id")

    if not name:
        raise ValueError("'name' parameter is required for describe action")

    executor = await resolve_executor(context, session_id)

    # Get columns
    columns_sql = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
    """
    columns = await executor.execute(columns_sql, [schema_name, name])

    # Get indexes
    indexes_sql = """
        SELECT
            indexname as name,
            indexdef as definition
        FROM pg_indexes
        WHERE schemaname = $1 AND tablename = $2
    """
    indexes = await executor.execute(indexes_sql, [schema_name, name])

    result = {
        "table": name,
        "schema": schema_name,
        "columns": columns.rows,
        "indexes": indexes.rows,
    }

    return json.dumps(result)
```

### Action Handler: DDL (create/alter/drop)

**File**: `coldquery/actions/schema/ddl.py`

```python
import json
from typing import Dict, Any
from coldquery.core.context import ActionContext
from coldquery.core.executor import resolve_executor
from coldquery.security.access_control import require_write_access
from coldquery.middleware.session_echo import enrich_response

async def create_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Create database object."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit")
    sql = params.get("sql")

    if not sql:
        raise ValueError("'sql' parameter is required for create action")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result = await executor.execute(sql)

    return enrich_response(result.to_dict(), session_id, context.session_manager)

async def alter_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Alter database object."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit")
    sql = params.get("sql")

    if not sql:
        raise ValueError("'sql' parameter is required for alter action")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result = await executor.execute(sql)

    return enrich_response(result.to_dict(), session_id, context.session_manager)

async def drop_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Drop database object."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit")
    sql = params.get("sql")

    if not sql:
        raise ValueError("'sql' parameter is required for drop action")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result = await executor.execute(sql)

    return enrich_response(result.to_dict(), session_id, context.session_manager)
```

### Tests

**File**: `tests/test_pg_schema.py`

```python
@pytest.mark.asyncio
async def test_list_tables(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(
        rows=[{"schema": "public", "name": "users", "owner": "postgres"}],
        row_count=1,
        fields=[],
    )

    result = await pg_schema(action="list", target="table", context=mock_context)
    assert "users" in result

@pytest.mark.asyncio
async def test_describe_table(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.side_effect = [
        QueryResult(rows=[{"column_name": "id", "data_type": "integer"}], row_count=1, fields=[]),
        QueryResult(rows=[{"name": "users_pkey"}], row_count=1, fields=[]),
    ]

    result = await pg_schema(action="describe", name="users", context=mock_context)
    assert "columns" in result

@pytest.mark.asyncio
async def test_create_requires_auth(mock_context):
    with pytest.raises(PermissionError):
        await pg_schema(action="create", sql="CREATE TABLE test (id INT)", context=mock_context)
```

---

## Part 3: pg_admin Tool

**File**: `coldquery/tools/pg_admin.py`

### Actions

| Action | Description |
|--------|-------------|
| `vacuum` | VACUUM tables |
| `analyze` | ANALYZE tables |
| `reindex` | REINDEX tables |
| `stats` | Get table statistics |
| `settings` | Get/set configuration |

### Tool Implementation

```python
@mcp.tool()
async def pg_admin(
    action: Literal["vacuum", "analyze", "reindex", "stats", "settings"],
    table: str | None = None,
    full: bool = False,
    verbose: bool = False,
    setting_name: str | None = None,
    setting_value: str | None = None,
    category: str | None = None,
    session_id: str | None = None,
    autocommit: bool | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Database administration and maintenance."""
    # Similar pattern to other tools
```

---

## Part 4: pg_monitor Tool

**File**: `coldquery/tools/pg_monitor.py`

### Actions

| Action | Description |
|--------|-------------|
| `health` | Database health check |
| `activity` | Active queries |
| `connections` | Connection stats |
| `locks` | Lock information |
| `size` | Database sizes |

### Tool Implementation

```python
@mcp.tool()
async def pg_monitor(
    action: Literal["health", "activity", "connections", "locks", "size"],
    include_idle: bool = False,
    database: str | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Database monitoring and observability."""
    # All actions are read-only, no safety checks needed
```

---

## Part 5: MCP Resources

**File**: `coldquery/resources/schema_resources.py`

```python
from fastmcp import Context
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.server import mcp
from coldquery.actions.schema.list import list_handler
from coldquery.actions.schema.describe import describe_handler

@mcp.resource("postgres://schema/tables")
async def tables_resource(ctx: ActionContext = CurrentActionContext()) -> str:
    """List all tables in the database."""
    params = {"target": "table", "limit": 100, "offset": 0}
    return await list_handler(params, ctx)

@mcp.resource("postgres://schema/{schema}/{table}")
async def table_resource(schema: str, table: str, ctx: ActionContext = CurrentActionContext()) -> str:
    """Get detailed information about a specific table."""
    params = {"name": table, "schema": schema}
    return await describe_handler(params, ctx)
```

**File**: `coldquery/resources/monitor_resources.py`

```python
@mcp.resource("postgres://monitor/health")
async def health_resource(ctx: ActionContext = CurrentActionContext()) -> str:
    """Database health status."""
    # Call health_handler

@mcp.resource("postgres://monitor/activity")
async def activity_resource(ctx: ActionContext = CurrentActionContext()) -> str:
    """Current database activity."""
    # Call activity_handler
```

---

## Part 6: MCP Prompts

**File**: `coldquery/prompts/analyze_query.py`

```python
from fastmcp import Context
from coldquery.server import mcp

@mcp.prompt()
async def analyze_query_performance(sql: str, ctx: Context) -> list:
    """Analyze query performance and suggest optimizations.

    This prompt guides the LLM to:
    1. Run EXPLAIN ANALYZE on the query
    2. Check table statistics
    3. Review indexes
    4. Suggest optimizations
    """
    return [
        {
            "role": "user",
            "content": f"""Analyze the performance of this SQL query:

```sql
{sql}
```

Steps:
1. Use pg_query with action="explain" and analyze=true to get the query plan
2. Use pg_admin with action="stats" to check table statistics
3. Use pg_schema with action="describe" to review indexes
4. Provide optimization recommendations
"""
        }
    ]
```

**File**: `coldquery/prompts/debug_locks.py`

```python
@mcp.prompt()
async def debug_lock_contention(ctx: Context) -> list:
    """Debug lock contention issues.

    Guides the LLM to investigate blocking queries and locks.
    """
    return [
        {
            "role": "user",
            "content": """Investigate database lock contention:

1. Use pg_monitor with action="locks" to see current locks
2. Use pg_monitor with action="activity" to see blocking queries
3. Use pg_tx with action="list" to see active transactions
4. Provide recommendations for resolving contention
"""
        }
    ]
```

---

## Implementation Checklist

### Tools (4 tools, 21 actions)
- [ ] `coldquery/tools/pg_tx.py` - 6 actions
- [ ] `coldquery/actions/tx/lifecycle.py` - All 6 handlers
- [ ] `tests/test_pg_tx.py` - ~15 tests

- [ ] `coldquery/tools/pg_schema.py` - 5 actions
- [ ] `coldquery/actions/schema/list.py` - List handler
- [ ] `coldquery/actions/schema/describe.py` - Describe handler
- [ ] `coldquery/actions/schema/ddl.py` - Create/alter/drop handlers
- [ ] `tests/test_pg_schema.py` - ~20 tests

- [ ] `coldquery/tools/pg_admin.py` - 5 actions
- [ ] `coldquery/actions/admin/maintenance.py` - Vacuum/analyze/reindex
- [ ] `coldquery/actions/admin/stats.py` - Stats handler
- [ ] `coldquery/actions/admin/settings.py` - Settings handler
- [ ] `tests/test_pg_admin.py` - ~15 tests

- [ ] `coldquery/tools/pg_monitor.py` - 5 actions
- [ ] `coldquery/actions/monitor/health.py` - Health handler
- [ ] `coldquery/actions/monitor/observability.py` - Activity/connections/locks/size
- [ ] `tests/test_pg_monitor.py` - ~15 tests

### Resources
- [ ] `coldquery/resources/schema_resources.py` - 2 resources
- [ ] `coldquery/resources/monitor_resources.py` - 2 resources
- [ ] `tests/test_resources.py` - ~8 tests

### Prompts
- [ ] `coldquery/prompts/analyze_query.py` - Query analysis prompt
- [ ] `coldquery/prompts/debug_locks.py` - Lock debugging prompt
- [ ] `tests/test_prompts.py` - ~4 tests

---

## Key Requirements

### 1. Use Verified FastMCP Patterns

✅ **Correct**: `@mcp.tool()` decorator (no parameters)
✅ **Correct**: `@mcp.resource("uri")` decorator
✅ **Correct**: `@mcp.prompt()` decorator
✅ **Correct**: Dependency injection via `CurrentActionContext()`

❌ **Wrong**: `@mcp.tool(name="...", annotations={...})`
❌ **Wrong**: `mcp.register(tool)`
❌ **Wrong**: Manual context passing

### 2. Test Each Component

- Unit tests with mocks for all handlers
- Test error conditions (missing params, invalid values)
- Test safety checks (Default-Deny for DDL operations)
- Verify tool dispatch logic

### 3. Import Tools in server.py

```python
# coldquery/server.py
if __name__ == "__main__":
    # Import all tools to register them
    from coldquery.tools import pg_query, pg_tx, pg_schema, pg_admin, pg_monitor  # noqa: F401
    from coldquery import resources, prompts  # noqa: F401

    mcp.run()
```

### 4. Documentation

Update README.md with:
- All 5 tools in the table
- Resource URIs
- Available prompts

---

## Estimated Line Counts

| Component | Files | Lines | Tests |
|-----------|-------|-------|-------|
| pg_tx | 2 | ~180 | ~15 |
| pg_schema | 4 | ~300 | ~20 |
| pg_admin | 4 | ~250 | ~15 |
| pg_monitor | 3 | ~220 | ~15 |
| Resources | 2 | ~80 | ~8 |
| Prompts | 2 | ~60 | ~4 |
| **Total** | **17** | **~1,090** | **~77** |

---

## Success Criteria

✅ All 4 tools registered and callable
✅ All 21 actions implemented
✅ All action handlers follow pg_query pattern
✅ Default-Deny enforced on DDL operations
✅ MCP resources accessible via URI
✅ MCP prompts guide LLM workflows
✅ ~77 new tests passing (total ~124 tests)
✅ Server starts without errors
✅ Documentation updated

---

## Reference Files

**TypeScript source** (for SQL queries and logic):
- `packages/core/src/tools/pg-tx.ts`
- `packages/core/src/tools/pg-schema.ts`
- `packages/core/src/tools/pg-admin.ts`
- `packages/core/src/tools/pg-monitor.ts`

**Python patterns** (for FastMCP usage):
- `coldquery/tools/pg_query.py` - Tool registration pattern
- `coldquery/dependencies.py` - Dependency injection pattern
- `tests/test_pg_query.py` - Testing pattern

**Documentation**:
- `docs/fastmcp-api-patterns.md` - FastMCP API reference
- `docs/DEVELOPMENT.md` - Testing and development guide
