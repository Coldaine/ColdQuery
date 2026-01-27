# Migration Guide: TypeScript to Python (FastMCP 3.0)

Guide for understanding the differences between the TypeScript and Python implementations of ColdQuery.

## Table of Contents

- [Overview](#overview)
- [FastMCP API Differences](#fastmcp-api-differences)
- [Dependency Injection](#dependency-injection)
- [Code Patterns](#code-patterns)
- [Testing](#testing)
- [Common Pitfalls](#common-pitfalls)

---

## Overview

### Why Rewrite?

1. **FastMCP 3.0 Python** is more mature and better documented than TypeScript version
2. **Python ecosystem** has stronger async/await support for database operations (asyncpg)
3. **Simpler deployment** - single Python process vs Node.js build step
4. **Better IDE support** for type hints and dependency injection

### What Changed?

| Aspect | TypeScript | Python |
|--------|------------|--------|
| Framework | FastMCP 3.30.0 (TS) | FastMCP 3.0.0b1 (Python) |
| DB Driver | `pg` | `asyncpg` |
| DI System | Manual context passing | Docket-style `Depends()` |
| Tool Registration | `server.addTool()` | `@mcp.tool()` decorator |
| Server Lifecycle | `server.setLifespan()` | Constructor parameter `lifespan=` |
| Custom Routes | `server.registerRoute()` | `@mcp.custom_route()` decorator |

---

## FastMCP API Differences

### Server Creation

**TypeScript**:
```typescript
import { FastMCP } from "@fastmcp/sdk";

const mcp = new FastMCP({
  name: "coldquery",
  version: "1.0.0",
});
```

**Python**:
```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="coldquery",
    version="1.0.0",
)
```

---

### Tool Registration

**TypeScript** (Manual registration):
```typescript
import { z } from "zod";

mcp.addTool({
  name: "pg_query",
  description: "Execute SQL queries",
  schema: z.object({
    action: z.enum(["read", "write"]),
    sql: z.string(),
  }),
  handler: async (params) => {
    // Implementation
    return result;
  },
});
```

**Python** (Decorator registration):
```python
from typing import Literal

@mcp.tool()
async def pg_query(
    action: Literal["read", "write"],
    sql: str,
) -> str:
    """Execute SQL queries."""
    # Implementation
    return result
```

✅ **Python advantage**: Schema auto-generated from type hints, no manual Zod schema required.

---

### Lifespan Management

**TypeScript**:
```typescript
mcp.setLifespan(async (server) => {
  // Setup
  const executor = new QueryExecutor();
  await executor.connect();

  // Make available to tools somehow (global var or context)
  globalThis.executor = executor;

  return async () => {
    // Cleanup
    await executor.disconnect();
  };
});
```

**Python**:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(server: FastMCP):
    # Setup
    executor = QueryExecutor()
    await executor.connect()

    # Yield data accessible to tools
    yield {"executor": executor}

    # Cleanup
    await executor.disconnect()

mcp = FastMCP(name="coldquery", lifespan=lifespan)
```

✅ **Python advantage**: Lifespan data explicitly yielded and accessible via DI, no globals needed.

---

### Custom Routes

**TypeScript**:
```typescript
mcp.registerRoute("/health", async (req, res) => {
  res.json({ status: "ok" });
});
```

**Python**:
```python
from starlette.responses import JSONResponse

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})
```

⚠️ **Python requirement**: Must specify `methods=["GET", "POST", ...]` explicitly.

---

## Dependency Injection

### The Problem TypeScript Had

**TypeScript** - Manual context threading:
```typescript
// Context had to be passed manually through every layer
const context = {
  executor: dbExecutor,
  sessionManager: sessionManager,
};

// Tool handler
async function pgQueryTool(params: any) {
  return await handleQuery(params, context); // Manual passing
}

// Action handler
async function handleQuery(params: any, context: ActionContext) {
  const executor = context.executor; // Manual extraction
  // ...
}
```

**Problems:**
- ❌ Easy to forget `context` parameter
- ❌ Verbose function signatures
- ❌ Hard to add new dependencies
- ❌ No type safety for context

---

### The Solution: FastMCP DI System

**Python** - Automatic injection:
```python
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext

@mcp.tool()
async def pg_query(
    action: str,
    sql: str,
    context: ActionContext = CurrentActionContext(),  # ✅ Injected automatically
) -> str:
    return await handle_query(action, sql, context)

async def handle_query(action: str, sql: str, context: ActionContext) -> str:
    executor = context.executor  # ✅ Already available
    result = await executor.execute(sql)
    return json.dumps(result.to_dict())
```

**Benefits:**
- ✅ Can't forget context - type system enforces it
- ✅ Clean signatures - dependencies are defaults
- ✅ Easy to add new dependencies - just add new `Current*()` functions
- ✅ Type-safe - IDE autocomplete works

---

### Creating Custom Dependencies

**Pattern in Python**:

```python
from fastmcp.server.dependencies import Dependency
from typing import cast

# 1. Define dependency class
class _CurrentActionContext(Dependency):
    async def __aenter__(self) -> ActionContext:
        # Get from server lifespan
        server = get_server()
        return server._lifespan_result["action_context"]

    async def __aexit__(self, *args):
        pass

# 2. Create public function
def CurrentActionContext() -> ActionContext:
    return cast(ActionContext, _CurrentActionContext())

# 3. Use in tools
@mcp.tool()
async def my_tool(ctx: ActionContext = CurrentActionContext()) -> str:
    return await ctx.executor.execute("SELECT 1")
```

**TypeScript equivalent**: Would require manual global state or complex context threading.

---

## Code Patterns

### Action Registry Pattern

Both TypeScript and Python use the same action registry pattern for dispatching tool actions.

**TypeScript**:
```typescript
const QUERY_ACTIONS = {
  read: readHandler,
  write: writeHandler,
  explain: explainHandler,
} as const;

function pgQuery(params: { action: string; sql: string }) {
  const handler = QUERY_ACTIONS[params.action];
  return handler(params);
}
```

**Python**:
```python
QUERY_ACTIONS = {
    "read": read_handler,
    "write": write_handler,
    "explain": explain_handler,
}

@mcp.tool()
async def pg_query(action: Literal["read", "write", "explain"], sql: str, ...) -> str:
    handler = QUERY_ACTIONS.get(action)
    return await handler(params, context)
```

✅ Same pattern, works well in both languages.

---

### Database Connection Management

**TypeScript** (`pg` library):
```typescript
import { Pool } from "pg";

const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT),
});

// Query
const result = await pool.query("SELECT $1 as num", [1]);
console.log(result.rows[0].num); // 1
```

**Python** (`asyncpg` library):
```python
import asyncpg

pool = await asyncpg.create_pool(
    host=os.environ.get("DB_HOST"),
    port=int(os.environ.get("DB_PORT")),
)

# Query
result = await pool.fetch("SELECT $1 as num", 1)
print(result[0]["num"]) # 1
```

**Key Differences:**
- `pg` uses callback-style result objects: `result.rows`
- `asyncpg` returns list of records directly
- Both use `$1, $2` for parameterized queries ✅

---

### Error Handling

**TypeScript**:
```typescript
try {
  await executor.execute(sql);
} catch (error) {
  if (error instanceof PostgresError) {
    throw new ToolError(`Database error: ${error.message}`);
  }
  throw error;
}
```

**Python**:
```python
try:
    await executor.execute(sql)
except asyncpg.PostgresError as error:
    raise ValueError(f"Database error: {error}")
```

✅ Similar patterns, Python's exception handling is cleaner with `except Type as var`.

---

## Testing

### Test Structure

**TypeScript** (Vitest):
```typescript
import { describe, it, expect, beforeEach } from "vitest";

describe("pg_query", () => {
  beforeEach(() => {
    // Setup
  });

  it("should execute read query", async () => {
    const result = await pgQuery({
      action: "read",
      sql: "SELECT 1",
    });
    expect(result).toBeDefined();
  });
});
```

**Python** (pytest):
```python
import pytest

@pytest.fixture
def mock_context():
    # Setup
    return ActionContext(...)

@pytest.mark.asyncio
async def test_pg_query_read(mock_context):
    result = await pg_query(
        action="read",
        sql="SELECT 1",
        context=mock_context,
    )
    assert result is not None
```

---

### Mocking

**TypeScript** (vi.mock):
```typescript
import { vi } from "vitest";

const mockExecute = vi.fn();
vi.mock("./executor", () => ({
  executor: {
    execute: mockExecute,
  },
}));
```

**Python** (unittest.mock):
```python
from unittest.mock import AsyncMock, MagicMock

mock_executor = AsyncMock()
mock_executor.execute.return_value = QueryResult(...)
```

✅ Python's mock library is more powerful and flexible.

---

## Common Pitfalls

### 1. Circular Imports

**Problem**:
```python
# ❌ server.py
from coldquery.tools.pg_query import pg_query  # Imports mcp from server.py

# ❌ pg_query.py
from coldquery.server import mcp  # Imports pg_query from tools

# Result: ImportError: cannot import name 'pg_query' from partially initialized module
```

**Solution**:
```python
# ✅ server.py
mcp = FastMCP(name="coldquery", lifespan=lifespan)

if __name__ == "__main__":
    # Import tools only when running as main
    from coldquery.tools import pg_query  # noqa: F401
    mcp.run()

# ✅ pg_query.py
from coldquery.server import mcp  # Safe - mcp is created before tools imported

@mcp.tool()
async def pg_query(...):
    pass
```

---

### 2. FastMCP API Guessing

**Problem**: The TypeScript and Python FastMCP APIs are DIFFERENT. Don't assume!

**❌ Wrong** (based on TypeScript):
```python
@mcp.context_provider  # ❌ Doesn't exist in Python
async def context_provider():
    return context

mcp.register(my_tool)  # ❌ Use decorator instead

@mcp.custom_route("/health")  # ❌ Missing required 'methods' parameter
async def health():
    return {"status": "ok"}
```

**✅ Correct** (actual Python API):
```python
@asynccontextmanager
async def lifespan(server):
    yield {"context": context}

mcp = FastMCP(name="server", lifespan=lifespan)  # ✅ Pass as parameter

@mcp.tool()  # ✅ Decorator registers automatically
async def my_tool():
    pass

@mcp.custom_route("/health", methods=["GET"])  # ✅ Methods required
async def health(request):
    return JSONResponse({"status": "ok"})
```

---

### 3. Async/Await Everywhere

**Problem**: Python requires `async`/`await` for ALL async operations.

**❌ Wrong**:
```python
def my_function():
    result = executor.execute("SELECT 1")  # ❌ Missing await
    return result
```

**✅ Correct**:
```python
async def my_function():
    result = await executor.execute("SELECT 1")  # ✅ Await async calls
    return result
```

**Rule**: If a function calls `await`, it MUST be declared `async def`.

---

### 4. asyncpg vs pg Differences

| Feature | `pg` (TypeScript) | `asyncpg` (Python) |
|---------|-------------------|-------------------|
| Query method | `pool.query(sql, [params])` | `pool.fetch(sql, *params)` |
| Result format | `{ rows: [...], rowCount: N }` | `[Record, ...]` (list) |
| Parameterized | `$1, $2` | `$1, $2` (same ✅) |
| Connection | `await pool.connect()` then `client.release()` | `await pool.acquire()` then `await pool.release(conn)` |

**Migration tip**: Wrap asyncpg in `QueryExecutor` protocol to abstract differences (already done in ColdQuery).

---

## Migration Checklist

When porting TypeScript code to Python:

- [ ] Replace `server.addTool()` with `@mcp.tool()` decorator
- [ ] Replace `server.setLifespan()` with `lifespan=` constructor parameter
- [ ] Replace manual context passing with dependency injection
- [ ] Replace `pg` library calls with `asyncpg` equivalents
- [ ] Add `async`/`await` keywords to all async functions
- [ ] Update custom routes to include `methods=` parameter
- [ ] Replace Zod schemas with Python type hints
- [ ] Replace Vitest tests with pytest
- [ ] Update imports: `from fastmcp import FastMCP, Context, ...`
- [ ] Test thoroughly - APIs are different!

---

## Resources

- **FastMCP Python Docs**: https://gofastmcp.com
- **asyncpg Docs**: https://magicstack.github.io/asyncpg/
- **Python Type Hints**: https://docs.python.org/3/library/typing.html
- **pytest Docs**: https://docs.pytest.org/

---

## Summary

✅ **Python implementation is cleaner** due to:
1. Decorator-based tool registration
2. Automatic dependency injection
3. Type hint-based schema generation
4. Mature asyncpg library
5. Better IDE support

⚠️ **Watch out for**:
1. Different FastMCP APIs between TypeScript and Python
2. Circular import issues
3. asyncpg vs pg differences
4. async/await requirements

**Bottom line**: Don't port TypeScript code directly. Use Python idioms and FastMCP Python patterns.
