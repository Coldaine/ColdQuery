import json
from typing import Any, Dict, Optional

from coldquery.core.session import SessionManager


def enrich_response(
    result: Dict[str, Any], session_id: Optional[str], session_manager: SessionManager
) -> str:
    """
    Enriches the response with session metadata.

    Args:
        result: The original result dictionary.
        session_id: The session ID for the current operation.
        session_manager: The session manager instance.

    Returns:
        A JSON string representing the enriched response.
    """
    if not session_id:
        return json.dumps(result)

    session = session_manager.get_session(session_id)
    if not session:
        return json.dumps(result)

    expires_in_minutes = session.expires_in
    is_near_expiry = expires_in_minutes < 5

    if is_near_expiry:
        result["active_session"] = {
            "id": session.id,
            "expires_in": f"{expires_in_minutes}m",
            "hint": "Warning: Session expiring soon. Commit your work shortly.",
        }

    return json.dumps(result)
