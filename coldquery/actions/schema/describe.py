import json
from typing import Dict, Any
from fastmcp.exceptions import ToolError
from coldquery.core.context import ActionContext, resolve_executor

async def describe_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Describe table structure."""
    name = params.get("name")
    schema_name = params.get("schema", "public")
    session_id = params.get("session_id")

    if not name:
        raise ToolError("'name' parameter is required for describe action")

    executor = await resolve_executor(context, session_id)

    # Get columns
    columns_sql = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
    """
    columns = await executor.execute(columns_sql, [schema_name, name])

    # Get indexes
    indexes_sql = """
        SELECT
            indexname as name,
            indexdef as definition
        FROM pg_indexes
        WHERE schemaname = $1 AND tablename = $2
    """
    indexes = await executor.execute(indexes_sql, [schema_name, name])

    result = {
        "table": name,
        "schema": schema_name,
        "columns": columns.rows,
        "indexes": indexes.rows,
    }

    return json.dumps(result, default=str)
