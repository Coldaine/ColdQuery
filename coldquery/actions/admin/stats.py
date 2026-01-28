import json
from typing import Dict, Any
from fastmcp.exceptions import ToolError
from coldquery.core.context import ActionContext, resolve_executor

async def stats_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Get table statistics."""
    session_id = params.get("session_id")
    table = params.get("table")
    schema = params.get("schema", "public")

    executor = await resolve_executor(context, session_id)

    if not table:
        raise ToolError("'table' is required for stats action")

    sql = """
        SELECT
            n_live_tup,
            n_dead_tup,
            last_vacuum,
            last_autovacuum,
            last_analyze,
            last_autoanalyze
        FROM pg_stat_user_tables
        WHERE relname = $1 AND schemaname = $2
    """

    result = await executor.execute(sql, [table, schema])
    return json.dumps(result.to_dict(), default=str)
