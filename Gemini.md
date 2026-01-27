# Gemini Instructions for ColdQuery

This file contains instructions for Gemini AI when working on the ColdQuery project. For general project information, see `CLAUDE.md` or `README.md`.

## Quick Reference

**Project**: ColdQuery - PostgreSQL MCP Server (Python + FastMCP 3.0)
**Key Principle**: Default-Deny write policy for safety
**Architecture**: Action-based tool dispatch with dependency injection

---

## Development Commands

```bash
# Run tests
pytest tests/unit/ -v                    # Unit tests only
pytest tests/integration/ -v             # Integration tests (requires DB)
pytest tests/ --cov=coldquery           # With coverage

# Start server
python -m coldquery.server              # stdio mode
python -m coldquery.server --transport http  # HTTP mode

# Start database
docker-compose up -d
```

---

## Code Patterns

### Tool Definition (FastMCP 3.0)

```python
from coldquery.server import mcp
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from typing import Literal

TOOL_ACTIONS = {
    "action1": handler1,
    "action2": handler2,
}

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

### Action Handler

```python
import json
from typing import Dict, Any
from coldquery.core.context import ActionContext

async def my_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Handle the action."""
    param1 = params.get("param1")

    # Use executor for database queries
    result = await context.executor.execute("SELECT ...")

    return json.dumps(result.to_dict())
```

### Security - Sanitize Identifiers

```python
from coldquery.security.identifiers import sanitize_identifier, sanitize_table_name

# Always sanitize user input
safe_table = sanitize_table_name("public.users")  # Handles schema.table
safe_column = sanitize_identifier("user_id")

# Use parameterized queries
await executor.execute(
    f"SELECT {safe_column} FROM {safe_table} WHERE id = $1",
    [user_id]
)
```

### Security - Default-Deny for Writes

```python
from coldquery.security.access_control import require_write_access

async def write_handler(params: Dict[str, Any], context: ActionContext) -> str:
    session_id = params.get("session_id")
    autocommit = params.get("autocommit")

    # This will raise PermissionError if neither is provided
    require_write_access(session_id, autocommit)

    # Safe to execute write now
    await context.executor.execute(sql)
```

---

## Documentation Maintenance

### When Completing Features or Merging PRs

1. **Update CHANGELOG.md**:
   ```markdown
   ## [Unreleased]

   ### Added
   - New feature description (PR #XX)

   ### Fixed
   - Bug fix description (PR #XX)
   ```

2. **Follow Keep a Changelog format**:
   - Categories: Added, Changed, Deprecated, Removed, Fixed, Security
   - Include PR numbers
   - Use user-focused descriptions
   - Use ISO 8601 dates (YYYY-MM-DD)

3. **Version numbering** (Semantic Versioning):
   - MAJOR: Breaking changes
   - MINOR: New features (backward compatible)
   - PATCH: Bug fixes

### Before Creating a Release

1. Update `pyproject.toml` version
2. Update CHANGELOG.md:
   - Change `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
   - Add new `[Unreleased]` section
3. Run full test suite
4. Create release commit and tag

---

## Testing Guidelines

### Unit Tests (tests/unit/)
- Fast execution (< 1 second)
- Use mocks for database operations
- Test business logic, not database behavior
- Test error conditions

```python
@pytest.mark.asyncio
async def test_write_requires_auth(mock_context):
    with pytest.raises(PermissionError, match="Safety Check Failed"):
        await pg_query(action="write", sql="INSERT ...", context=mock_context)
```

### Integration Tests (tests/integration/)
- Use real PostgreSQL database
- Test actual ACID properties
- Test transaction isolation
- Test connection management

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_workflow(real_context):
    # real_context has real database connection
    result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(result)["session_id"]

    await pg_query(
        action="write",
        sql="INSERT INTO test (val) VALUES ($1)",
        params=["value"],
        session_id=session_id,
        context=real_context,
    )

    await pg_tx(action="commit", session_id=session_id, context=real_context)
```

---

## Common Mistakes to Avoid

1. **Don't bypass Default-Deny**:
   ```python
   # BAD - executes without safety check
   await executor.execute("DELETE FROM users")

   # GOOD - uses pg_query with autocommit or session_id
   await pg_query(action="write", sql="DELETE FROM users WHERE id = $1",
                  params=[1], autocommit=True, context=context)
   ```

2. **Don't concatenate SQL strings**:
   ```python
   # BAD - SQL injection risk
   sql = f"SELECT * FROM users WHERE name = '{name}'"

   # GOOD - parameterized query
   sql = "SELECT * FROM users WHERE name = $1"
   await executor.execute(sql, [name])
   ```

3. **Don't forget to sanitize identifiers**:
   ```python
   # BAD - user input directly in SQL
   await executor.execute(f"SELECT * FROM {table_name}")

   # GOOD - sanitized identifier
   safe_table = sanitize_table_name(table_name)
   await executor.execute(f"SELECT * FROM {safe_table}")
   ```

4. **Don't use manual tool registration**:
   ```python
   # BAD - manual registration (old FastMCP pattern)
   mcp.register(tool)

   # GOOD - decorator registration
   @mcp.tool()
   async def my_tool(...):
       ...
   ```

---

## Project Structure

```
coldquery/
  __init__.py
  server.py              # FastMCP server setup
  dependencies.py        # Custom DI
  core/
    executor.py          # Database connections
    session.py           # Session management
    context.py           # ActionContext
    logger.py            # Logging
  security/
    identifiers.py       # SQL sanitization
    access_control.py    # Default-Deny policy
  tools/                 # MCP tools
    pg_query.py          # Main query tool
    pg_tx.py             # Transaction control
    pg_schema.py         # Schema operations
    pg_admin.py          # Admin operations
    pg_monitor.py        # Monitoring
  actions/               # Action handlers
    query/               # Query actions
    tx/                  # Transaction actions
    schema/              # Schema actions
    admin/               # Admin actions
    monitor/             # Monitoring actions
  middleware/
    session_echo.py      # Session metadata
  resources/             # MCP resources
  prompts/               # MCP prompts

tests/
  unit/                  # Fast tests with mocks
  integration/           # Real database tests
```

---

## Key Files

- `coldquery/server.py` - Entry point, tool imports
- `coldquery/dependencies.py` - `CurrentActionContext()` DI
- `coldquery/core/executor.py` - Database query execution
- `coldquery/core/session.py` - Session lifecycle (TTL, limits)
- `coldquery/security/access_control.py` - `require_write_access()`
- `CHANGELOG.md` - Version history (update on PR merge)
- `README.md` - User documentation
- `CLAUDE.md` - Detailed agent instructions

---

## Resources

- FastMCP Docs: https://github.com/jlowin/fastmcp
- PostgreSQL Docs: https://www.postgresql.org/docs/
- MCP Specification: https://spec.modelcontextprotocol.io/
- Keep a Changelog: https://keepachangelog.com/

---

For more detailed information, see `CLAUDE.md`.
