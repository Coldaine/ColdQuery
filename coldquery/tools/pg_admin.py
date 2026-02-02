from typing import Literal

from coldquery.actions.admin.maintenance import analyze_handler, reindex_handler, vacuum_handler
from coldquery.actions.admin.settings import settings_handler
from coldquery.actions.admin.stats import stats_handler

# Import the mcp server instance to register the tool
from coldquery.app import mcp
from coldquery.core.context import ActionContext
from coldquery.dependencies import CurrentActionContext

ADMIN_ACTIONS = {
    "vacuum": vacuum_handler,
    "analyze": analyze_handler,
    "reindex": reindex_handler,
    "stats": stats_handler,
    "settings": settings_handler,
}

@mcp.tool()
async def pg_admin(
    action: Literal["vacuum", "analyze", "reindex", "stats", "settings"],
    table: str | None = None,
    full: bool = False,
    verbose: bool = False,
    setting_name: str | None = None,
    setting_value: str | None = None,
    category: str | None = None,
    session_id: str | None = None,
    autocommit: bool | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Database administration and maintenance.

    Actions:
    - vacuum: VACUUM tables
    - analyze: ANALYZE tables
    - reindex: REINDEX tables
    - stats: Get table statistics
    - settings: Get/set configuration
    """
    handler = ADMIN_ACTIONS.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    params = {
        "table": table,
        "full": full,
        "verbose": verbose,
        "setting_name": setting_name,
        "setting_value": setting_value,
        "category": category,
        "session_id": session_id,
        "autocommit": autocommit,
    }

    return await handler(params, context)
