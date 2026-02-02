from contextlib import asynccontextmanager
from fastmcp import FastMCP
from coldquery.core.context import ActionContext
from coldquery.core.executor import db_executor
from coldquery.core.session import session_manager

# --- ARCHITECTURE NOTE ---
# This file defines the specific FastMCP application instance.
# It is separated from server.py to prevent "module shadowing" issues.
#
# When running `python -m coldquery.server`, server.py is loaded as `__main__`.
# If tools import `mcp` from `coldquery.server`, Python loads it AGAIN as a module,
# creating a second `mcp` instance. Tools would register to Instance B, but
# the server runs Instance A (empty).
#
# ALWAYS import `mcp` from `coldquery.app`.
# -------------------------


# Lifespan context manager for initialization/cleanup
@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize ActionContext and provide it to tools via lifespan."""
    # Create ActionContext once at startup
    action_context = ActionContext(executor=db_executor, session_manager=session_manager)

    # Yield a dict that tools can access via the server's lifespan result
    yield {"action_context": action_context}


# Create server with lifespan for initialization
mcp = FastMCP(
    name="coldquery",
    version="1.0.0",
    instructions=(
        "ColdQuery PostgreSQL MCP Server - Execute SQL queries safely with session management and transaction support."
    ),
    lifespan=lifespan,
)


# Health endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Returns the health status of the server."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok"})
