"""Debug server with tracing to identify FastMCP HTTP transport bug."""

import logging
import os
import sys

# Enable DEBUG logging for FastMCP
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("fastmcp").setLevel(logging.DEBUG)
logging.getLogger("mcp").setLevel(logging.DEBUG)

# Import after logging is configured
from coldquery.server import mcp

print("=" * 60)
print("DEBUG SERVER STARTUP")
print("=" * 60)

# Verify tools are registered
print(f"Tools in _local_provider._components:")
for key in mcp._local_provider._components.keys():
    print(f"  {key}")

print(f"\nProviders: {len(mcp.providers)}")
print(f"Middleware: {mcp.middleware}")
print(f"Transforms: {mcp.transforms}")

# Patch list_tools with tracing
original_list_tools = mcp.list_tools


async def traced_list_tools(run_middleware=True):
    """Traced version of list_tools to debug HTTP requests."""
    print("\n" + "=" * 60)
    print(f">>> TRACE: list_tools(run_middleware={run_middleware})")
    print("=" * 60)

    # Check providers
    print(f">>> Providers count: {len(mcp.providers)}")
    for i, p in enumerate(mcp.providers):
        try:
            tools = list(await p.list_tools())
            print(f">>> Provider[{i}] ({type(p).__name__}): {len(tools)} tools")
            for t in tools:
                print(f"      - {t.name}")
        except Exception as e:
            print(f">>> Provider[{i}] ERROR: {e}")

    # Call original
    print("\n>>> Calling original list_tools...")
    try:
        result = list(await original_list_tools(run_middleware=run_middleware))
        print(f">>> Original returned: {len(result)} tools")
        for t in result:
            print(f"      - {t.name}")
    except Exception as e:
        print(f">>> Original list_tools ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60 + "\n")
        raise

    print("=" * 60 + "\n")
    return result


mcp.list_tools = traced_list_tools

# Also trace the _list_tools_mcp handler if we can find it
try:
    from fastmcp.server.mixins.mcp_operations import MCPOperationsMixin

    original_list_tools_mcp = mcp._list_tools_mcp

    async def traced_list_tools_mcp():
        print("\n>>> _list_tools_mcp called (MCP protocol handler)")
        result = await original_list_tools_mcp()
        print(f">>> _list_tools_mcp returning: {result}")
        return result

    mcp._list_tools_mcp = traced_list_tools_mcp
    print(">>> Patched _list_tools_mcp handler")
except Exception as e:
    print(f">>> Could not patch _list_tools_mcp: {e}")

print("\n" + "=" * 60)
print("STARTING HTTP SERVER")
print("=" * 60)

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "19002"))
    print(f"Listening on {host}:{port}")
    print("Test with:")
    print(f'  curl -X POST http://localhost:{port}/mcp -H "Content-Type: application/json" -d \'{{\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}}\'')
    print()
    mcp.run(transport="http", host=host, port=port)
