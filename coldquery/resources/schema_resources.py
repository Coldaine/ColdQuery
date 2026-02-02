from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.app import mcp
from coldquery.actions.schema.list import list_handler
from coldquery.actions.schema.describe import describe_handler

@mcp.resource("postgres://schema/tables")
async def tables_resource(ctx: ActionContext = CurrentActionContext()) -> str:
    """List all tables in the database."""
    params = {"target": "table", "limit": 100, "offset": 0}
    return await list_handler(params, ctx)

@mcp.resource("postgres://schema/{schema}/{table}")
async def table_resource(schema: str, table: str, ctx: ActionContext = CurrentActionContext()) -> str:
    """Get detailed information about a specific table."""
    params = {"name": table, "schema": schema}
    return await describe_handler(params, ctx)
