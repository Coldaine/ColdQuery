# ColdQuery vs pgEdge Postgres MCP Server — Comparison Report

**Date**: 2026-02-05
**pgEdge Repo**: https://github.com/pgEdge/pgedge-postgres-mcp
**pgEdge Version**: 1.0.0-beta3 (Go 1.24)
**ColdQuery Version**: 1.0.0 (Python 3.12+, FastMCP 3.0)

---

## At a Glance

| Dimension | ColdQuery | pgEdge |
|-----------|-----------|--------|
| Language | Python 3.12+ | Go 1.24 |
| MCP Framework | FastMCP 3.0 | Custom (MCP protocol from scratch) |
| PostgreSQL Driver | asyncpg | pgx v5 |
| Transport | stdio + HTTP (FastMCP) | stdio + HTTP (custom JSON-RPC) |
| License | — | PostgreSQL License |
| Design Philosophy | Focused DBA toolkit, stateful | Broad AI-database platform, stateless |

---

## Tool Comparison

| Capability | ColdQuery | pgEdge |
|------------|-----------|--------|
| Query execution | `pg_query` (read/write/explain/transaction) | `query_database` + `execute_explain` |
| Transaction control | `pg_tx` (begin/commit/rollback/savepoint) | **None** (per-query only) |
| Schema introspection | `pg_schema` (list/describe/create/alter/drop) | `get_schema_info` |
| Admin/maintenance | `pg_admin` (vacuum/analyze/reindex/stats/settings) | **None** |
| Monitoring | `pg_monitor` (health/activity/connections/locks/size) | **None** (basic `pg://system_info` resource) |
| Vector/semantic search | **None** | `similarity_search` (BM25 + MMR + pgvector) |
| Embedding generation | **None** | `generate_embedding` |
| Knowledgebase search | **None** | `search_knowledgebase` |
| Row counting | Via `pg_query` | `count_rows` (dedicated) |
| Multi-database switching | **None** | `select_database_connection` |
| Custom tools | **None** | YAML-defined SQL/PL tools |

ColdQuery: **5 tools, 25 actions**. pgEdge: **10+ tools**, broader surface area.

---

## Where ColdQuery Is Stronger

### 1. Stateful Transaction Sessions (Major Differentiator)

`pg_tx` lets the LLM `begin` a transaction, receive a `session_id`, run multiple
operations against the same connection, and `commit` or `rollback`. pgEdge has no
equivalent — every tool call is an independent auto-committed transaction.

This matters for multi-step workflows: "insert a row, check something, update
another row, all atomically" is impossible with pgEdge.

### 2. Savepoint Support

Full `SAVEPOINT`, `RELEASE`, and `ROLLBACK TO SAVEPOINT` within sessions. pgEdge
has no savepoint support.

### 3. Database Administration Tools

ColdQuery exposes `VACUUM`, `ANALYZE`, `REINDEX`, PostgreSQL settings management,
and table statistics via `pg_admin`. pgEdge has none of these.

### 4. Monitoring & Observability

`pg_monitor` exposes `pg_stat_activity`, connection stats, lock info, and database
sizes. pgEdge has only a basic `pg://system_info` resource.

### 5. Schema DDL Operations

`pg_schema` supports `create`, `alter`, and `drop` as dedicated actions with
identifier sanitization. pgEdge relies on the LLM writing raw DDL via
`query_database`.

### 6. Batch Atomic Execution

`pg_query action=transaction` accepts an array of operations and executes them
atomically (all-or-nothing). pgEdge has no batch execution mechanism.

### 7. Session Metadata Hints

Middleware enriches responses with session expiry warnings, guiding the LLM to
commit before timeouts.

---

## Where pgEdge Is Stronger

### 1. Semantic/Vector Search (Major Feature)

`similarity_search` is a sophisticated pipeline: pgvector distance → BM25 lexical
re-ranking → MMR diversity filtering. Multiple embedding providers (OpenAI, Voyage AI,
Ollama) and token budgeting for output. ColdQuery has nothing comparable.

