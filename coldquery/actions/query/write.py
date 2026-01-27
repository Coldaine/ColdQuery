from typing import Any, Dict, List, Optional

from coldquery.core.context import ActionContext, resolve_executor
from coldquery.core.executor import QueryResult
from coldquery.middleware.session_echo import enrich_response
from coldquery.security.access_control import require_write_access


async def write_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Handles the 'write' action to execute INSERT, UPDATE, or DELETE queries."""
    sql: Optional[str] = params.get("sql")
    query_params: Optional[List[Any]] = params.get("params")
    session_id: Optional[str] = params.get("session_id")
    autocommit: Optional[bool] = params.get("autocommit")

    if not sql:
        raise ValueError("The 'sql' parameter is required for the 'write' action.")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result: QueryResult = await executor.execute(sql, query_params)

    return enrich_response(
        result.to_dict(), session_id, context.session_manager
    )
