from typing import Any, List, Literal, Optional

from coldquery.actions.query.explain import explain_handler
from coldquery.actions.query.read import read_handler
from coldquery.actions.query.transaction import transaction_handler
from coldquery.actions.query.write import write_handler
from coldquery.core.context import ActionContext
from coldquery.dependencies import CurrentActionContext

# Import the mcp server instance to register the tool
from coldquery.server import mcp

QUERY_ACTIONS = {
    "read": read_handler,
    "write": write_handler,
    "explain": explain_handler,
    "transaction": transaction_handler,
}


@mcp.tool()
async def pg_query(
    action: Literal["read", "write", "explain", "transaction"],
    sql: Optional[str] = None,
    params: Optional[List[Any]] = None,
    analyze: Optional[bool] = None,
    operations: Optional[List[dict]] = None,
    session_id: Optional[str] = None,
    autocommit: Optional[bool] = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Execute SQL queries with safety controls.

    Args:
        action: The type of query action (read, write, explain, transaction)
        sql: SQL query string (required for read, write, explain)
        params: Query parameters for parameterized queries
        analyze: Include ANALYZE in EXPLAIN plans (for explain action)
        operations: List of SQL operations for transaction action
        session_id: Session ID for transactional operations
        autocommit: Enable autocommit for write operations (bypasses session requirement)
        context: ActionContext dependency (injected automatically)

    Returns:
        JSON string containing query results or error information
    """
    handler = QUERY_ACTIONS.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    # Prepare params for the handler
    handler_params = {
        "sql": sql,
        "params": params,
        "analyze": analyze,
        "operations": operations,
        "session_id": session_id,
        "autocommit": autocommit,
    }

    return await handler(handler_params, context)
