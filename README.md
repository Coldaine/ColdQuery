# ColdQuery

A secure, stateful PostgreSQL Model Context Protocol (MCP) server optimized for Agentic AI workflows. Built with **FastMCP 3.0** (Python).

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/Coldaine/ColdQuery.git
cd ColdQuery
pip install -e .

# 2. Start test database
docker compose up -d

# 3. Run tests
pytest tests/

# 4. Run server
python -m coldquery.server
```

## Installation

### From Source

```bash
pip install -e .
```

### Development Dependencies

```bash
pip install -e ".[dev]"
```

## Key Features

- **Transactional Safety:** "Default-Deny" write policy prevents accidental data corruption
- **Stateful Sessions:** Persistent database connections for multi-step reasoning
- **Batch Operations:** Atomic multi-statement execution via `pg_query:transaction`
- **LLM Ergonomics:** Active session hints and discovery (`pg_tx:list`)
- **Secure by Design:** Destructive session cleanup and connection pooling
- **FastMCP 3.0:** Modern Python MCP server with dependency injection

## Available Tools

| Tool | Purpose | Actions |
|------|---------|---------|
| `pg_query` | Data manipulation (DML) | `read`, `write`, `explain`, `transaction` |
| `pg_schema` | Schema management (DDL) | `list`, `describe`, `create`, `alter`, `drop` |
| `pg_admin` | Database maintenance | `vacuum`, `analyze`, `reindex`, `stats`, `settings` |
| `pg_tx` | Transaction control | `begin`, `commit`, `rollback`, `savepoint`, `release`, `list` |
| `pg_monitor` | Observability | `health`, `activity`, `connections`, `locks`, `size` |

## Transactional Safety Guide

The **Default-Deny** policy prevents silent failures where an AI agent intends to use a transaction but forgets the `session_id`.

### Simple Writes (Autocommit)

For single-statement updates where a transaction isn't needed:

```json
{
  "action": "write",
  "sql": "UPDATE users SET status = 'active' WHERE id = 1",
  "autocommit": true
}
```

### Multi-Step Transactions

For complex workflows involving multiple queries:

```json
// 1. Begin transaction
{"action": "begin"}
// Response: {"session_id": "tx_abc123"}

// 2. Use session_id for all operations
{"action": "write", "sql": "UPDATE ...", "session_id": "tx_abc123"}
{"action": "write", "sql": "INSERT ...", "session_id": "tx_abc123"}

// 3. Commit or rollback
{"action": "commit", "session_id": "tx_abc123"}
```

### Atomic Batch Writes

For multiple statements that should succeed or fail together:

```json
{
  "action": "transaction",
  "operations": [
    {"sql": "INSERT INTO logs (msg) VALUES ($1)", "params": ["started"]},
    {"sql": "UPDATE status SET val = $1", "params": ["running"]}
  ]
}
```

## Session Lifecycle

- **TTL:** Sessions auto-rollback after 30 minutes of inactivity
- **Limits:** Maximum 10 concurrent sessions (configurable)
- **Cleanup:** Connections destroyed on close (no state leakage)

## Configuration

Environment variables:

```bash
# Database Connection
DB_HOST=localhost
DB_PORT=5433
DB_USER=mcp
DB_PASSWORD=mcp
DB_DATABASE=mcp_test

# Server Settings
HOST=0.0.0.0
PORT=3000

# Debug Mode
DEBUG=false
```

## Documentation

### Core Documentation

| Document | Description |
|----------|-------------|
| [docs/fastmcp-api-patterns.md](docs/fastmcp-api-patterns.md) | FastMCP 3.0 API patterns and dependency injection |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local setup, testing, debugging |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and design decisions |
| [docs/MIGRATION.md](docs/MIGRATION.md) | Migration from TypeScript to Python |

### API Reference

| Document | Description |
|----------|-------------|
| [docs/TOOL_REFERENCE.md](docs/TOOL_REFERENCE.md) | Complete tool API reference |
| [docs/SECURITY.md](docs/SECURITY.md) | Security model and threat analysis |

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=coldquery --cov-report=html

# Run specific test file
pytest tests/test_pg_query.py

# Run with verbose output
pytest tests/ -v

# Run tests matching a pattern
pytest tests/ -k "test_write"
```

## Running the Server

### stdio (for MCP clients)

```bash
python -m coldquery.server
```

### HTTP (for development/debugging)

```bash
python -m coldquery.server --transport http
```

The server will start on `http://0.0.0.0:3000` by default.

### Custom Configuration

```bash
# Custom database
DB_HOST=prod-db.example.com DB_PORT=5432 python -m coldquery.server

# Custom HTTP port
HOST=127.0.0.1 PORT=8080 python -m coldquery.server --transport http
```

## Development

### Project Structure

```
coldquery/
  __init__.py
  server.py              # FastMCP server and tool registration
  dependencies.py        # Custom dependency injection
  config.py             # Environment variable configuration
  core/
    executor.py         # Database connection and query execution
    session.py          # Session management (TTL, max sessions)
    context.py          # ActionContext for handler functions
    logger.py           # Structured logging
  security/
    identifiers.py      # SQL identifier sanitization
    access_control.py   # Default-Deny write policy
  tools/
    pg_query.py         # Main query tool with action registry
  actions/
    query/              # Query action handlers (read, write, explain, transaction)
  middleware/
    session_echo.py     # Session metadata in responses
tests/
  conftest.py           # Shared test fixtures
  test_*.py             # Unit tests for each module
  integration/          # Integration tests
```

### Adding a New Tool

1. Create the tool function in `coldquery/tools/`:

```python
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.server import mcp

@mcp.tool()
async def my_new_tool(
    param1: str,
    param2: int = 10,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Tool description for MCP schema."""
    # Your implementation
    return "result"
```

2. The `@mcp.tool()` decorator automatically registers the tool
3. Write tests in `tests/test_my_new_tool.py`

### Adding a New Action Handler

1. Create handler in `coldquery/actions/<category>/`:

```python
async def my_handler(params: dict, context: ActionContext) -> str:
    """Handle the action."""
    param1 = params.get("param1")
    # Your logic here
    result = await context.executor.execute("SELECT ...")
    return json.dumps(result.to_dict())
```

2. Register in the action registry (e.g., `pg_query.py`):

```python
QUERY_ACTIONS = {
    "read": read_handler,
    "write": write_handler,
    "my_action": my_handler,  # Add here
}
```

## Docker Deployment

Build and run with Docker:

```bash
# Build image
docker build -t coldquery:latest .

# Run container
docker run -p 3000:3000 \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5433 \
  coldquery:latest
```

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

- **Issues**: https://github.com/Coldaine/ColdQuery/issues
- **Discussions**: https://github.com/Coldaine/ColdQuery/discussions
