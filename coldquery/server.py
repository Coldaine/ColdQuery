import os
import sys

# Import the mcp server instance
from coldquery.core.mcp import mcp
# Import tools to ensure they are registered
from coldquery.tools import pg_query  # noqa: F401

if __name__ == "__main__":
    transport = (
        "http" if "--transport" in sys.argv and "http" in sys.argv else "stdio"
    )

    if transport == "http":
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "3000"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()
