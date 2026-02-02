# Claude Code Instructions for ColdQuery

## Project Overview

**ColdQuery** is a secure, stateful PostgreSQL Model Context Protocol (MCP) server built with **FastMCP 3.0** (Python). It provides a safe, transaction-aware interface for AI agents to interact with PostgreSQL databases.

**Key Features:**
- Default-Deny write policy to prevent accidental data corruption
- Stateful transaction sessions with automatic TTL and cleanup
- SQL injection prevention via identifier sanitization
- FastMCP 3.0 dependency injection patterns
- Comprehensive test suite (unit + integration tests)

---

## Development Workflow

### Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only (fast, no database required)
pytest tests/unit/ -v

# Integration tests only (requires PostgreSQL)
pytest tests/integration/ -v

# With coverage
pytest tests/ --cov=coldquery --cov-report=html
```

### Starting the Server

```bash
# stdio mode (for MCP clients)
python -m coldquery.server

# HTTP mode (for testing/debugging)
python -m coldquery.server --transport http
```

### Docker Compose (Local Development)

```bash
# Start PostgreSQL + server
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Architecture Guidelines

### 1. FastMCP 3.0 Patterns

**Tool Registration** - Use decorator, no manual registration:
```python
from coldquery.server import mcp
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext

@mcp.tool()
async def my_tool(
    param1: str,
    param2: int = 10,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Tool description for MCP schema."""
    # Implementation
    return result
```

**Resource Registration**:
```python
@mcp.resource("postgres://schema/{schema}/{table}")
async def table_resource(schema: str, table: str, ctx: ActionContext = CurrentActionContext()) -> str:
    """Resource description."""
    # Implementation
```

**Prompt Registration**:
```python
@mcp.prompt()
async def analyze_query(sql: str) -> list:
    """Prompt description."""
    return [{"role": "user", "content": f"Analyze: {sql}"}]
```

### 2. Action Registry Pattern

Tools use action-based dispatch:
```python
TOOL_ACTIONS = {
    "action1": handler1,
    "action2": handler2,
}

@mcp.tool()
async def my_tool(
    action: Literal["action1", "action2"],
    context: ActionContext = CurrentActionContext(),
) -> str:
    handler = TOOL_ACTIONS.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")
    return await handler(params, context)
```

### 3. Security Requirements

**Always sanitize SQL identifiers**:
```python
from coldquery.security.identifiers import sanitize_identifier, sanitize_table_name

safe_table = sanitize_table_name("public.users")
safe_column = sanitize_identifier("user_id")
```

**Enforce Default-Deny for writes**:
```python
from coldquery.security.access_control import require_write_access

# In write handlers
require_write_access(session_id, autocommit)
```

**Use parameterized queries**:
```python
# GOOD
await executor.execute("SELECT * FROM users WHERE id = $1", [user_id])

# BAD - SQL injection risk
await executor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### 4. Testing Standards

**Unit Tests** (tests/unit/):
- Fast, use mocks
- Test business logic, not database behavior
- Test error conditions

**Integration Tests** (tests/integration/):
- Real PostgreSQL connections
- Test actual ACID properties
- Test transaction isolation
- Test connection management

```python
# Integration test example
@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_workflow(real_context):
    # Use real ActionContext with real database
    result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(result)["session_id"]

    await pg_query(
        action="write",
        sql="INSERT INTO test (val) VALUES ($1)",
        params=["test"],
        session_id=session_id,
        context=real_context,
    )

    await pg_tx(action="commit", session_id=session_id, context=real_context)
```

---

## Documentation Maintenance

### Updating CHANGELOG.md

**When to update**: After completing features, fixing bugs, or merging PRs.

**Format** (follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)):

```markdown
## [Version] - YYYY-MM-DD

