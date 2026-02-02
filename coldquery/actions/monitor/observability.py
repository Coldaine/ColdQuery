import json
from typing import Any, Dict

from coldquery.core.context import ActionContext, resolve_executor


async def activity_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Get active queries."""
    session_id = params.get("session_id")
    include_idle = params.get("include_idle", False)
    executor = await resolve_executor(context, session_id)

    sql = """
        SELECT
            pid,
            usename,
            client_addr,
            state,
            query
        FROM pg_stat_activity
        WHERE state != 'idle' OR $1
    """
    result = await executor.execute(sql, [include_idle])
    return json.dumps(result.to_dict(), default=str)

async def connections_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Get connection stats."""
    session_id = params.get("session_id")
    executor = await resolve_executor(context, session_id)

    sql = "SELECT datname, numbackends FROM pg_stat_database"
    result = await executor.execute(sql)
    return json.dumps(result.to_dict(), default=str)

async def locks_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Get lock information."""
    session_id = params.get("session_id")
    executor = await resolve_executor(context, session_id)

    sql = """
        SELECT
            locktype,
            relation::regclass,
            page,
            tuple,
            virtualtransaction,
            pid,
            mode,
            granted
        FROM pg_locks
    """
    result = await executor.execute(sql)
    return json.dumps(result.to_dict(), default=str)

async def size_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Get database sizes."""
    session_id = params.get("session_id")
    database = params.get("database")
    executor = await resolve_executor(context, session_id)

    if database:
        sql = "SELECT pg_size_pretty(pg_database_size($1)) as size"
        result = await executor.execute(sql, [database])
    else:
        sql = "SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size FROM pg_database"
        result = await executor.execute(sql)
    return json.dumps(result.to_dict(), default=str)
