# ColdQuery

A secure, stateful PostgreSQL Model Context Protocol (MCP) server optimized for Agentic AI workflows.

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/Coldaine/ColdQuery.git
cd ColdQuery
npm install

# 2. Start test database
docker compose up -d

# 3. Build and run tests
npm run build
npm test
```

## Key Features

- **Transactional Safety:** "Default-Deny" write policy prevents accidental data corruption
- **Stateful Sessions:** Persistent database connections for multi-step reasoning
- **Batch Operations:** Atomic multi-statement execution via `pg_transaction`
- **LLM Ergonomics:** Active session hints and discovery (`pg_tx:list`)
- **Secure by Design:** Destructive session cleanup and connection pooling

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

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and design decisions |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local setup, testing, debugging |
| [docs/TOOL_REFERENCE.md](docs/TOOL_REFERENCE.md) | Complete tool API reference |
| [docs/SECURITY.md](docs/SECURITY.md) | Security model and threat analysis |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guidelines |
| [DEPLOY.md](DEPLOY.md) | Deployment instructions |
| [.github/WORKFLOWS.md](.github/WORKFLOWS.md) | CI/CD pipeline documentation |

### Tool Descriptions

Detailed documentation for each tool:

- [pg_query](docs/toolDescriptions/pg_query.md) - Query execution and data manipulation
- [pg_schema](docs/toolDescriptions/pg_schema.md) - Schema introspection and DDL
- [pg_admin](docs/toolDescriptions/pg_admin.md) - Maintenance and administration
- [pg_tx](docs/toolDescriptions/pg_tx.md) - Transaction lifecycle management
- [pg_monitor](docs/toolDescriptions/pg_monitor.md) - Database observability

## Testing

```bash
# Run tests with automated database lifecycle
npm run test:ci

# Manual database management
docker compose up -d
npm test
docker compose down
```

## License

MIT
