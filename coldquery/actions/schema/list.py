import json
from typing import Dict, Any
from fastmcp.exceptions import ToolError
from coldquery.core.context import ActionContext, resolve_executor

async def list_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """List database objects."""
    target = params.get("target", "table")
    schema = params.get("schema")  # noqa: F841 - TODO: wire up schema filtering
    limit = params.get("limit", 100)
    offset = params.get("offset", 0)
    include_sizes = params.get("include_sizes", False)  # noqa: F841 - TODO: wire up size inclusion
    session_id = params.get("session_id")

    executor = await resolve_executor(context, session_id)

    # Build query based on target type
    if target == "table":
        sql = """
            SELECT
                schemaname as schema,
                tablename as name,
                tableowner as owner
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename
            LIMIT $1 OFFSET $2
        """
        result = await executor.execute(sql, [limit, offset])

    elif target == "view":
        sql = """
            SELECT
                schemaname as schema,
                viewname as name,
                viewowner as owner
            FROM pg_views
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, viewname
            LIMIT $1 OFFSET $2
        """
        result = await executor.execute(sql, [limit, offset])

    elif target == "schema":
        sql = """
            SELECT
                schema_name as name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schema_name
            LIMIT $1 OFFSET $2
        """
        result = await executor.execute(sql, [limit, offset])

    else:
        raise ToolError(f"Unsupported target type: {target}")

    return json.dumps(result.to_dict(), default=str)
