from typing import Any

from coldquery.core.context import ActionContext, resolve_executor
from coldquery.core.executor import QueryResult
from coldquery.middleware.session_echo import enrich_response
from coldquery.security.access_control import require_write_access


async def write_handler(params: dict[str, Any], context: ActionContext) -> str:
    """Handles the 'write' action to execute INSERT, UPDATE, or DELETE queries."""
    sql: str | None = params.get("sql")
    query_params: list[Any] | None = params.get("params")
    session_id: str | None = params.get("session_id")
    autocommit: bool | None = params.get("autocommit")

    if not sql:
        raise ValueError("The 'sql' parameter is required for the 'write' action.")

    require_write_access(session_id, autocommit)

    executor = await resolve_executor(context, session_id)
    result: QueryResult = await executor.execute(sql, query_params)

    return enrich_response(result.to_dict(), session_id, context.session_manager)
