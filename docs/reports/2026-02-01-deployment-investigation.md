# ColdQuery Deployment Investigation Report

**Date:** 2026-02-01
**Status:** In Progress
**Severity:** Blocking - MCP tools not accessible via HTTP transport

---

## Executive Summary

ColdQuery v1.0.0 (Python/FastMCP 3.0) has been successfully deployed to the Raspberry Pi at `/opt/coldquery/`. The server starts, passes health checks, and correctly registers all 5 MCP tools internally. However, **the HTTP transport returns an empty tools list** when queried via the MCP protocol, making the server unusable for Claude Code integration.

This appears to be a bug or incompatibility in FastMCP 3.0.0b1's HTTP (Streamable HTTP) transport layer.

---

## Infrastructure State

### Deployment Location
- **Path:** `/opt/coldquery/` (new location)
- **Old path:** `/home/coldaine/coldquery/` (cleaned up, only contains old compose file)

### Container Status
| Container | Image | Status |
|-----------|-------|--------|
| `coldquery-server` | `coldquery:latest` (local build) | Up, Healthy |
| `coldquery-tailscale` | `tailscale/tailscale:latest` | Up |

### Network Configuration
- **Internal port:** 19002 (changed from 3000 to avoid conflict with `netbootxyz`)
- **Tailscale Serve:** `https://coldquery-server.tail4c911d.ts.net/` → `http://localhost:19002`
- **MCP Endpoint:** `/mcp`

### Health Check
```bash
curl http://localhost:19002/health
# Returns: {"status":"ok"}
```

---

## The Problem

### Symptom
When Claude Code (or any MCP client) queries `tools/list`, the server returns an empty array:

```json
{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}
```

### Evidence That Tools ARE Registered

When importing the module directly inside the container:

```bash
docker exec coldquery-server python -c "
import asyncio
from coldquery.server import mcp
print(asyncio.run(mcp.list_tools()))
"
```

**Output:** All 5 tools are present:
- `pg_query` - SQL query execution
- `pg_tx` - Transaction management
- `pg_schema` - Schema introspection
- `pg_admin` - Database administration
- `pg_monitor` - Monitoring/observability

The tools are also registered in FastMCP's `LocalProvider`:
```python
provider = mcp.providers[0]  # LocalProvider
asyncio.run(provider.list_tools())  # Returns all 5 tools
```

### MCP Protocol Flow Analysis

Tested the full MCP handshake:

1. **Initialize** - Works correctly:
   ```bash
   POST /mcp
   Headers: Content-Type: application/json, Accept: application/json, text/event-stream
   Body: {"jsonrpc":"2.0","method":"initialize",...}

   Response: 200 OK
   Headers: mcp-session-id: <uuid>
   Body: {"serverInfo":{"name":"coldquery","version":"1.0.0"},...}
   ```

2. **Tools List** - Returns empty:
   ```bash
   POST /mcp
   Headers: Mcp-Session-Id: <uuid>
   Body: {"jsonrpc":"2.0","method":"tools/list","id":2}

   Response: {"result":{"tools":[]}}  # EMPTY!
   ```

---

## Root Cause Analysis

### Hypothesis 1: Circular Import (Investigated - Partially Fixed)

**Original code (`server.py`):**
```python
if __name__ == "__main__":
    from coldquery.tools import pg_query, pg_tx, ...  # Tools imported here
    mcp.run()
```

**Problem:** Tool imports were inside `if __name__ == "__main__":` block.

**Fix applied:** Moved imports to module level:
```python
# Import at module level, after mcp is created
from coldquery.tools import pg_query, pg_tx, pg_schema, pg_admin, pg_monitor
from coldquery import resources, prompts

if __name__ == "__main__":
    mcp.run()
```

**Result:** Tools now register correctly (verified via direct import), but HTTP endpoint still returns empty.

### Hypothesis 2: FastMCP 3.0 Beta Bug (Current Theory)

FastMCP 3.0.0b1 is **beta software**. Similar issues have been reported:

