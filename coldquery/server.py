import os
import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from coldquery.core.executor import db_executor


# Lifespan context manager for initialization/cleanup
@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize database connections and perform cleanup."""
    # Yield to let the server run.
    yield {}

    # Cleanup on shutdown
    await db_executor.disconnect()


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
    # Import all tools to register them
    from coldquery.tools import pg_query, pg_tx, pg_schema, pg_admin, pg_monitor  # noqa: F401
    from coldquery import resources, prompts  # noqa: F401

    transport = (
        "http" if "--transport" in sys.argv and "http" in sys.argv else "stdio"
    )

    if transport == "http":
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "3000"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()
