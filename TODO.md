# ColdQuery TODO

**Last Updated**: 2026-02-01

---

## High Priority

### Fix FastMCP 3.0 HTTP Transport Bug 🔴

**Status**: BLOCKED - Investigating
**Branch**: `fix/fastmcp-http-transport-investigation`
**Report**: `docs/reports/2026-02-01-deployment-investigation.md`

**Problem**: FastMCP 3.0.0b1's HTTP transport returns empty tools list (`{"tools":[]}`) despite all 5 tools being correctly registered internally.

**Evidence**:
- Tools ARE registered (verified via `mcp.list_tools()` in container)
- Health endpoint works (`/health` returns `{"status":"ok"}`)
- MCP initialize works (returns session ID)
- BUT: `tools/list` returns empty array via HTTP

**Action Items**:
- [ ] Debug FastMCP HTTP handler code path
- [ ] Try SSE transport instead: `mcp.run(transport="sse")`
- [ ] File bug report with FastMCP maintainers
- [ ] Monitor FastMCP 3.0 stable release

---

## Medium Priority

### Fix Integration Test Suite (Phase 4) 🟡

**Status**: FAILING (13 tests written, 10 failing)
**Location**: `tests/integration/`
**Related**: GitHub Issue #29

**Problems**:
1. Event loop management issues
2. Connection lifecycle bugs
3. API mismatch (`get_all_sessions` → `list_sessions`)

**Action Items**:
- [ ] Fix event loop scope for session-scoped fixtures
- [ ] Review asyncpg connection cleanup patterns
- [ ] Change `get_all_sessions()` to `list_sessions()` in test

---

## Low Priority

### Testing Improvements

- [ ] Add property-based tests (Hypothesis) for identifier sanitization
- [ ] Add mutation testing (mutmut) to verify test strength
- [ ] Increase coverage from ~82% to 90%+
- [ ] Add E2E tests with real MCP client

### Documentation

- [ ] Add API documentation with examples for each tool
- [ ] Create tutorial: "Building an MCP Tool with ColdQuery"
- [ ] Add troubleshooting guide for common errors

### Features

- [ ] Query result caching layer
- [ ] Connection pool metrics and monitoring
- [ ] Query timeout configuration per-tool
- [ ] Custom SQL template support

---

## Completed ✅

- [x] Phase 0: Project scaffolding
- [x] Phase 1: Core infrastructure (30 unit tests)
- [x] Phase 2: pg_query tool (17 unit tests)
- [x] Phase 3: Full tool suite - pg_tx, pg_schema, pg_admin, pg_monitor (24 unit tests)
- [x] Phase 5: Docker, CI/CD, Raspberry Pi deployment
- [x] FastMCP 3.0 migration
- [x] Default-Deny write policy
- [x] SQL injection prevention (identifier sanitization)
- [x] Session management with TTL
- [x] Action registry pattern
- [x] Comprehensive documentation (CHANGELOG, STATUS, CLAUDE.md)
- [x] Legacy TypeScript code cleanup (92 files removed)

---

## Technical Debt

### Code Quality
- Event loop fixtures need proper async context management
- Connection cleanup needs better error handling
- SessionManager API inconsistency (list_sessions vs get_all_sessions)

### Testing
- Integration tests fail due to async bugs
- No E2E tests with real MCP client
- Missing concurrency stress tests
- No connection leak tests under load

### Documentation
- Need better API reference
- Missing deployment runbook
- No troubleshooting guide for production issues

---

## Notes

- **Primary blocker**: FastMCP 3.0 HTTP transport bug - tools don't appear via HTTP
- All 71 unit tests pass - core functionality is solid
- Server is deployed and running on Raspberry Pi, but MCP clients can't see tools
- Integration tests are INTENTIONALLY failing - they document real bugs
- See investigation report: `docs/reports/2026-02-01-deployment-investigation.md`