### Added
- New feature description (PR #XX)

### Changed
- Modified behavior description (PR #XX)

### Fixed
- Bug fix description (PR #XX)

### Security
- Security-related change description (PR #XX)
```

**Example**:
```markdown
## [1.1.0] - 2026-02-15

### Added
- pg_backup tool for database backup operations (PR #35)
- Support for custom isolation levels in pg_tx:begin (PR #36)

### Fixed
- Connection leak in session cleanup (PR #37)
- Incorrect error handling in transaction rollback (PR #38)
```

**Guidelines**:
1. Use semantic versioning (MAJOR.MINOR.PATCH)
2. MAJOR: Breaking API changes
3. MINOR: New features (backward compatible)
4. PATCH: Bug fixes (backward compatible)
5. Include PR numbers for traceability
6. Write user-focused descriptions (not technical details)
7. Group changes by category (Added, Changed, Fixed, etc.)

### Documentation Files

- `README.md` - User-facing documentation, installation, Quick Start
- `CHANGELOG.md` - Version history and release notes
- `STATUS.md` - Current project status and known issues
- `TODO.md` - Task tracking and blockers
- `docs/DEVELOPMENT.md` - Developer setup and testing
- `docs/DEPLOYMENT.md` - Production deployment guide
- `docs/fastmcp-api-patterns.md` - FastMCP 3.0 API reference
- `docs/MIGRATION.md` - TypeScript to Python migration notes
- `docs/archive/PHASE_*.md` - Historical phase plans

---

## Common Tasks

### Adding a New Tool

1. Create tool file in `coldquery/tools/`
2. Define action registry
3. Implement tool with `@mcp.tool()` decorator
4. Create action handlers in `coldquery/actions/`
5. Write unit tests in `tests/unit/test_<tool>.py`
6. Import tool in `coldquery/server.py`
7. Update README.md with new tool
8. Update CHANGELOG.md

### Adding a New Action Handler

1. Create handler function in appropriate `coldquery/actions/` subdirectory
2. Register in action registry
3. Implement handler following signature:
   ```python
   async def my_handler(params: dict, context: ActionContext) -> str:
       # Implementation
       return json.dumps(result)
   ```
4. Add unit tests
5. Update CHANGELOG.md

### Fixing a Bug

1. Create branch: `fix/description`
2. Write failing test that reproduces bug
3. Implement fix
4. Verify all tests pass
5. Update CHANGELOG.md under `[Unreleased] -> Fixed`
6. Create PR with clear description
7. After merge, update CHANGELOG.md with version and date

### Creating a Release

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md:
   - Change `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
   - Add new `[Unreleased]` section at top
3. Commit: `chore: Release vX.Y.Z`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push && git push --tags`

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `coldquery/server.py` | FastMCP server and tool registration |
| `coldquery/dependencies.py` | Custom dependency injection |
| `coldquery/core/executor.py` | Database connection and query execution |
| `coldquery/core/session.py` | Session management (TTL, limits) |
| `coldquery/core/context.py` | ActionContext for handlers |
| `coldquery/security/identifiers.py` | SQL identifier sanitization |
| `coldquery/security/access_control.py` | Default-Deny write policy |
| `coldquery/middleware/session_echo.py` | Session metadata in responses |
| `tests/conftest.py` | Shared test fixtures |
| `tests/unit/` | Fast tests with mocks |
| `tests/integration/` | Slow tests with real PostgreSQL |

---

## Troubleshooting

### Tests Failing

```bash
# Check database is running
docker-compose ps

# Restart database
docker-compose restart postgres

# View database logs
docker-compose logs postgres

# Run specific test
pytest tests/unit/test_pg_query.py::test_write_requires_auth -v
```

### Import Errors

```bash
# Reinstall in development mode
pip install -e .

# Verify installation
python -c "import coldquery; print(coldquery.__file__)"
```

### Type Checking Issues

```bash
# Run mypy
mypy coldquery/

# Fix common issues:
# - Add type hints to function signatures
# - Import types from typing module
# - Use Optional[T] for nullable parameters
```

### FastMCP HTTP Transport Bug (Known Issue)

**Problem**: FastMCP 3.0.0b1's HTTP transport returns empty tools list.

**Symptoms**:
- `tools/list` via HTTP returns `{"tools":[]}`
- Tools ARE registered internally (verified via `mcp.list_tools()`)
- Health endpoint works, MCP initialize works

**Workarounds being investigated**:
1. Try SSE transport: `mcp.run(transport="sse")`
2. Debug FastMCP HTTP handler code path
3. File bug report with FastMCP maintainers

See `docs/reports/2026-02-01-deployment-investigation.md` for full details.

---

## Project Status

See `STATUS.md` for current project status, completed phases, and known issues.

---

## Contact

- Issues: https://github.com/Coldaine/ColdQuery/issues
- Discussions: https://github.com/Coldaine/ColdQuery/discussions
