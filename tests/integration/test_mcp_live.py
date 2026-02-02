import json
import os
import sys
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Mark as integration test
pytestmark = pytest.mark.integration

# Environment for the server process
def get_server_env():
    env = os.environ.copy()
    env["DB_PORT"] = os.environ.get("DB_PORT", "5432")
    env["DB_HOST"] = os.environ.get("DB_HOST", "localhost")
    env["DB_USER"] = os.environ.get("DB_USER", "mcp")
    env["DB_PASSWORD"] = os.environ.get("DB_PASSWORD", "mcp")
    env["DB_DATABASE"] = os.environ.get("DB_DATABASE", "mcp_test")
    # Ensure unbuffered output for stdio
    env["PYTHONUNBUFFERED"] = "1"
    return env

@pytest.mark.asyncio
async def test_mcp_server_live_lifecycle():
    """
    Live integration test that:
    1. Starts the coldquery server as a subprocess.
    2. Connects via MCP protocol (JSON-RPC over stdio).
    3. Performs a full read/write lifecycle against the real DB.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coldquery.server"],
        env=get_server_env()
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. Initialize
            await session.initialize()

            # 2. List Tools
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"Discovered tools: {tool_names}")

            assert "pg_query" in tool_names
            assert "pg_tx" in tool_names
            assert "pg_schema" in tool_names

            # 3. Create Table (pg_query with autocommit)
            print("Creating test table...")
            await session.call_tool(
                "pg_query",
                arguments={
                    "action": "write",
                    "sql": "CREATE TABLE IF NOT EXISTS mcp_live_test (id INT, val TEXT)",
                    "autocommit": True
                }
            )

            try:
                # 4. Insert Data
                print("Inserting data...")
                insert_result = await session.call_tool(
                    "pg_query",
                    arguments={
                        "action": "write",
                        "sql": "INSERT INTO mcp_live_test VALUES (1, 'mcp_live_data')",
                        "autocommit": True
                    }
                )
                print(f"Insert result: {insert_result}")

                # 5. Read Data
                print("Reading data...")
                read_result = await session.call_tool(
                    "pg_query",
                    arguments={
                        "action": "read",
                        "sql": "SELECT * FROM mcp_live_test WHERE id = 1"
                    }
                )

                # Parse JSON content
                assert len(read_result.content) > 0
                data = json.loads(read_result.content[0].text)
                assert len(data["rows"]) == 1
                assert data["rows"][0]["val"] == "mcp_live_data"

            finally:
                # 6. Cleanup
                print("Cleaning up...")
                await session.call_tool(
                    "pg_query",
                    arguments={
                        "action": "write",
                        "sql": "DROP TABLE IF EXISTS mcp_live_test",
                        "autocommit": True
                    }
                )

@pytest.mark.asyncio
async def test_mcp_server_transaction_workflow():
    """
    Live integration test for transaction workflow (pg_tx).
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coldquery.server"],
        env=get_server_env()
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Setup table
            await session.call_tool(
                "pg_query",
                arguments={
                    "action": "write",
                    "sql": "CREATE TABLE IF NOT EXISTS tx_test (id INT, name TEXT)",
                    "autocommit": True
                }
            )

            try:
                # 1. Begin Transaction
                print("Beginning transaction...")
                begin_result = await session.call_tool(
                    "pg_tx",
                    arguments={"action": "begin"}
                )
                begin_data = json.loads(begin_result.content[0].text)
                session_id = begin_data.get("session_id")
                assert session_id is not None
                print(f"Transaction started with session_id: {session_id}")

                # 2. Write in Transaction
                await session.call_tool(
                    "pg_query",
                    arguments={
                        "action": "write",
                        "sql": "INSERT INTO tx_test VALUES (99, 'tx_data')",
                        "session_id": session_id
                    }
                )

                # 3. Commit Transaction
                print("Committing transaction...")
                commit_result = await session.call_tool(
                    "pg_tx",
                    arguments={
                        "action": "commit",
                        "session_id": session_id
                    }
                )
                commit_data = json.loads(commit_result.content[0].text)
                assert commit_data["status"] == "transaction committed"

                # 4. Verify Data (in new session/autocommit)
                read_result = await session.call_tool(
                    "pg_query",
                    arguments={
                        "action": "read",
                        "sql": "SELECT * FROM tx_test WHERE id = 99"
                    }
                )
                data = json.loads(read_result.content[0].text)
                assert len(data["rows"]) == 1
                assert data["rows"][0]["name"] == "tx_data"

            finally:
                # Cleanup
                await session.call_tool(
                    "pg_query",
                    arguments={
                        "action": "write",
                        "sql": "DROP TABLE IF EXISTS tx_test",
                        "autocommit": True
                    }
                )
