import json
from typing import Dict, Any
from fastmcp.exceptions import ToolError
from coldquery.core.context import ActionContext
from coldquery.middleware.session_echo import enrich_response
from coldquery.security.identifiers import sanitize_identifier

async def begin_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Begin a new transaction."""
    isolation_level = params.get("isolation_level")

    # Create session
    session_id = await context.session_manager.create_session()

    try:
        # Get session executor
        executor = context.session_manager.get_session_executor(session_id)
        if not executor:
            raise RuntimeError(f"Failed to create session: {session_id}")

        # BEGIN with optional isolation level
        if isolation_level:
            valid_levels = ["READ UNCOMMITTED", "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]
            if isolation_level.upper() not in valid_levels:
                raise ToolError(f"Invalid isolation level: {isolation_level}")
            await executor.execute(f"BEGIN ISOLATION LEVEL {isolation_level.upper()}")
        else:
            await executor.execute("BEGIN")

        result = {
            "session_id": session_id,
            "isolation_level": isolation_level or "READ COMMITTED",
            "status": "transaction started",
        }

        return enrich_response(result, session_id, context.session_manager)

    except Exception as e:
        # Cleanup on failure
        await context.session_manager.close_session(session_id)
        raise RuntimeError(f"Failed to begin transaction: {e}")

async def commit_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Commit transaction and close session."""
    session_id = params.get("session_id")

    if not session_id:
        raise ToolError("session_id is required for commit action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ToolError(f"Invalid or expired session: {session_id}")

    try:
        await executor.execute("COMMIT")
        result = {"status": "transaction committed"}
        return json.dumps(result)
    finally:
        await context.session_manager.close_session(session_id)

async def rollback_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Rollback transaction and close session."""
    session_id = params.get("session_id")

    if not session_id:
        raise ToolError("session_id is required for rollback action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ToolError(f"Invalid or expired session: {session_id}")

    try:
        await executor.execute("ROLLBACK")
        result = {"status": "transaction rolled back"}
        return json.dumps(result)
    finally:
        await context.session_manager.close_session(session_id)

async def savepoint_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Create a savepoint within a transaction."""
    session_id = params.get("session_id")
    savepoint_name = params.get("savepoint_name")

    if not session_id:
        raise ToolError("session_id is required for savepoint action")
    if not savepoint_name:
        raise ToolError("savepoint_name is required for savepoint action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ToolError(f"Invalid or expired session: {session_id}")

    # Sanitize savepoint name
    safe_name = sanitize_identifier(savepoint_name)

    await executor.execute(f"SAVEPOINT {safe_name}")

    result = {
        "status": "savepoint created",
        "savepoint_name": savepoint_name,
    }

    return enrich_response(result, session_id, context.session_manager)

async def release_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Release a savepoint."""
    session_id = params.get("session_id")
    savepoint_name = params.get("savepoint_name")

    if not session_id:
        raise ToolError("session_id is required for release action")
    if not savepoint_name:
        raise ToolError("savepoint_name is required for release action")

    executor = context.session_manager.get_session_executor(session_id)
    if not executor:
        raise ToolError(f"Invalid or expired session: {session_id}")

    # Sanitize savepoint name
    safe_name = sanitize_identifier(savepoint_name)

    await executor.execute(f"RELEASE SAVEPOINT {safe_name}")

    result = {
        "status": "savepoint released",
        "savepoint_name": savepoint_name,
    }

    return enrich_response(result, session_id, context.session_manager)

async def list_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """List all active sessions."""
    sessions = context.session_manager.list_sessions()

    result = {
        "sessions": sessions,
        "count": len(sessions),
    }

    return json.dumps(result)
