# FastMCP 3.0.0b1 Python API Patterns

A comprehensive guide to implementing MCP servers using FastMCP's decorator-based API and dependency injection system.

## Table of Contents

1. [Tool Registration](#tool-registration)
2. [Dependency Injection](#dependency-injection)
3. [Custom Dependencies](#custom-dependencies)
4. [Custom Routes](#custom-routes)
5. [Server Creation and Running](#server-creation-and-running)
6. [Complete Example](#complete-example)

---

## Tool Registration

### Basic Tool Registration

Register a tool using the `@server.tool()` decorator. The decorator takes **no parameters** - configuration is provided as keyword arguments:

```python
from fastmcp import FastMCP

server = FastMCP("MyServer")

@server.tool()
def add(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y

@server.tool()
async def fetch_data(url: str) -> str:
    """Fetch data from a URL."""
    # Can be sync or async
    return await some_async_http_client.get(url)
```

### Tool Decorator Parameters

While the decorator itself takes no parameters, you can customize tools via `server.tool()` when calling it as a function:

```python
# With keyword arguments
@server.tool(name="custom_name", description="Custom description")
def my_function(x: int) -> int:
    return x * 2

# Or call directly
def calculate(x: int) -> int:
    """Calculate something."""
    return x * 2

server.tool(calculate, name="my_calc")
```

**Available Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Custom tool name (defaults to function name) |
| `description` | `str` | Tool description (defaults to docstring) |
| `title` | `str` | Display title for the tool |
| `version` | `str \| int` | Tool version (supports versioning) |
| `tags` | `set[str]` | Tags for categorizing tools |
| `icons` | `list[mcp.types.Icon]` | Icon definitions |
| `output_schema` | `dict` | JSON schema for tool output |
| `annotations` | `ToolAnnotations` | MCP annotations |
| `meta` | `dict` | Arbitrary metadata |
| `task` | `bool \| TaskConfig` | Enable background task execution |
| `timeout` | `float` | Execution timeout in seconds |
| `auth` | `AuthCheckCallable \| list` | Authorization checks |

### Parameter Types

Tool parameters are automatically documented in the MCP schema based on type hints:

```python
@server.tool()
def process(
    name: str,           # Required string
    count: int = 10,     # Optional int with default
    tags: list[str] | None = None,  # Optional list
    config: dict = None,  # Optional dict
) -> str:
    """Process data with parameters."""
    return f"Processed {name}"
```

### Accessing Context in Tools

Tools can optionally request a `Context` object to access MCP capabilities:

```python
from fastmcp import Context

@server.tool()
async def my_tool(x: int, ctx: Context) -> str:
    # The Context parameter name can be anything as long as it's type-hinted as Context
    await ctx.info(f"Processing {x}")
    await ctx.report_progress(50, 100, "Halfway done")

    # Access resources
    resource = await ctx.read_resource("resource://data")

    # Manage session state (persists across requests)
    await ctx.set_state("key", "value")
    value = await ctx.get_state("key")

    return f"Result: {x}"
```

---

## Dependency Injection

FastMCP uses a vendored Docket DI system (similar to FastAPI's `Depends`). Dependencies are injected via function parameters with default values.

### Built-in Dependencies

#### 1. CurrentContext()

Get the current request context:

```python
from fastmcp import CurrentContext, Context

@server.tool()
async def my_tool(ctx: Context = CurrentContext()) -> str:
    await ctx.info("Tool executing")
    request_id = ctx.request_id
    session_id = ctx.session_id
    return f"Request: {request_id}"
```

#### 2. CurrentFastMCP()

Get the server instance:

```python
from fastmcp import CurrentFastMCP, FastMCP

@server.tool()
async def introspect(server: FastMCP = CurrentFastMCP()) -> str:
    tools = await server.list_tools()
    return f"Server has {len(tools)} tools"
```

#### 3. Progress()

Track operation progress (works in both immediate and background task execution):

```python
from fastmcp import Progress, ProgressLike

@server.tool()
async def long_operation(progress: ProgressLike = Progress()) -> str:
    await progress.set_total(100)

    for i in range(100):
        # Do work
        await progress.increment()
        await progress.set_message(f"Processing {i}%")

    return "Complete"
```

#### 4. Depends()

Wrap any callable to inject its result:

```python
from fastmcp import Depends

def get_database():
    """Create a database connection."""
    return Database()

@server.tool()
async def query_db(db: Database = Depends(get_database)) -> str:
    result = await db.query("SELECT 1")
    return str(result)
```

### Context Injection Shorthand

Type annotations alone can inject Context - no need for explicit `Depends()`:

```python
@server.tool()
async def simple_tool(ctx: Context) -> str:
    # This works! FastMCP automatically transforms ctx: Context into ctx: Context = CurrentContext()
    await ctx.info("Hello")
    return "Done"
```

**How it works:** FastMCP's `transform_context_annotations()` function transforms all `ctx: Context` parameters into `ctx: Context = CurrentContext()` at registration time.

### Combining Dependencies

Mix multiple dependency patterns:

```python
@server.tool()
async def complex_tool(
    name: str,  # Regular parameter
    ctx: Context,  # Auto-injected context
    db: Database = Depends(get_database),  # Explicit dependency
    progress: ProgressLike = Progress(),  # Progress tracking
) -> str:
    await ctx.info(f"Processing {name}")
    await progress.set_total(100)

    results = await db.query(f"SELECT * FROM data WHERE name = {name}")

    for i, row in enumerate(results):
        # Process each row
        await progress.increment()

    return f"Processed {len(results)} rows"
```

### Dependency Resolution Order

1. Explicit user arguments (e.g., `name="Alice"`)
2. Parameters with defaults (including dependencies)
3. Async context managers are entered to resolve values
4. Context variables are set for nested calls
5. Exit stack handles cleanup in reverse order

---

## Custom Dependencies

Create custom dependencies by defining a class that inherits from `Dependency` with `__aenter__` and `__aexit__` methods, then wrap it in a function.

### Pattern: Custom Resource Dependency

For ColdQuery, you might need to inject an `ActionContext` with database connections:

```python
from fastmcp.server.dependencies import Dependency
from typing import cast

class ActionContext:
    """Context object for tool actions."""

    def __init__(self, query_engine, result_store):
        self.query_engine = query_engine
        self.result_store = result_store

class _ActionContextDep(Dependency):
    """Async context manager for ActionContext dependency."""

    async def __aenter__(self) -> ActionContext:
        from fastmcp import CurrentFastMCP

        # Get the server to access lifespan data
        server = await CurrentFastMCP().__aenter__()

        # Create context from server's lifespan state
        lifespan_data = server._lifespan_result or {}
        query_engine = lifespan_data.get("query_engine")
        result_store = lifespan_data.get("result_store")

        if not query_engine:
            raise RuntimeError("query_engine not found in lifespan context")

        return ActionContext(query_engine, result_store)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup if needed."""
        pass

def CurrentActionContext() -> ActionContext:
    """Get the current ActionContext instance.

    This dependency provides access to the active action context with
    database connections and result storage.

    Returns:
        A dependency that resolves to the ActionContext

    Raises:
        RuntimeError: If query_engine not found in lifespan context
    """
    return cast(ActionContext, _ActionContextDep())
```

### Using Custom Dependencies

```python
@server.tool()
async def execute_action(
    action_id: str,
    action_ctx: ActionContext = CurrentActionContext()
) -> str:
    # action_ctx is automatically injected
    result = await action_ctx.query_engine.execute(action_id)
    await action_ctx.result_store.save(action_id, result)
    return f"Executed {action_id}"
```

### Custom Dependency with Arguments

For dependencies that need parameters, use a factory pattern:

```python
from typing import Callable

def get_service(service_name: str) -> Callable:
    """Factory that returns a dependency resolver."""

    class _ServiceDep(Dependency):
        async def __aenter__(self):
            # Access service by name
            return SERVICE_REGISTRY[service_name]

        async def __aexit__(self, *args):
            pass

    return cast(_ServiceDep, _ServiceDep())

# In your tool:
@server.tool()
async def use_service(
    service_a = Depends(lambda: get_service("service_a")),
    service_b = Depends(lambda: get_service("service_b")),
):
    return await service_a.do_something()
```

---

## Custom Routes

FastMCP servers can expose custom HTTP routes beyond the MCP protocol:

```python
from starlette.responses import JSONResponse

@server.custom_route("/health", methods=["GET"])
async def health_check():
    """Custom health check endpoint."""
    return JSONResponse({"status": "ok"})

@server.custom_route("/metrics", methods=["GET"])
async def get_metrics():
    """Get server metrics."""
    return JSONResponse({
        "tools_count": len(await server.list_tools()),
        "resources_count": len(await server.list_resources()),
    })
```

### Custom Routes with Dependencies

Custom routes can also use dependency injection:

```python
@server.custom_route("/data", methods=["POST"])
async def process_data(
    request,
    ctx: Context = CurrentContext(),
    db: Database = Depends(get_database),
):
    """Process data via HTTP."""
    body = await request.json()
    await ctx.info(f"Processing: {body}")

    result = await db.insert("data", body)
    return JSONResponse({"id": result})
```

---

## Server Creation and Running

### Basic Server Setup

```python
from fastmcp import FastMCP

# Create server instance
server = FastMCP(
    name="MyQueryServer",
    instructions="Execute database queries and manage results",
)

# Register tools with @server.tool() decorator

# Run the server
if __name__ == "__main__":
    server.run()
```

### Server with Lifespan

Define initialization and cleanup via a lifespan function:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Server lifespan - initialize on startup, cleanup on shutdown."""

    # Initialize resources
    print("Starting server...")
    db = await init_database()
    query_engine = QueryEngine(db)
    result_store = ResultStore()

    # Yield context data that's accessible to tools
    yield {
        "db": db,
        "query_engine": query_engine,
        "result_store": result_store,
    }

    # Cleanup
    print("Shutting down...")
    await db.close()
    await result_store.cleanup()

server = FastMCP(
    name="QueryServer",
    lifespan=lifespan,
)

@server.tool()
async def execute(query: str) -> str:
    """Execute a query."""
    # Access from context
    ctx = # ... (via dependency injection)
    result = await ctx.query_engine.execute(query)
    return str(result)
```

### Accessing Lifespan Data

From within tools using the Context:

```python
@server.tool()
async def my_tool(ctx: Context) -> str:
    # Access lifespan context
    db = ctx.lifespan_context.get("db")
    query_engine = ctx.lifespan_context.get("query_engine")

    # Or use custom dependencies (cleaner)
    return "Using injected context"
```

### Running the Server

```python
if __name__ == "__main__":
    # Run with default stdio transport
    server.run()

    # Or with specific transport
    server.run(transport="stdio")  # stdio, sse, streamable-http
```

### Server Configuration

```python
server = FastMCP(
    name="QueryServer",
    instructions="Execute queries",
    version="1.0.0",
    website_url="https://example.com",
    # Error handling
    mask_error_details=False,  # Show full errors in development
    strict_input_validation=True,  # Validate all tool inputs
    # Task support
    tasks=True,  # Enable background task execution (requires fastmcp[tasks])
)
```

---

## Complete Example

Here's a complete FastMCP server implementing ColdQuery-style database operations:

```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP, Context, CurrentContext, CurrentFastMCP, Depends, Progress, ProgressLike
from fastmcp.server.dependencies import Dependency
from typing import cast

# ============================================================================
# Custom Dependencies
# ============================================================================

class ActionContext:
    """Context for executing actions."""

    def __init__(self, query_engine, result_store):
        self.query_engine = query_engine
        self.result_store = result_store

class _ActionContextDep(Dependency):
    """Dependency for injecting ActionContext."""

    async def __aenter__(self) -> ActionContext:
        server = await CurrentFastMCP().__aenter__()
        lifespan_data = server._lifespan_result or {}

        query_engine = lifespan_data.get("query_engine")
        result_store = lifespan_data.get("result_store")

        if not query_engine:
            raise RuntimeError("query_engine not available")

        return ActionContext(query_engine, result_store)

    async def __aexit__(self, *args) -> None:
        pass

def CurrentActionContext() -> ActionContext:
    """Get the current action context."""
    return cast(ActionContext, _ActionContextDep())

# ============================================================================
# Lifespan and Services
# ============================================================================

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize and cleanup server resources."""
    print("Starting QueryServer...")

    # Initialize services
    query_engine = QueryEngine()
    result_store = ResultStore()

    yield {
        "query_engine": query_engine,
        "result_store": result_store,
    }

    print("Shutting down...")
    await result_store.cleanup()

# ============================================================================
# Server and Tools
# ============================================================================

server = FastMCP(
    name="ColdQueryServer",
    instructions="Execute database queries and store results",
    lifespan=lifespan,
)

@server.tool()
async def execute_query(
    query: str,
    save_result: bool = False,
    ctx: Context = CurrentContext(),
    action_ctx: ActionContext = CurrentActionContext(),
) -> str:
    """Execute a database query."""
    await ctx.info(f"Executing: {query}")

    # Execute query
    result = await action_ctx.query_engine.execute(query)

    if save_result:
        result_id = await action_ctx.result_store.save(result)
        await ctx.info(f"Result saved with ID: {result_id}")
        return f"Query executed. Result ID: {result_id}"

    return f"Query executed. Rows: {len(result)}"

@server.tool()
async def process_large_dataset(
    dataset_id: str,
    batch_size: int = 100,
    progress: ProgressLike = Progress(),
    action_ctx: ActionContext = CurrentActionContext(),
) -> str:
    """Process a large dataset in batches with progress tracking."""

    # Fetch dataset metadata
    metadata = await action_ctx.query_engine.get_metadata(dataset_id)
    total_rows = metadata["row_count"]

    await progress.set_total(total_rows)
    await progress.set_message("Starting batch processing")

    processed = 0

    # Process in batches
    async for batch in action_ctx.query_engine.iter_batches(
        dataset_id, batch_size
    ):
        result = await action_ctx.query_engine.process(batch)
        await action_ctx.result_store.store_batch(dataset_id, result)

        processed += len(batch)
        await progress.increment(len(batch))
        await progress.set_message(f"Processed {processed}/{total_rows}")

    return f"Processing complete. Processed {processed} rows."

@server.tool()
async def list_results(
    limit: int = 10,
    ctx: Context = CurrentContext(),
) -> str:
    """List stored query results."""
    server = await ctx.fastmcp

    # Access server instance
    tools = await server.list_tools()

    return f"Server has {len(tools)} tools"

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    server.run(transport="stdio")
```

---

## Key Patterns Summary

### Pattern: Tool Registration
```python
@server.tool()
async def my_tool(arg1: str, arg2: int = 10) -> str:
    return f"{arg1}: {arg2}"
```

### Pattern: Context Injection
```python
@server.tool()
async def tool_with_context(data: str, ctx: Context) -> str:
    await ctx.info("Processing")
    return data
```

### Pattern: Dependency Injection
```python
def get_db():
    return Database()

@server.tool()
async def query(
    query: str,
    db: Database = Depends(get_db),
) -> str:
    return await db.execute(query)
```

### Pattern: Progress Tracking
```python
@server.tool()
async def long_task(progress: ProgressLike = Progress()) -> str:
    await progress.set_total(100)
    for i in range(100):
        await progress.increment()
    return "Done"
```

### Pattern: Custom Dependency
```python
class _MyDep(Dependency):
    async def __aenter__(self):
        return MyService()
    async def __aexit__(self, *args):
        pass

def CurrentMyService() -> MyService:
    return cast(MyService, _MyDep())

@server.tool()
async def use_service(svc: MyService = CurrentMyService()) -> str:
    return await svc.do_work()
```

### Pattern: Lifespan with Resources
```python
@asynccontextmanager
async def lifespan(server):
    db = await init_db()
    yield {"db": db}
    await db.close()

server = FastMCP(name="Server", lifespan=lifespan)
```

---

## Additional Resources

- **FastMCP Documentation**: https://gofastmcp.com
- **MCP Specification**: https://modelcontextprotocol.io
- **Docket DI System**: Vendored in fastmcp._vendor.docket_di
- **Context API**: `from fastmcp import Context`
- **Dependencies**: `from fastmcp import Depends, CurrentContext, CurrentFastMCP, Progress`
