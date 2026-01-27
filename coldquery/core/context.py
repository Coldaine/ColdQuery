from dataclasses import dataclass
from typing import Optional

from coldquery.core.executor import QueryExecutor
from coldquery.core.session import SessionManager

@dataclass
class ActionContext:
    """Holds shared application state for tool actions."""
    executor: QueryExecutor
    session_manager: SessionManager

def resolve_executor(ctx: ActionContext, session_id: Optional[str]) -> QueryExecutor:
    """
    Selects the appropriate database executor.

    If a session_id is provided, it returns the session-specific executor.
    Otherwise, it returns the main pool executor for autocommit operations.
    """
    if not session_id:
        return ctx.executor

    session_executor = ctx.session_manager.get_session_executor(session_id)
    if not session_executor:
        raise ValueError(f"Invalid or expired session: {session_id}")

    return session_executor
