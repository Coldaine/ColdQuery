import os
import sys
from coldquery.app import mcp

# --- TOOL REGISTRATION ---
# Tools must be imported here to execute their @mcp.tool() decorators.
# This registers them with the singleton `mcp` instance defined in `app.py`.
#
# Note: These imports must happen at the module level (not inside if __name__)
# to ensure tools are registered even when this module is imported by others.
# -------------------------
from coldquery.tools import pg_query, pg_tx, pg_schema, pg_admin, pg_monitor  # noqa: F401
from coldquery import resources, prompts  # noqa: F401

if __name__ == "__main__":
    transport = "http" if "--transport" in sys.argv and "http" in sys.argv else "stdio"

    if transport == "http":
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "19002"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()
