import os
import sys

# Import the mcp instance from app.py
from coldquery.app import mcp

if __name__ == "__main__":
    # Import all tools to register them
    from coldquery.tools import pg_query, pg_tx, pg_schema, pg_admin, pg_monitor  # noqa: F401
    from coldquery import resources, prompts  # noqa: F401

    transport = (
        "http" if "--transport" in sys.argv and "http" in sys.argv else "stdio"
    )

    if transport == "http":
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "3000"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()
