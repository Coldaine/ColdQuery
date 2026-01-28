from typing import Dict, Any
from fastmcp.exceptions import ToolError
from coldquery.core.context import ActionContext, resolve_executor
from coldquery.security.access_control import require_write_access
from coldquery.middleware.session_echo import enrich_response
from coldquery.security.identifiers import sanitize_identifier

async def vacuum_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Run VACUUM on a table."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit", True) # Maintenance commands are often autocommitted
    table = params.get("table")
    full = params.get("full", False)
    verbose = params.get("verbose", False)

    require_write_access(session_id, autocommit)
    executor = await resolve_executor(context, session_id)

    options = []
    if full:
        options.append("FULL")
    if verbose:
        options.append("VERBOSE")

    sql_options = f"({', '.join(options)})" if options else ""

    if table:
        safe_table = sanitize_identifier(table)
        sql = f"VACUUM {sql_options} {safe_table}"
    else:
        sql = f"VACUUM {sql_options}"

    result = await executor.execute(sql)
    return enrich_response(result.to_dict(), session_id, context.session_manager)

async def analyze_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Run ANALYZE on a table."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit", True)
    table = params.get("table")
    verbose = params.get("verbose", False)

    require_write_access(session_id, autocommit)
    executor = await resolve_executor(context, session_id)

    options = []
    if verbose:
        options.append("VERBOSE")

    sql_options = f"({', '.join(options)})" if options else ""

    if table:
        safe_table = sanitize_identifier(table)
        sql = f"ANALYZE {sql_options} {safe_table}"
    else:
        sql = f"ANALYZE {sql_options}"

    result = await executor.execute(sql)
    return enrich_response(result.to_dict(), session_id, context.session_manager)

async def reindex_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Run REINDEX on a table or database."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit", True)
    table = params.get("table")

    require_write_access(session_id, autocommit)
    executor = await resolve_executor(context, session_id)

    if not table:
        raise ToolError("'table' parameter is required for reindex action")

    safe_table = sanitize_identifier(table)
    sql = f"REINDEX TABLE {safe_table}"

    result = await executor.execute(sql)
    return enrich_response(result.to_dict(), session_id, context.session_manager)
