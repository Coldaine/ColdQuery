# Plan: MCP Protocol Integration Tests

**Date:** 2026-02-01
**Status:** Planned
**Branch:** `feature/mcp-protocol-tests`

---

## Background

PRs #33-37 were closed as superseded. The core HTTP transport fix was merged in PR #38. This plan captures the valuable test coverage from those PRs to be implemented fresh.

### What Was Valuable in Closed PRs

| PR | Valuable Content |
|----|------------------|
| #36 | `test_mcp_live.py` - MCP protocol test via stdio subprocess |
| #37 | E2E HTTP transport tests, testcontainers infrastructure |

---

## Implementation Plan

### Phase 1: MCP Stdio Protocol Test

**Goal:** Test the full MCP protocol over stdio transport (as PR #36 did).

**File:** `tests/integration/test_mcp_protocol.py`

**Functionality:**
1. Spawn `python -m coldquery.server` as subprocess
2. Communicate via MCP protocol (JSON-RPC over stdin/stdout)
3. Test:
   - Server initialization
   - `tools/list` returns all 5 tools
   - `tools/call` with `pg_query` action="read"
   - `tools/call` with `pg_query` action="write" + autocommit
   - Transaction lifecycle: begin -> write -> commit

**Dependencies:**
- `mcp` Python SDK (already in dev dependencies)
- PostgreSQL test database

**Test Pattern:**
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_protocol():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coldquery.server"],
        env=get_test_env()
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            # assertions...
```

---

### Phase 2: HTTP Transport Test (Optional)

**Goal:** Test HTTP transport to catch regressions in the tool list bug.

**File:** `tests/integration/test_http_transport.py`

**Note:** This may be optional since the bug is fixed. Consider if worth maintaining.

**Functionality:**
1. Start server with `--transport http`
2. Send MCP JSON-RPC requests via HTTP
3. Verify `tools/list` returns all tools (regression test)

---

### Phase 3: CI Integration

**Updates to `.github/workflows/ci.yml`:**
1. Ensure integration tests run with real PostgreSQL (already configured)
2. Add MCP protocol tests to integration test job

---

## Implementation Steps

1. [ ] Create feature branch `feature/mcp-protocol-tests`
2. [ ] Implement `tests/integration/test_mcp_protocol.py`
3. [ ] Run tests locally against docker-compose PostgreSQL
4. [ ] Update CI if needed
5. [ ] Create PR for review

---

## Success Criteria

- [ ] `pytest tests/integration/test_mcp_protocol.py` passes
- [ ] All 5 tools discovered via MCP protocol
- [ ] Read/write operations work through MCP
- [ ] Transaction lifecycle works through MCP
- [ ] CI passes

---

## Notes

- The existing `tests/live_test.py` tests handlers directly (not MCP protocol)
- This new test validates the full stack including MCP JSON-RPC layer
- Stdio transport is simpler to test than HTTP (no session management)
