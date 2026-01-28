from typing import Any, Dict, List, Optional
from fastmcp.exceptions import ToolError

from coldquery.core.context import ActionContext
from coldquery.middleware.session_echo import enrich_response


async def transaction_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Handles the 'transaction' action to execute a batch of SQL queries atomically."""
    operations: Optional[List[Dict[str, Any]]] = params.get("operations")

    if not operations:
        raise ToolError(
            "The 'operations' parameter is required for the 'transaction' action."
        )

    session_id = await context.session_manager.create_session()
    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise RuntimeError("Failed to get session executor.")

    results = []
    try:
        await executor.execute("BEGIN")
        for i, op in enumerate(operations):
            sql = op.get("sql")
            query_params = op.get("params")
            if not sql:
                raise ToolError(f"Operation {i} is missing 'sql'.")
            try:
                result = await executor.execute(sql, query_params)
                results.append(result)
            except Exception as e:
                await executor.execute("ROLLBACK")
                raise RuntimeError(
                    f"Transaction failed at operation {i}: {e}"
                ) from e
        await executor.execute("COMMIT")
        return enrich_response(
            {
                "status": "committed",
                "results": [r.to_dict() for r in results],
            },
            session_id,
            context.session_manager,
        )
    finally:
        await context.session_manager.close_session(session_id)
