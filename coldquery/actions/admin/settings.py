import json
from typing import Any, Dict

from coldquery.core.context import ActionContext, resolve_executor
from coldquery.middleware.session_echo import enrich_response
from coldquery.security.access_control import require_write_access
from coldquery.security.identifiers import sanitize_identifier


async def settings_handler(params: Dict[str, Any], context: ActionContext) -> str:
    """Get or set configuration settings."""
    session_id = params.get("session_id")
    autocommit = params.get("autocommit", True)
    setting_name = params.get("setting_name")
    setting_value = params.get("setting_value")

    executor = await resolve_executor(context, session_id)

    if setting_name and setting_value:
        # This is a write operation
        require_write_access(session_id, autocommit)
        safe_setting_name = sanitize_identifier(setting_name)
        sql = f"SET {safe_setting_name} TO $1"
        result = await executor.execute(sql, [setting_value])
        return enrich_response(result.to_dict(), session_id, context.session_manager)

    elif setting_name:
        # This is a read operation
        safe_setting_name = sanitize_identifier(setting_name)
        sql = f"SHOW {safe_setting_name}"
        result = await executor.execute(sql)
        return json.dumps(result.to_dict(), default=str)
    else:
        # Show all settings
        sql = "SELECT name, setting, category, short_desc FROM pg_settings"
        result = await executor.execute(sql)
        return json.dumps(result.to_dict(), default=str)