# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-01-21

### Fixed
- **Transport Layer**: Migrated from `StreamableHTTPServerTransport` to `SSEServerTransport` + `express` adapter to resolve "Server not initialized" errors on high-latency networks (Tailscale/Pi).
- **Deployment Security**: Hardened CI/CD pipeline by removing secrets from shell arguments and moving to encrypted `.env` file generation.
- **SSH Connectivity**: Fixed "Host key verification failed" in CI by implementing `webfactory/ssh-agent`.

### Changed
- **Server Architecture**: Switched to a Factory Pattern for the MCP server, creating isolated instances per connection for better multi-client stability.

## [0.2.0] - 2026-01-20

### Added
- **ARCHITECTURE.md** - Comprehensive documentation of design decisions and the "why" behind architectural choices
- **ROADMAP.md** - Future plans for pg_vector and pg_code extensions
- **SessionManager** - Session management with TTL for transaction support
- **Structured logging** - JSON-formatted Logger class writing to stderr (MCP-compliant)
- **pg_admin settings action** - List, get, and set PostgreSQL configuration
- **pg_monitor activity action** - Monitor active queries and connections
- **Streamable HTTP transport** - MCP 2025-11-25 spec with multi-client session routing (replaces SSE)
- **Acceptance test suite** - 10 E2E tests covering all tools via HTTP transport
- **Deployment test suite** - Black-box tests against remote PostgreSQL
- Inline "why" documentation throughout the codebase

### Changed
- Refactored to declarative plugin pattern for tool registration
- All console.error calls replaced with structured Logger
- DDL operations now use `sanitizeIdentifier()` for table/schema names
- Settings handler now sanitizes setting names to prevent SQL injection

### Fixed
- Race condition in SessionManager.createSession() - session now added to map before timer starts
- SQL injection vulnerability in settings.ts `SET` command
- `result.fields` undefined for DDL statements (CREATE/DROP SCHEMA, etc.)
- Unused imports removed across codebase

### Removed
- Stale documentation files (docs/plans/, docs/reports/)

### Security
- Added identifier sanitization to DDL operations
- Added identifier sanitization to SET command in settings handler
- Documented trust model for raw SQL in DDL definitions

## [0.1.0] - 2026-01-18

### Added
- Initial release
- Monorepo structure with npm workspaces
- Core tools: pg_query, pg_schema, pg_admin, pg_monitor, pg_tx
- QueryExecutor interface with PostgresExecutor implementation
- Identifier sanitization utilities in shared/security
- Basic test infrastructure
