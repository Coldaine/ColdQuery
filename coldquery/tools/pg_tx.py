from typing import Literal
from fastmcp.exceptions import ToolError
from coldquery.dependencies import CurrentActionContext
from coldquery.core.context import ActionContext
from coldquery.app import mcp
from coldquery.actions.tx.lifecycle import (
    begin_handler,
    commit_handler,
    rollback_handler,
    savepoint_handler,
    release_handler,
    list_handler,
)

TX_ACTIONS = {
    "begin": begin_handler,
    "commit": commit_handler,
    "rollback": rollback_handler,
    "savepoint": savepoint_handler,
    "release": release_handler,
    "list": list_handler,
}

@mcp.tool()
async def pg_tx(
    action: Literal["begin", "commit", "rollback", "savepoint", "release", "list"],
    session_id: str | None = None,
    isolation_level: str | None = None,
    savepoint_name: str | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Manage PostgreSQL transaction lifecycle.

    Actions:
    - begin: Start a new transaction, returns session_id
    - commit: Commit transaction and close session
    - rollback: Rollback transaction and close session
    - savepoint: Create a savepoint within a transaction
    - release: Release a savepoint
    - list: List all active sessions with metadata
    """
    handler = TX_ACTIONS.get(action)
    if not handler:
        raise ToolError(f"Unknown action: {action}")

    params = {
        "session_id": session_id,
        "isolation_level": isolation_level,
        "savepoint_name": savepoint_name,
    }

    return await handler(params, context)
