import os
import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from coldquery.core.context import ActionContext
from coldquery.core.executor import db_executor
from coldquery.core.session import session_manager


# Lifespan context manager for initialization/cleanup
@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize ActionContext and provide it to tools via lifespan."""
    # Create ActionContext once at startup
    action_context = ActionContext(executor=db_executor, session_manager=session_manager)

    # Yield a dict that tools can access via the server's lifespan result
    yield {"action_context": action_context}

    # Cleanup on shutdown (if needed)
    # await db_executor.disconnect()


# Create server with lifespan for initialization
mcp = FastMCP(
    name="coldquery",
    version="1.0.0",
    instructions=(
        "ColdQuery PostgreSQL MCP Server - Execute SQL queries safely with session"
        " management and transaction support."
    ),
    lifespan=lifespan,
)


# Health endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Returns the health status of the server."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    # Import tools to register them before running
    from coldquery.tools import pg_query  # noqa: F401

    transport = (
        "http" if "--transport" in sys.argv and "http" in sys.argv else "stdio"
    )

    if transport == "http":
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "3000"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()
