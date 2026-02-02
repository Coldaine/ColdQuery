import json
from typing import Any, Dict

from coldquery.core.context import ActionContext, resolve_executor


async def health_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Database health check."""
    executor = await resolve_executor(context, None)

    try:
        result = await executor.execute("SELECT 1 AS health_check")
        if result.row_count == 1 and result.rows[0].get("health_check") == 1:
            health_status = {"status": "ok"}
        else:
            health_status = {"status": "error", "reason": "Health check query failed"}
    except Exception as e:
        health_status = {"status": "error", "reason": str(e)}

    return json.dumps(health_status)
