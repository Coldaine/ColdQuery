from typing import Any

from coldquery.core.context import ActionContext, resolve_executor
from coldquery.core.executor import QueryResult
from coldquery.middleware.session_echo import enrich_response


async def explain_handler(params: dict[str, Any], context: ActionContext) -> str:
    """Handles the 'explain' action to analyze query execution plans."""
    sql: str | None = params.get("sql")
    query_params: list[Any] | None = params.get("params")
    session_id: str | None = params.get("session_id")
    analyze: bool | None = params.get("analyze")

    if not sql:
        raise ValueError("The 'sql' parameter is required for the 'explain' action.")

    explain_parts = ["EXPLAIN"]
    if analyze:
        explain_parts.append("ANALYZE")

    # Always use JSON format for structured output
    explain_parts.append("FORMAT JSON")

    explain_sql = f"{' '.join(explain_parts)} {sql}"

    executor = await resolve_executor(context, session_id)
    result: QueryResult = await executor.execute(explain_sql, query_params)

    return enrich_response(result.to_dict(), session_id, context.session_manager)
