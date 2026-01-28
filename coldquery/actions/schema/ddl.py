from typing import Dict, Any
from fastmcp.exceptions import ToolError
from coldquery.core.context import ActionContext, resolve_executor
from coldquery.security.access_control import require_write_access
from coldquery.middleware.session_echo import enrich_response

async def create_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Create database object."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit")
    sql = params.get("sql")

    if not sql:
        raise ToolError("'sql' parameter is required for create action")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result = await executor.execute(sql)

    return enrich_response(result.to_dict(), session_id, context.session_manager)

async def alter_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Alter database object."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit")
    sql = params.get("sql")

    if not sql:
        raise ToolError("'sql' parameter is required for alter action")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result = await executor.execute(sql)

    return enrich_response(result.to_dict(), session_id, context.session_manager)

async def drop_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Drop database object."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit")
    sql = params.get("sql")

    if not sql:
        raise ToolError("'sql' parameter is required for drop action")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result = await executor.execute(sql)

    return enrich_response(result.to_dict(), session_id, context.session_manager)
