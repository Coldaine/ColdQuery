# ColdQuery Development Guide

Comprehensive guide for developing and contributing to ColdQuery (Python FastMCP 3.0 implementation).

## Table of Contents

- [Setup](#setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [FastMCP Architecture](#fastmcp-architecture)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)
- [Code Style](#code-style)

---

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ (via Docker)
- pip or uv package manager

### Initial Setup

```bash
# Clone repository
git clone https://github.com/Coldaine/ColdQuery.git
cd ColdQuery

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Start test database
docker compose up -d

# Verify installation
pytest tests/ -v
```

### IDE Setup

**VS Code**

`.vscode/settings.json`:
```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    },
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false
}
```

**PyCharm**

1. Settings → Tools → Python Integrated Tools → Default test runner: pytest
2. Settings → Tools → Actions on Save → Reformat code ✓
3. Settings → Tools → External Tools → Add Ruff

---

## Development Workflow

### Daily Workflow

```bash
# 1. Pull latest changes
git pull origin main

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes and test frequently
pytest tests/ -k "relevant_test"

# 4. Run full test suite before committing
pytest tests/ -v

# 5. Check code quality
ruff check coldquery/ tests/
mypy coldquery/

# 6. Commit and push
git add .
git commit -m "feat: add my feature"
git push origin feature/my-feature
```

### Running the Server

**stdio mode (for MCP clients):**
```bash
python -m coldquery.server
```

**HTTP mode (for debugging):**
```bash
python -m coldquery.server --transport http

# In another terminal, test with curl:
curl http://localhost:3000/health
```

**With custom database:**
```bash
DB_HOST=prod-db DB_PORT=5432 python -m coldquery.server
```

### Hot Reloading During Development

FastMCP doesn't have built-in hot reload, but you can use watchfiles:

```bash
pip install watchfiles
watchfiles --filter python 'python -m coldquery.server' coldquery/
```

---

## Testing

### Test Structure

```
tests/
  conftest.py               # Shared fixtures
  test_context.py           # ActionContext tests
  test_executor.py          # Database executor tests
  test_session.py           # Session management tests
  test_security.py          # Identifier sanitization tests
  test_pg_query.py          # Tool and action handler tests
  integration/
    test_safety.py          # Default-Deny policy tests
    test_isolation.py       # Transaction isolation tests
```

### Running Tests

```bash
# All tests
pytest tests/

# Specific file
pytest tests/test_pg_query.py

# Specific test
pytest tests/test_pg_query.py::test_write_action_blocked_without_auth

# With coverage
pytest tests/ --cov=coldquery --cov-report=html
# View: open htmlcov/index.html

# Watch mode (requires pytest-watch)
ptw tests/

# Verbose output
pytest tests/ -v -s

# Stop on first failure
pytest tests/ -x

# Run tests matching pattern
pytest tests/ -k "write"
```

### Writing Tests

**Unit Test Pattern:**

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from coldquery.core.context import ActionContext
from coldquery.actions.query.read import read_handler

@pytest.mark.asyncio
async def test_read_action_returns_rows():
    # Arrange
    mock_executor = AsyncMock()
    mock_executor.execute.return_value = QueryResult(
        rows=[{"id": 1, "name": "Alice"}],
        row_count=1,
        fields=[{"name": "id", "type": "int"}, {"name": "name", "type": "str"}],
    )

    mock_context = ActionContext(
        executor=mock_executor,
        session_manager=MagicMock(),
    )

    params = {
        "sql": "SELECT * FROM users",
        "params": None,
    }

    # Act
    result = await read_handler(params, mock_context)

    # Assert
    assert "rows" in result
    mock_executor.execute.assert_called_once_with("SELECT * FROM users", None)
```

**Integration Test Pattern:**

```python
import pytest
import asyncpg
from coldquery.core.executor import AsyncpgPoolExecutor

@pytest.mark.asyncio
@pytest.mark.integration
async def test_actual_database_query():
    """Test with real database connection."""
    executor = AsyncpgPoolExecutor()

    try:
        result = await executor.execute("SELECT 1 as num")
        assert result.rows[0]["num"] == 1
    finally:
        await executor.disconnect()
```

### Test Fixtures

**conftest.py patterns:**

```python
@pytest.fixture
def mock_executor():
    """Mock QueryExecutor with common setup."""
    executor = AsyncMock(spec=QueryExecutor)
    executor.execute.return_value = QueryResult(
        rows=[], row_count=0, fields=[]
    )
    return executor

@pytest.fixture
def mock_session_manager():
    """Mock SessionManager."""
    manager = MagicMock(spec=SessionManager)
    manager.create_session.return_value = "test-session-id"
    return manager

@pytest.fixture
def mock_context(mock_executor, mock_session_manager):
    """Complete ActionContext mock."""
    return ActionContext(
        executor=mock_executor,
        session_manager=mock_session_manager,
    )
```

---

## FastMCP Architecture

### Server Initialization Flow

1. **Create FastMCP instance** with lifespan
2. **Lifespan starts**: Initialize ActionContext
3. **Import tools**: `@mcp.tool()` decorators register tools
4. **Server runs**: Accept MCP requests

### Dependency Injection Flow

1. **Request arrives** → MCP protocol parsing
2. **Tool invoked** → FastMCP identifies injected parameters
3. **Dependencies resolved**:
   - `CurrentContext()` → Active MCP Context
   - `CurrentActionContext()` → From server lifespan
   - `Depends()` → Custom providers
4. **Tool executes** with all dependencies
5. **Cleanup** → AsyncExitStack unwinds

### Action Handler Pattern

Tools dispatch to action handlers via registries:

```python
# Tool (coldquery/tools/pg_query.py)
QUERY_ACTIONS = {
    "read": read_handler,
    "write": write_handler,
    "explain": explain_handler,
    "transaction": transaction_handler,
}

@mcp.tool()
async def pg_query(
    action: Literal["read", "write", "explain", "transaction"],
    sql: str | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    handler = QUERY_ACTIONS.get(action)
    return await handler(params, context)
```

**Benefits:**
- Single tool in MCP schema
- Type-safe action dispatch
- Easy to add new actions
- Clean separation of concerns

### Custom Dependency Creation

Pattern for creating injectable dependencies:

```python
# 1. Define the dependency class
class _CurrentActionContext(Dependency):
    async def __aenter__(self) -> ActionContext:
        server = get_server()  # From FastMCP
        return server._lifespan_result["action_context"]

    async def __aexit__(self, *args):
        pass

# 2. Create public function
def CurrentActionContext() -> ActionContext:
    return cast(ActionContext, _CurrentActionContext())

# 3. Use in tools
@mcp.tool()
async def my_tool(ctx: ActionContext = CurrentActionContext()) -> str:
    return await ctx.executor.execute("SELECT 1")
```

---

## Common Tasks

### Adding a New Tool

1. **Create tool file**:

```python
# coldquery/tools/pg_backup.py
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.server import mcp

@mcp.tool()
async def pg_backup(
    table_name: str,
    backup_location: str,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Backup a PostgreSQL table."""
    # Implementation
    return f"Backed up {table_name} to {backup_location}"
```

2. **Add tests**:

```python
# tests/test_pg_backup.py
import pytest
from coldquery.tools.pg_backup import pg_backup

@pytest.mark.asyncio
async def test_pg_backup_success(mock_context):
    result = await pg_backup(
        table_name="users",
        backup_location="/backups/users.sql",
        context=mock_context,
    )
    assert "Backed up" in result
```

3. **Import in server** (if not using decorator):

```python
# coldquery/server.py (in __main__ block)
if __name__ == "__main__":
    from coldquery.tools import pg_backup  # noqa: F401
    server.run()
```

### Adding a New Action to Existing Tool

1. **Create handler**:

```python
# coldquery/actions/query/upsert.py
async def upsert_handler(params: dict, context: ActionContext) -> str:
    """Handle upsert operations."""
    sql = params.get("sql")
    # Implementation
    return json.dumps(result.to_dict())
```

2. **Register in tool**:

```python
# coldquery/tools/pg_query.py
from coldquery.actions.query.upsert import upsert_handler

QUERY_ACTIONS = {
    "read": read_handler,
    "write": write_handler,
    "explain": explain_handler,
    "transaction": transaction_handler,
    "upsert": upsert_handler,  # Add here
}
```

3. **Update type hints**:

```python
@mcp.tool()
async def pg_query(
    action: Literal["read", "write", "explain", "transaction", "upsert"],  # Add here
    ...
) -> str:
```

### Modifying the Database Schema

For testing, you can use migrations or direct SQL:

```python
# tests/test_with_custom_schema.py
@pytest.mark.asyncio
async def test_with_temp_table():
    executor = AsyncpgPoolExecutor()

    try:
        # Setup
        await executor.execute("""
            CREATE TEMP TABLE test_data (
                id SERIAL PRIMARY KEY,
                value TEXT
            )
        """)

        # Test
        await executor.execute(
            "INSERT INTO test_data (value) VALUES ($1)",
            ["test"]
        )

        result = await executor.execute("SELECT * FROM test_data")
        assert len(result.rows) == 1

    finally:
        await executor.disconnect()
```

### Debugging

**Enable verbose logging:**

```bash
DEBUG=true python -m coldquery.server
```

**Add debug statements:**

```python
from coldquery.core.logger import logger

@mcp.tool()
async def my_tool(x: int) -> str:
    logger.debug({"message": "Tool called", "x": x})
    result = await do_work(x)
    logger.debug({"message": "Tool completed", "result": result})
    return result
```

**Interactive debugging with pdb:**

```python
import pdb; pdb.set_trace()
```

**VS Code debugger** - `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "ColdQuery Server",
      "type": "python",
      "request": "launch",
      "module": "coldquery.server",
      "console": "integratedTerminal",
      "env": {
        "DB_HOST": "localhost",
        "DB_PORT": "5433"
      }
    }
  ]
}
```

---

## Troubleshooting

### Tests Failing

**Issue**: `ImportError: cannot import name 'pg_query'`

**Solution**: Circular import. Check import order in `server.py` and `pg_query.py`.

```python
# ❌ Bad - circular import
# server.py
from coldquery.tools.pg_query import pg_query

# pg_query.py
from coldquery.server import mcp

# ✅ Good - import tools only in __main__
# server.py
if __name__ == "__main__":
    from coldquery.tools import pg_query
    server.run()
```

**Issue**: `RuntimeError: No active context found`

**Solution**: Dependency not available. Check lifespan setup:

```python
@asynccontextmanager
async def lifespan(server: FastMCP):
    action_context = ActionContext(executor=db_executor, session_manager=session_manager)
    yield {"action_context": action_context}  # Must yield dict
```

**Issue**: `TypeError: tool() got an unexpected keyword argument 'mcp_context'`

**Solution**: Parameter name changed from `mcp_context` to `context`. Update tests:

```python
# ❌ Old
await pg_query(action="read", mcp_context=mock_context)

# ✅ New
await pg_query(action="read", context=mock_context)
```

### Database Connection Issues

**Issue**: `asyncpg.exceptions.CannotConnectNowError`

**Solution**: Database not running or wrong credentials.

```bash
# Check database
docker compose ps

# Restart database
docker compose down
docker compose up -d

# Check environment variables
echo $DB_HOST $DB_PORT $DB_USER
```

### Server Won't Start

**Issue**: `AttributeError: 'FastMCP' object has no attribute 'context_provider'`

**Solution**: Using wrong FastMCP API. Use lifespan parameter, not decorator:

```python
# ❌ Wrong
@mcp.context_provider
async def context_provider():
    ...

# ✅ Correct
@asynccontextmanager
async def lifespan(server: FastMCP):
    yield {"action_context": ...}

mcp = FastMCP(name="coldquery", lifespan=lifespan)
```

---

## Code Style

### Formatting

We use Ruff for formatting and linting:

```bash
# Format code
ruff format coldquery/ tests/

# Check for issues
ruff check coldquery/ tests/

# Auto-fix issues
ruff check --fix coldquery/ tests/
```

### Type Hints

All functions should have type hints:

```python
# ✅ Good
async def my_function(x: int, y: str | None = None) -> str:
    return f"{x}: {y}"

# ❌ Bad - no type hints
async def my_function(x, y=None):
    return f"{x}: {y}"
```

Run mypy to check types:

```bash
mypy coldquery/
```

### Docstrings

Use Google-style docstrings:

```python
async def execute_query(sql: str, params: list | None = None) -> QueryResult:
    """Execute a SQL query with optional parameters.

    Args:
        sql: The SQL query string to execute
        params: Optional list of query parameters

    Returns:
        QueryResult containing rows, row count, and field metadata

    Raises:
        ValueError: If SQL is empty or invalid
        asyncpg.PostgresError: If query execution fails

    Example:
        >>> result = await execute_query("SELECT * FROM users WHERE id = $1", [123])
        >>> print(result.rows[0]["name"])
    """
    # Implementation
```

### Naming Conventions

- **Functions/methods**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: Prefix with `_`

```python
# Constants
MAX_SESSIONS = 10
DEFAULT_TTL = 30 * 60

# Class
class ActionContext:
    pass

# Functions
async def execute_query():
    pass

# Private
def _internal_helper():
    pass
```

### Import Order

1. Standard library
2. Third-party packages
3. Local imports

```python
# Standard library
import json
import sys
from contextlib import asynccontextmanager

# Third-party
from fastmcp import FastMCP, Context
import asyncpg

# Local
from coldquery.core.executor import db_executor
from coldquery.dependencies import CurrentActionContext
```

---

## Resources

- [FastMCP API Patterns](./fastmcp-api-patterns.md)
- [FastMCP Documentation](https://gofastmcp.com)
- [MCP Specification](https://modelcontextprotocol.io)
- [pytest Documentation](https://docs.pytest.org/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
