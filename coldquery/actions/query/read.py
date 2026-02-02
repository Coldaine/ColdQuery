from typing import Any

from coldquery.core.context import ActionContext, resolve_executor
from coldquery.core.executor import QueryResult
from coldquery.middleware.session_echo import enrich_response


async def read_handler(params: dict[str, Any], context: ActionContext) -> str:
    """Handles the 'read' action to execute SELECT queries."""
    sql: str | None = params.get("sql")
    query_params: list[Any] | None = params.get("params")
    session_id: str | None = params.get("session_id")

    if not sql:
        raise ValueError("The 'sql' parameter is required for the 'read' action.")

    executor = await resolve_executor(context, session_id)
    result: QueryResult = await executor.execute(sql, query_params)

    return enrich_response(result.to_dict(), session_id, context.session_manager)
