import os
from typing import Any


class AuthError(Exception):
    """Base class for authentication errors."""

    pass


class WriteAccessDeniedError(AuthError):
    """Raised when a write operation is attempted without authorization."""

    pass


def is_auth_enabled() -> bool:
    """Checks if authentication is enabled via environment variable."""
    return os.environ.get("COLDQUERY_AUTH_ENABLED", "false").lower() == "true"


def require_write_access(session_id: str | None, autocommit: bool | None) -> None:
    """
    Enforces the Default-Deny policy for write operations.
    A write operation is only allowed if it's within a session or explicitly autocommitted.
    """
    if not session_id and not autocommit:
        raise WriteAccessDeniedError(
            "Write operations require an active session or 'autocommit=true'. "
            "Use the 'pg_tx' tool to begin a transaction and obtain a session_id."
        )


# The functions below are placeholders and will be fully integrated once ActionContext is available.


def require_auth(ctx: Any) -> None:
    """
    Checks if the session is authenticated, if auth is enabled.
    This is a placeholder for a function that will be fully implemented once ActionContext is defined.
    """
    if not is_auth_enabled():
        return

    # The full implementation will check state from the context object, for example:
    # if not ctx.get_state("unlocked"):
    #     raise AuthError("Authentication required. Please use the 'auth_unlock' tool.")
    pass


async def auth_unlock_logic(token: str, ctx: Any) -> bool:
    """
    Provides the logic for the future 'auth_unlock' tool.
    This is a placeholder that will be fully implemented once ActionContext is defined.
    """
    if not is_auth_enabled():
        return True

    correct_token = os.environ.get("COLDQUERY_AUTH_TOKEN")
    if not correct_token:
        raise AuthError("Authentication is enabled, but no COLDQUERY_AUTH_TOKEN is set on the server.")

    # NOTE: Keeping explicit if/return structure for future implementation
    # that will set state on the context object (e.g., ctx.set_state("unlocked", True))
    if token == correct_token:  # noqa: SIM103
        return True

    return False