### 2. Knowledgebase System

A `kb-builder` CLI creates SQLite-based documentation indexes searchable via
`search_knowledgebase`. The LLM can query product docs alongside database data.

### 3. Multi-Database Support

Up to 10 named databases with per-token isolation and LLM-switchable connections.
ColdQuery connects to a single database.

### 4. Custom Tool Definitions (YAML)

Users define custom tools via YAML — SQL queries, PL/pgSQL DO blocks, or temporary
functions — with full JSON Schema parameter definitions. No code changes required.

### 5. Authentication & Rate Limiting

Mature auth: SHA256-hashed tokens (constant-time comparison), user/password auth,
per-IP rate limiting (15-min window, 10 attempts, lockout), per-user database ACLs,
timing-attack-resistant error messages. ColdQuery has placeholder auth disabled by
default.

### 6. Context-Aware Tool Descriptions

Tool descriptions dynamically change based on the connected database's capabilities
(e.g., write access status). The LLM sees different schemas depending on context.

### 7. EXPLAIN Analyzer

Beyond raw `EXPLAIN ANALYZE`, pgEdge detects performance issues (sequential scans,
hash join spills, cache misses, sort disk spillage) and generates recommendations.

### 8. Hot Configuration Reload

SIGHUP-triggered config reload for database configurations without server restart.

### 9. Web UI + LLM Proxy

React-based web interface and built-in LLM proxy (Anthropic, OpenAI, Ollama).

### 10. Context Compaction

Built-in token counting and LLM-based summarization for managing conversation context.

---

## Security Model Comparison

| Aspect | ColdQuery | pgEdge |
|--------|-----------|--------|
| Default posture | Default-deny (writes blocked unless `session_id` or `autocommit=true`) | Read-only transactions (`SET TRANSACTION READ ONLY`) |
| Write authorization | Per-statement (session or autocommit flag) | Per-database config (`AllowWrites`) |
| SQL identifier safety | `sanitize_identifier()` with validation + double-quoting | `quoteIdentifier()` with double-quoting |
| Auth | Placeholder token auth (disabled) | Token + user/password + rate limiting + lockout |
| Token storage | Environment variable | YAML file (0600 perms), SHA256-hashed |
| Per-user DB access | No | Yes, per-user ACLs |

ColdQuery's per-statement write control is more granular — the LLM must explicitly
opt in to each write. pgEdge's per-database flag is coarser but simpler to configure.

---

## Architecture Differences

| Aspect | ColdQuery | pgEdge |
|--------|-----------|--------|
| Complexity | ~2,000 LOC production | Significantly larger (Go + React UI) |
| State management | Stateful (session-based transactions) | Stateless (per-query transactions) |
| Configuration | Environment variables only | YAML + env vars + CLI flags (hierarchical) |
| Testing | 71 unit tests, 13 integration tests | Go `testing` package, per-file test coverage |
| Deployment | Docker + Raspberry Pi + Tailscale | Docker Compose, multiple database support |

---

## Actionable Takeaways for ColdQuery

### Features worth considering

1. **Multi-database support** — connect to and switch between multiple databases
2. **EXPLAIN output analysis** — auto-detect performance issues, generate recommendations
3. **Custom tool definitions** — YAML or similar declarative tool creation
4. **Stronger authentication** — rate limiting, per-user ACLs, hashed token storage
5. **Context-aware tool descriptions** — dynamic schemas based on connection capabilities

### ColdQuery advantages to preserve and promote

1. **Stateful transactions** — this is genuinely unique among PostgreSQL MCP servers
2. **Database administration tools** — `VACUUM`, `ANALYZE`, `REINDEX`, settings
3. **Active monitoring** — `pg_stat_activity`, locks, connections, sizes
4. **Schema DDL as structured actions** — safer than raw DDL via query tool
5. **Batch atomic execution** — array of operations in single transaction
