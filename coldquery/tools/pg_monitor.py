from typing import Literal
from fastmcp.exceptions import ToolError
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.app import mcp
from coldquery.actions.monitor.health import health_handler
from coldquery.actions.monitor.observability import (
    activity_handler,
    connections_handler,
    locks_handler,
    size_handler,
)

MONITOR_ACTIONS = {
    "health": health_handler,
    "activity": activity_handler,
    "connections": connections_handler,
    "locks": locks_handler,
    "size": size_handler,
}

@mcp.tool()
async def pg_monitor(
    action: Literal["health", "activity", "connections", "locks", "size"],
    include_idle: bool = False,
    database: str | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Database monitoring and observability.

    Actions:
    - health: Database health check
    - activity: Active queries
    - connections: Connection stats
    - locks: Lock information
    - size: Database sizes
    """
    handler = MONITOR_ACTIONS.get(action)
    if not handler:
        raise ToolError(f"Unknown action: {action}")

    params = {
        "include_idle": include_idle,
        "database": database,
    }

    return await handler(params, context)
