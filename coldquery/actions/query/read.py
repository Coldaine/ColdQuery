from typing import Any, Dict, List, Optional
from fastmcp.exceptions import ToolError

from coldquery.core.context import ActionContext, resolve_executor
from coldquery.core.executor import QueryResult
from coldquery.middleware.session_echo import enrich_response


async def read_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Handles the 'read' action to execute SELECT queries."""
    sql: Optional[str] = params.get("sql")
    query_params: Optional[List[Any]] = params.get("params")
    session_id: Optional[str] = params.get("session_id")

    if not sql:
        raise ToolError("The 'sql' parameter is required for the 'read' action.")

    executor = await resolve_executor(context, session_id)
    result: QueryResult = await executor.execute(sql, query_params)

    return enrich_response(
        result.to_dict(), session_id, context.session_manager
    )