- [AgentOS not seeing tools with FastMCP](https://github.com/agno-agi/agno/issues/4573) - Tools visible via `fastmcp.Client` but not via external integrations
- [Server failures causing empty tools](https://github.com/jlowin/fastmcp/issues/595) - `client.list_tools()` returning empty
- [HTTP transport bugs](https://github.com/jlowin/fastmcp/issues/444) - Streamable HTTP disconnection issues

The pattern matches: tools are registered internally but the HTTP transport layer fails to expose them.

### Hypothesis 3: Session/Request Context Issue

FastMCP 3.0 uses a new architecture with:
- `LocalProvider` for tool storage
- Session management via `Mcp-Session-Id` header
- Streamable HTTP transport with SSE for responses

The disconnect may be happening in how the HTTP transport layer queries the provider for tools. The provider has the tools, but the HTTP handler may be using a different code path or missing context.

---

## Why We Can't Simply Downgrade to FastMCP 2.x

The ColdQuery codebase was built specifically for FastMCP 3.0 patterns:

### 1. Dependency Injection Pattern
```python
from coldquery.dependencies import CurrentActionContext

@mcp.tool()
async def pg_monitor(
    action: Literal["health", "activity", ...],
    context: ActionContext = CurrentActionContext(),  # FastMCP 3.0 DI
) -> str:
```

FastMCP 3.0 introduced a new dependency injection system. The `CurrentActionContext()` pattern may not exist or work differently in 2.x.

### 2. Lifespan Context
```python
@asynccontextmanager
async def lifespan(server: FastMCP):
    action_context = ActionContext(executor=db_executor, session_manager=session_manager)
    yield {"action_context": action_context}

mcp = FastMCP(name="coldquery", lifespan=lifespan)
```

The lifespan pattern for initialization/cleanup is a FastMCP 3.0 feature.

### 3. Custom Routes
```python
@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})
```

Custom HTTP routes alongside MCP endpoints may have different APIs in 2.x.

### 4. Tool Decorator Syntax
The `@mcp.tool()` decorator and its handling of async functions, type hints, and return types may differ between versions.

---

## Attempted Fixes

| Fix | Result |
|-----|--------|
| Moved tool imports to module level | Tools register, but HTTP still empty |
| Verified `python -m coldquery.server` runs correctly | ✓ Works |
| Checked for import errors in logs | None found |
| Verified tools in LocalProvider | All 5 present |
| Tested MCP handshake manually | Initialize works, tools/list empty |

---

## Next Steps (Recommended)

### Option A: Debug FastMCP 3.0 HTTP Transport
1. Add logging to FastMCP's HTTP handler to trace the tools/list request
2. Compare the code paths between direct `list_tools()` and HTTP handler
3. File a bug report with FastMCP maintainers with reproduction steps

### Option B: Try SSE Transport Instead
FastMCP supports multiple transports. SSE might not have this bug:
```python
mcp.run(transport="sse", host=host, port=port)
```

### Option C: Use stdio Transport with Proxy
Deploy as stdio server and use a proxy to expose via HTTP:
```python
# Bridge pattern from FastMCP docs
remote_proxy = FastMCP.as_proxy(ProxyClient(...))
```

### Option D: Wait for FastMCP 3.0 Stable
The 3.0 release is in beta. Monitor for bug fixes and stable release.

### Option E: Investigate Provider Wiring
Deep dive into how FastMCP 3.0 wires the LocalProvider to the HTTP transport layer. There may be a missing configuration or initialization step.

---

## Environment Details

| Component | Version |
|-----------|---------|
| FastMCP | 3.0.0b1 |
| Python | 3.12 |
| MCP Protocol | 2024-11-05 |
| asyncpg | 0.31.0 |
| Docker | Latest (Alpine-based) |
| Tailscale | Latest |

---

## Files Modified During Investigation

1. `coldquery/server.py` - Moved tool imports to module level
2. `docker-compose.deploy.yml` - Changed port from 3000 to 19002
3. `.github/workflows/deploy.yml` - Rewrote for native Pi builds (earlier fix)

---

## Related Documentation

- [FastMCP 3.0 Changelog](https://gofastmcp.com/changelog)
- [MCP Streamable HTTP Transport Spec](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [Claude Code MCP HTTP Support](https://www.infoq.com/news/2025/06/anthropic-claude-remote-mcp/)

---

## Conclusion

ColdQuery's deployment infrastructure is working correctly. The server starts, health checks pass, and tools are properly registered in FastMCP's internal registry. The failure point is specifically in FastMCP 3.0.0b1's HTTP transport layer, which returns an empty tools list despite the tools being present.

This is likely a beta bug that needs to be reported to the FastMCP maintainers or worked around via an alternative transport mechanism.
