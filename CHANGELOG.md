# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Phase 4: Integration Tests (FAILING - Known Bugs)
- **Integration test suite** with REAL PostgreSQL database (13 tests)
  - Tests transaction workflows (BEGIN/COMMIT/ROLLBACK)
  - Tests Default-Deny safety policy enforcement
  - Tests connection pool management
  - Tests transaction isolation between sessions
  - Tests concurrent session handling
- **Test organization**: Separated unit/ and integration/ test directories
- **KNOWN ISSUES**: Tests currently fail due to:
  - Event loop management bugs (fixture cleanup in wrong loop)
  - Connection lifecycle issues (double-close errors)
  - See TODO.md and docs/OBSERVATIONS.md for details
- **Rationale**: Committed failing tests to make technical debt visible
  - Tests document the CORRECT behavior we want
  - Bugs are in fixtures, not the tools themselves
  - Can be fixed incrementally without losing test structure

### In Progress
- Phase 5: Docker, CI/CD, and Raspberry Pi deployment (Issue #31)

## [1.0.0] - 2026-01-27

### Added - Phase 3: Full Tool Suite (PR #27)
- **pg_tx tool**: Transaction lifecycle management
  - `begin` - Create transaction session
  - `commit` - Commit and close transaction
  - `rollback` - Rollback and close transaction
  - `savepoint` - Create savepoint within transaction
  - `release` - Release savepoint
  - `list` - List active transaction sessions
- **pg_schema tool**: Schema introspection and DDL operations
  - `list` - List database objects (tables, views, schemas)
  - `describe` - Get detailed table structure
  - `create` - Create database objects
  - `alter` - Modify database objects
  - `drop` - Remove database objects
- **pg_admin tool**: Database administration and maintenance
  - `vacuum` - VACUUM tables
  - `analyze` - ANALYZE tables for query planning
  - `reindex` - Rebuild indexes
  - `stats` - Get table statistics
  - `settings` - Get/set configuration parameters
- **pg_monitor tool**: Observability and health monitoring
  - `health` - Database health check
  - `activity` - View active queries
  - `connections` - Connection statistics
  - `locks` - Lock information
  - `size` - Database and table sizes
- **MCP Resources**: Direct URI access to database metadata
  - `postgres://schema/tables` - List all tables
  - `postgres://schema/{schema}/{table}` - Table details
  - `postgres://monitor/health` - Health status
  - `postgres://monitor/activity` - Current activity
- **MCP Prompts**: Guided workflows for AI agents
  - `analyze_query_performance` - Query optimization guidance
  - `debug_lock_contention` - Lock debugging workflow
- All tools follow FastMCP 3.0 dependency injection patterns
- Comprehensive unit tests for all new tools (24 additional tests)

### Added - Phase 2: pg_query Tool (PR #25)
- **pg_query tool**: Core data manipulation with action-based dispatch
  - `read` - Execute SELECT queries
  - `write` - Execute INSERT/UPDATE/DELETE with safety checks
  - `explain` - Query plan analysis with EXPLAIN/ANALYZE
  - `transaction` - Atomic multi-statement execution
- FastMCP 3.0 tool registration with `@mcp.tool()` decorator
- Action registry pattern for extensible command dispatch
- Session echo middleware for transaction state awareness
- Unit tests for all query actions (17 tests)

### Added - Phase 1: Core Infrastructure (PR #23)
- **AsyncpgPoolExecutor**: Connection pool management with asyncpg
- **AsyncpgSessionExecutor**: Session-scoped connections for transactions
- **SessionManager**: Transaction session lifecycle with TTL
  - Automatic session expiry after 30 minutes of inactivity
  - Maximum 10 concurrent sessions (configurable via MAX_SESSIONS)
  - Proper connection cleanup on session close
- **ActionContext**: Dependency injection for tool handlers
- **Default-Deny write policy**: Prevents accidental writes without explicit authorization
  - Requires `session_id` (transactional) or `autocommit=true` (single statement)
  - Enforced via `require_write_access()` security check
- SQL identifier sanitization to prevent injection attacks
- Structured logging with configurable debug mode
- Environment-based configuration (DB_HOST, DB_PORT, etc.)
- FastMCP 3.0 custom dependency injection via `CurrentActionContext()`
- Comprehensive unit tests (30 tests for core infrastructure)

### Added - Phase 0: Project Scaffolding
- Project structure with `coldquery/` package
- Python 3.12+ FastMCP 3.0 server foundation
- Asyncpg PostgreSQL driver integration
- Test infrastructure with pytest and pytest-asyncio
- Development tooling: Ruff (linting), mypy (type checking)
- Docker Compose for local PostgreSQL test database
- README with Quick Start and installation instructions
- Comprehensive documentation:
  - `docs/fastmcp-api-patterns.md` - FastMCP 3.0 API guide
  - `docs/DEVELOPMENT.md` - Local development setup
  - `docs/MIGRATION.md` - TypeScript to Python migration notes

### Changed
- Migrated from TypeScript `@modelcontextprotocol/sdk` to Python `fastmcp` 3.0
- Replaced Express.js HTTP server with FastMCP's native HTTP transport
- Replaced TypeScript action handlers with Python async/await patterns

### Security
- SQL identifier validation (63 byte limit, alphanumeric + underscore only)
- SQL identifier sanitization with PostgreSQL quoting
- Default-Deny write policy to prevent accidental data loss
- Session-based transaction isolation
- No SQL string concatenation (parameterized queries only)

## [0.x.x] - Legacy TypeScript Version

Previous TypeScript implementation available in git history.
Refer to legacy commits for historical changes.

---

## Contributing to this Changelog

When completing features or merging PRs, update this file with:

1. **Version number** - Use semantic versioning (MAJOR.MINOR.PATCH)
2. **Date** - Use ISO 8601 format (YYYY-MM-DD)
3. **Category** - Added, Changed, Deprecated, Removed, Fixed, Security
4. **Description** - Clear, user-focused description of the change
5. **PR reference** - Link to the pull request (e.g., PR #27)

Example:
```markdown
## [1.1.0] - 2026-02-15

### Added
- New feature description (PR #42)

### Fixed
- Bug fix description (PR #43)
```

For guidelines, see [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
