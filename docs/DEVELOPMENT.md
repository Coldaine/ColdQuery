# ColdQuery Development Guide

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Start test database
docker compose up -d

# Run tests
pytest tests/

# Run server (stdio)
python -m coldquery.server

# Run server (HTTP for debugging)
python -m coldquery.server --transport http
# Health check: curl http://localhost:19002/health
```

## Project Structure

```
coldquery/
  app.py          # FastMCP instance (import mcp from here!)
  server.py       # Entry point, imports tools
  tools/          # MCP tools (pg_query, pg_tx, pg_schema, pg_admin, pg_monitor)
  actions/        # Action handlers grouped by tool
  core/           # Executor, session manager, context
  dependencies.py # CurrentActionContext() dependency
tests/
  unit/           # Fast tests with mocks
  integration/    # Tests requiring PostgreSQL
```

## Key Patterns

### Tool Registration

Tools import `mcp` from `app.py` and use decorators:

```python
from coldquery.app import mcp  # ALWAYS import from app, not server!
from coldquery.dependencies import CurrentActionContext

@mcp.tool()
async def my_tool(
    action: Literal["read", "write"],
    context: ActionContext = CurrentActionContext(),
) -> str:
    # dispatch to action handlers
    ...
```

### Writing Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from coldquery.core.context import ActionContext

@pytest.mark.asyncio
async def test_my_handler():
    # Mock the executor
    mock_executor = AsyncMock()
    mock_executor.execute.return_value = QueryResult(rows=[{"id": 1}], row_count=1, fields=[])

    ctx = ActionContext(executor=mock_executor, session_manager=MagicMock())

    result = await my_handler({"sql": "SELECT 1"}, ctx)

    assert "rows" in result
```

## VS Code Setup

`.vscode/settings.json`:
```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "python.testing.pytestEnabled": true
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5433 | PostgreSQL port |
| `DB_USER` | mcp | Database user |
| `DB_PASSWORD` | mcp | Database password |
| `DB_DATABASE` | mcp_test | Database name |
| `PORT` | 19002 | HTTP server port |

## Resources

- [FastMCP Patterns](./fastmcp-api-patterns.md) - Dependency injection details
- [FastMCP Docs](https://gofastmcp.com)
- [MCP Specification](https://modelcontextprotocol.io)
