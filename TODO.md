# ColdQuery TODO

**Last Updated**: 2026-01-27

---

## High Priority

### Fix Integration Test Suite (Phase 4) 🔴

**Status**: FAILING (13 tests written, 10 failing, 13 errors)
**Location**: `tests/integration/`
**Related**: GitHub Issue #29, docs/OBSERVATIONS.md

**Problems**:

1. **Event Loop Management** (CRITICAL)
   - Error: `RuntimeError: Task got Future attached to a different loop`
   - Root cause: Fixture cleanup happening in wrong event loop
   - Affects: ALL 13 tests during teardown
   - Files: `tests/integration/conftest.py` fixtures

2. **Connection Lifecycle** (CRITICAL)
   - Error: `InterfaceError: cannot call Connection.close(): connection has been released`
   - Root cause: Session cleanup trying to close already-released connections
   - Affects: 9/13 tests
   - Files: Session executor disconnect logic

3. **API Mismatch** (MEDIUM)
   - Error: `AttributeError: 'SessionManager' object has no attribute 'get_all_sessions'`
   - Root cause: Test uses non-existent method
   - Fix: Use `list_sessions()` instead
   - Affects: `test_transaction_workflow.py::test_transaction_state_is_managed`

**Action Items**:
- [ ] Research pytest-asyncio fixture lifecycle best practices
- [ ] Fix event loop scope for session-scoped fixtures
- [ ] Review asyncpg connection cleanup patterns
- [ ] Update SessionManager to properly track connection state
- [ ] Change `get_all_sessions()` to `list_sessions()` in test
- [ ] Add integration test documentation to DEVELOPMENT.md

**References**:
- pytest-asyncio docs: https://pytest-asyncio.readthedocs.io/
- asyncpg pool docs: https://magicstack.github.io/asyncpg/

---

## Medium Priority

### Phase 5: Docker & CI/CD 🟡

**Status**: IN PROGRESS (Jules working on Issue #31)
**Target**: Production deployment infrastructure

**Deliverables**:
- [ ] Multi-stage Dockerfile
- [ ] docker-compose.yml (development)
- [ ] docker-compose.deploy.yml (production with Tailscale)
- [ ] GitHub Actions CI workflow (updated)
- [ ] GitHub Actions deploy workflow (new)
- [ ] ARM64 builds for Raspberry Pi
- [ ] docs/DEPLOYMENT.md

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
- [x] FastMCP 3.0 migration
- [x] Default-Deny write policy
- [x] SQL injection prevention (identifier sanitization)
- [x] Session management with TTL
- [x] Action registry pattern
- [x] Comprehensive documentation (CHANGELOG, STATUS, CLAUDE.md, Gemini.md)

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

- Integration tests are INTENTIONALLY failing - they document real bugs we need to fix
- All 71 unit tests pass - core functionality is solid
- Focus on Phase 5 deployment first, then circle back to fix integration tests
- Keep TODO.md updated when completing tasks or discovering new issues
