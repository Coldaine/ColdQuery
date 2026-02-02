"""Custom FastMCP dependencies for ColdQuery."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from coldquery.core.context import ActionContext

# Import the Dependency base class from fastmcp's vendored docket
try:
    from docket.dependencies import Dependency
except ImportError:
    from fastmcp._vendor.docket_di import Dependency


class _CurrentActionContext(Dependency):  # type: ignore[misc]
    """Dependency that resolves to ActionContext from FastMCP lifespan."""

    async def __aenter__(self) -> ActionContext:
        """Get the ActionContext from the current FastMCP context's lifespan."""
        from fastmcp.server.dependencies import get_context

        ctx = get_context()

        if ctx.lifespan_context is None:
            raise RuntimeError("Lifespan context not available. Server lifespan may not have completed.")

        action_context = ctx.lifespan_context.get("action_context")
        if action_context is None:
            raise RuntimeError(
                "ActionContext not found in lifespan. Ensure the lifespan context manager sets action_context."
            )

        return action_context

    async def __aexit__(self, *args: object) -> None:
        """No cleanup needed."""
        pass


def CurrentActionContext() -> ActionContext:
    """Get the current ActionContext instance.

    This dependency provides access to the ActionContext which contains
    the database executor and session manager.

    Returns:
        A dependency that resolves to the active ActionContext instance

    Raises:
        RuntimeError: If no active ActionContext found

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
    return cast("ActionContext", _CurrentActionContext())
