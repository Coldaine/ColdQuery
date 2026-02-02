from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.app import mcp
from coldquery.actions.monitor.health import health_handler
from coldquery.actions.monitor.observability import activity_handler

@mcp.resource("postgres://monitor/health")
async def health_resource(ctx: ActionContext = CurrentActionContext()) -> str:
    """Database health status."""
    return await health_handler({}, ctx)

@mcp.resource("postgres://monitor/activity")
async def activity_resource(ctx: ActionContext = CurrentActionContext()) -> str:
    """Current database activity."""
    return await activity_handler({}, ctx)
