"""Custom FastMCP dependencies for ColdQuery."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastmcp.dependencies import Depends

from coldquery.core.executor import db_executor
from coldquery.core.session import session_manager
from coldquery.core.context import ActionContext

if TYPE_CHECKING:
    pass

def get_action_context() -> ActionContext:
    """Factory for ActionContext dependency."""
    return ActionContext(executor=db_executor, session_manager=session_manager)

def CurrentActionContext() -> ActionContext:
    """Get the current ActionContext instance.

    This dependency provides access to the ActionContext which contains
    the database executor and session manager.

    Returns:
        A dependency that resolves to the active ActionContext instance

    Example:
        ```python
        from coldquery.dependencies import CurrentActionContext

        @mcp.tool()
        async def my_query(
            sql: str,
            ctx: ActionContext = CurrentActionContext()
        ) -> str:
            executor = ctx.executor
            result = await executor.execute(sql)
            return json.dumps(result.to_dict())
        ```
    """
    return cast("ActionContext", Depends(get_action_context))
