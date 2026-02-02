# ColdQuery TODO

**Last Updated**: 2026-02-02

---

## High Priority

### Verify E2E with Claude Code 🟡

**Status**: Pending verification
**Prerequisite**: Merge fix/fastmcp-http-transport-investigation PR

**Action Items**:
- [ ] Test Claude Code can list tools via MCP
- [ ] Test Claude Code can invoke pg_query
- [ ] Test full transaction workflow (begin → query → commit)

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
- [x] Phase 6: HTTP transport fix (circular import resolution)
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

- All 71 unit tests pass - core functionality is solid
- Server is deployed and running on Raspberry Pi with all 5 tools accessible
- HTTP transport fix merged - tools now visible via MCP protocol
- Integration tests are INTENTIONALLY failing - they document real bugs
- See investigation report: `docs/reports/2026-02-01-deployment-investigation.md`
