"""
Access control logic for ColdQuery.

OPINIONATED STANCE: Default-Deny for Writes
-------------------------------------------
ColdQuery operates on a strict "Default-Deny" policy for data modification.
Unless a user explicitly opts in via `autocommit=True` (unsafe/single-shot)
or `session_id` (transactional/safe), ANY write operation (INSERT, UPDATE, DELETE,
DDL) MUST be rejected.

This prevents LLMs from accidentally destructing data while exploring.
"""

from typing import Optional


def require_write_access(session_id: Optional[str], autocommit: Optional[bool]) -> None:
    """
    Enforces the safety policy for write operations.

    Args:
        session_id: The session ID for the current operation.
        autocommit: Flag indicating if autocommit is enabled.

    Raises:
        PermissionError: If the safety check fails.
    """
    if not session_id and not autocommit:
        raise PermissionError(
            "Safety Check Failed: Write operations require either a valid 'session_id' "
            "(for transactions) or 'autocommit: true' (for immediate execution). "
            "This prevents accidental data corruption if the session ID is forgotten."
        )
