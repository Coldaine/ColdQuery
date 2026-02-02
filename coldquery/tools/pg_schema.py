from typing import Literal

from coldquery.actions.schema.ddl import alter_handler, create_handler, drop_handler
from coldquery.actions.schema.describe import describe_handler
from coldquery.actions.schema.list import list_handler

# Import the mcp server instance to register the tool
from coldquery.app import mcp
from coldquery.core.context import ActionContext
from coldquery.dependencies import CurrentActionContext

SCHEMA_ACTIONS = {
    "list": list_handler,
    "describe": describe_handler,
    "create": create_handler,
    "alter": alter_handler,
    "drop": drop_handler,
}

@mcp.tool()
async def pg_schema(
    action: Literal["list", "describe", "create", "alter", "drop"],
    target: str | None = None,  # table, view, schema, function, trigger, sequence, constraint
    name: str | None = None,
    schema: str | None = None,
    sql: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_sizes: bool = False,
    cascade: bool = False,
    if_exists: bool = False,
    if_not_exists: bool = False,
    session_id: str | None = None,
    autocommit: bool | None = None,
    context: ActionContext = CurrentActionContext(),
) -> str:
    """Manage database schema and introspection.

    Actions:
    - list: List database objects (tables, views, functions, etc.)
    - describe: Get detailed structure of a table
    - create: Create database objects with DDL
    - alter: Modify existing database objects
    - drop: Remove database objects
    """
    handler = SCHEMA_ACTIONS.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    params = {
        "target": target,
        "name": name,
        "schema": schema,
        "sql": sql,
        "limit": limit,
        "offset": offset,
        "include_sizes": include_sizes,
        "cascade": cascade,
        "if_exists": if_exists,
        "if_not_exists": if_not_exists,
        "session_id": session_id,
        "autocommit": autocommit,
    }

    return await handler(params, context)
