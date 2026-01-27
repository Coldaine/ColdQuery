import json
from typing import Dict, Any
from coldquery.core.context import ActionContext
from coldquery.core.executor import resolve_executor

async def health_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Database health check."""
    session_id = params.get("session_id")
    executor = await resolve_executor(context, session_id)

    try:
        # A simple query to check if the database is responsive
        result = await executor.execute("SELECT 1")
        if result.row_count == 1 and result.rows[0][0] == 1:
            health_status = {"status": "ok"}
        else:
            health_status = {"status": "error", "reason": "Health check query failed"}
    except Exception as e:
        health_status = {"status": "error", "reason": str(e)}

    return json.dumps(health_status)
