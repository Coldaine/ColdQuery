import os
import sys

from coldquery import prompts, resources  # noqa: F401
from coldquery.app import mcp

# Import all tools to register them with the mcp instance
# This MUST happen at module level, after mcp is created
from coldquery.tools import pg_admin, pg_monitor, pg_query, pg_schema, pg_tx  # noqa: F401

if __name__ == "__main__":
    transport = (
        "http" if "--transport" in sys.argv and "http" in sys.argv else "stdio"
    )

    if transport == "http":
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "19002"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()