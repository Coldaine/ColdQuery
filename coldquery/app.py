import os
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
