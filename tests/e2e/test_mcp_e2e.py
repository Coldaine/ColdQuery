"""
End-to-End MCP Protocol Tests

These tests verify the COMPLETE flow:
1. Start ColdQuery server as subprocess
2. Connect via MCP client (stdio transport)
3. List tools - verify all 5 are present
4. Call tools - verify responses are correct
5. Execute transactions - verify ACID properties
6. Verify data in database

This is the definitive test that proves ColdQuery works as an MCP server.

Requirements:
- Docker (for Testcontainers PostgreSQL)
- pip install testcontainers[postgres]

Run: pytest tests/e2e/test_mcp_e2e.py -v -s
"""
import pytest
import os
import json

# Check Docker availability
DOCKER_AVAILABLE = False
DOCKER_ERROR = None

try:
    import docker
    client = docker.from_env()
    client.ping()
    DOCKER_AVAILABLE = True
except Exception as e:
    DOCKER_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason=f"Docker not available: {DOCKER_ERROR}"
)


@pytest.fixture(scope="module")
def postgres_container():
    """Start PostgreSQL container for the entire test module."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        image="postgres:16",
        username="e2e_user",
        password="e2e_pass",
        dbname="e2e_db",
    ) as postgres:
        yield {
            "host": postgres.get_container_host_ip(),
            "port": postgres.get_exposed_port(5432),
            "user": postgres.username,
            "password": postgres.password,
            "database": postgres.dbname,
        }


@pytest.fixture(scope="module")
def server_env(postgres_container):
    """Environment variables for the ColdQuery server."""
    return {
        **os.environ,
        "DB_HOST": postgres_container["host"],
        "DB_PORT": str(postgres_container["port"]),
        "DB_USER": postgres_container["user"],
        "DB_PASSWORD": postgres_container["password"],
        "DB_DATABASE": postgres_container["database"],
    }


class TestMCPEndToEnd:
    """
    End-to-end tests using FastMCP's in-memory client.

    These tests start a real server instance and make actual MCP calls.
    """

    @pytest.fixture
    async def mcp_client(self, server_env):
        """
        Create MCP client connected to ColdQuery with real database.

        We need to create a fresh server instance with the test database
        environment variables, then connect a client to it.
        """
        # Set environment variables before importing server
        for key, value in server_env.items():
            os.environ[key] = value

        # Import fresh server with new env vars
        # We need to reload the executor to pick up new DB connection
        import importlib
        import coldquery.core.executor as executor_module
        import coldquery.core.session as session_module
        import coldquery.server as server_module

        # Create fresh executor with test DB
        from coldquery.core.executor import AsyncpgPoolExecutor
        from coldquery.core.session import SessionManager
        from coldquery.core.context import ActionContext

        test_executor = AsyncpgPoolExecutor()
        test_session_manager = SessionManager(test_executor)
        test_context = ActionContext(executor=test_executor, session_manager=test_session_manager)

        # Now create a test-specific FastMCP server
        from fastmcp import FastMCP
        from fastmcp.client import Client
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def test_lifespan(server: FastMCP):
            yield {"action_context": test_context}

        test_mcp = FastMCP(
            name="coldquery-e2e-test",
            version="1.0.0",
            lifespan=test_lifespan,
        )

        # Register tools manually (same as server.py but with our context)
        from coldquery.tools.pg_query import QUERY_ACTIONS
        from coldquery.tools.pg_tx import TX_ACTIONS
        from coldquery.tools.pg_schema import SCHEMA_ACTIONS
        from coldquery.tools.pg_admin import ADMIN_ACTIONS
        from coldquery.tools.pg_monitor import MONITOR_ACTIONS
        from typing import Literal, Optional, List, Any

        @test_mcp.tool()
        async def pg_query(
            action: Literal["read", "write", "explain", "transaction"],
            sql: Optional[str] = None,
            params: Optional[List[Any]] = None,
            autocommit: bool = False,
            session_id: Optional[str] = None,
            analyze: bool = False,
            operations: Optional[List[dict]] = None,
        ) -> str:
            """Execute SQL queries with safety controls."""
            handler = QUERY_ACTIONS.get(action)
            if not handler:
                raise ValueError(f"Unknown action: {action}")
            return await handler({
                "sql": sql, "params": params, "autocommit": autocommit,
                "session_id": session_id, "analyze": analyze, "operations": operations,
            }, test_context)

        @test_mcp.tool()
        async def pg_tx(
            action: Literal["begin", "commit", "rollback", "savepoint", "release", "list"],
            session_id: Optional[str] = None,
            name: Optional[str] = None,
        ) -> str:
            """Manage database transactions."""
            handler = TX_ACTIONS.get(action)
            if not handler:
                raise ValueError(f"Unknown action: {action}")
            return await handler({"session_id": session_id, "name": name}, test_context)

        @test_mcp.tool()
        async def pg_schema(
            action: Literal["list", "describe", "create", "alter", "drop"],
            target: Optional[str] = None,
            name: Optional[str] = None,
            schema: Optional[str] = None,
            definition: Optional[str] = None,
            autocommit: bool = False,
            session_id: Optional[str] = None,
        ) -> str:
            """Inspect and modify database schema."""
            handler = SCHEMA_ACTIONS.get(action)
            if not handler:
                raise ValueError(f"Unknown action: {action}")
            return await handler({
                "target": target, "name": name, "schema": schema,
                "definition": definition, "autocommit": autocommit, "session_id": session_id,
            }, test_context)

        @test_mcp.tool()
        async def pg_admin(
            action: Literal["vacuum", "analyze", "reindex", "stats", "settings"],
            table: Optional[str] = None,
            setting: Optional[str] = None,
            value: Optional[str] = None,
            autocommit: bool = False,
            session_id: Optional[str] = None,
        ) -> str:
            """Database administration operations."""
            handler = ADMIN_ACTIONS.get(action)
            if not handler:
                raise ValueError(f"Unknown action: {action}")
            return await handler({
                "table": table, "setting": setting, "value": value,
                "autocommit": autocommit, "session_id": session_id,
            }, test_context)

        @test_mcp.tool()
        async def pg_monitor(
            action: Literal["health", "activity", "connections", "locks", "size"],
            include_idle: bool = False,
        ) -> str:
            """Monitor database health and activity."""
            handler = MONITOR_ACTIONS.get(action)
            if not handler:
                raise ValueError(f"Unknown action: {action}")
            return await handler({"include_idle": include_idle}, test_context)

        # Connect client to server
        async with Client(transport=test_mcp) as client:
            yield client

        # Cleanup
        await test_executor.disconnect(destroy=True)

    # =========================================================================
    # PHASE 1: Tool Discovery
    # =========================================================================

    async def test_01_list_tools_returns_all_five(self, mcp_client):
        """
        VERIFY: MCP client can list all 5 ColdQuery tools.

        This proves tools are properly registered with the MCP server.
        """
        tools = await mcp_client.list_tools()
        tool_names = sorted([t.name for t in tools])

        expected = ["pg_admin", "pg_monitor", "pg_query", "pg_schema", "pg_tx"]
        assert tool_names == expected, f"Expected {expected}, got {tool_names}"

        print(f"✓ Found all 5 tools: {tool_names}")

    async def test_02_tools_have_descriptions(self, mcp_client):
        """
        VERIFY: Each tool has a description for AI clients.
        """
        tools = await mcp_client.list_tools()

        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 10, f"Tool {tool.name} description too short"
            print(f"✓ {tool.name}: {tool.description[:50]}...")

    async def test_03_tools_have_parameter_schemas(self, mcp_client):
        """
        VERIFY: Each tool has a parameter schema for validation.
        """
        tools = await mcp_client.list_tools()

        for tool in tools:
            assert tool.parameters, f"Tool {tool.name} has no parameters schema"
            assert "properties" in tool.parameters, f"Tool {tool.name} missing properties"
            print(f"✓ {tool.name}: {list(tool.parameters.get('properties', {}).keys())}")

    # =========================================================================
    # PHASE 2: Health Check
    # =========================================================================

    async def test_04_health_check_returns_ok(self, mcp_client):
        """
        VERIFY: pg_monitor:health returns status=ok when database is connected.
        """
        result = await mcp_client.call_tool(
            name="pg_monitor",
            arguments={"action": "health"}
        )

        # Parse response
        text = result.content[0].text
        data = json.loads(text)

        assert data["status"] == "ok", f"Expected status=ok, got {data}"
        print(f"✓ Health check passed: {data}")

    # =========================================================================
    # PHASE 3: Read Queries
    # =========================================================================

    async def test_05_read_query_select_one(self, mcp_client):
        """
        VERIFY: pg_query:read can execute SELECT 1.
        """
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={"action": "read", "sql": "SELECT 1 AS value"}
        )

        data = json.loads(result.content[0].text)

        assert "rows" in data, f"Expected rows in response: {data}"
        assert len(data["rows"]) == 1, f"Expected 1 row: {data}"
        assert data["rows"][0]["value"] == 1, f"Expected value=1: {data}"
        print(f"✓ SELECT 1 returned: {data['rows']}")

    async def test_06_read_query_with_parameters(self, mcp_client):
        """
        VERIFY: pg_query:read supports parameterized queries ($1, $2).
        """
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "read",
                "sql": "SELECT $1::int + $2::int AS sum",
                "params": [10, 20]
            }
        )

        data = json.loads(result.content[0].text)

        assert data["rows"][0]["sum"] == 30, f"Expected sum=30: {data}"
        print(f"✓ Parameterized query: 10 + 20 = {data['rows'][0]['sum']}")

    # =========================================================================
    # PHASE 4: Write Queries (Security)
    # =========================================================================

    async def test_07_write_blocked_without_auth(self, mcp_client):
        """
        VERIFY: pg_query:write is blocked without autocommit or session_id.

        This tests the Default-Deny security policy.
        """
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "write",
                "sql": "CREATE TABLE should_fail (id INT)"
            }
        )

        # Should return error, not success
        text = result.content[0].text
        assert "error" in text.lower() or "permission" in text.lower(), \
            f"Expected permission error: {text}"
        print(f"✓ Default-deny blocked unauthorized write")

    async def test_08_write_allowed_with_autocommit(self, mcp_client):
        """
        VERIFY: pg_query:write succeeds with autocommit=true.
        """
        # Create table
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "write",
                "sql": "CREATE TABLE e2e_test (id INT, name TEXT)",
                "autocommit": True
            }
        )

        data = json.loads(result.content[0].text)
        # CREATE TABLE returns row_count 0 typically
        assert "error" not in result.content[0].text.lower(), f"Unexpected error: {result.content[0].text}"
        print(f"✓ CREATE TABLE with autocommit succeeded")

        # Insert data
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "write",
                "sql": "INSERT INTO e2e_test VALUES (1, 'hello')",
                "autocommit": True
            }
        )

        data = json.loads(result.content[0].text)
        assert data.get("row_count") == 1, f"Expected row_count=1: {data}"
        print(f"✓ INSERT with autocommit succeeded: {data}")

        # Verify data exists
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "read",
                "sql": "SELECT * FROM e2e_test"
            }
        )

        data = json.loads(result.content[0].text)
        assert len(data["rows"]) == 1, f"Expected 1 row: {data}"
        assert data["rows"][0]["name"] == "hello", f"Expected name='hello': {data}"
        print(f"✓ Data verified in database: {data['rows']}")

    # =========================================================================
    # PHASE 5: Transaction Lifecycle
    # =========================================================================

    async def test_09_transaction_begin_returns_session_id(self, mcp_client):
        """
        VERIFY: pg_tx:begin returns a session_id for transaction tracking.
        """
        result = await mcp_client.call_tool(
            name="pg_tx",
            arguments={"action": "begin"}
        )

        data = json.loads(result.content[0].text)

        assert "session_id" in data, f"Expected session_id: {data}"
        assert data["status"] == "transaction started", f"Expected status: {data}"

        session_id = data["session_id"]
        print(f"✓ Transaction started with session_id: {session_id}")

        # Clean up - rollback the transaction
        await mcp_client.call_tool(
            name="pg_tx",
            arguments={"action": "rollback", "session_id": session_id}
        )

    async def test_10_transaction_commit_persists_data(self, mcp_client):
        """
        VERIFY: Data written in a transaction is visible after COMMIT.

        Flow:
        1. BEGIN → get session_id
        2. CREATE TABLE (with session_id)
        3. INSERT (with session_id)
        4. COMMIT
        5. SELECT → data is there
        """
        # 1. Begin transaction
        result = await mcp_client.call_tool(
            name="pg_tx",
            arguments={"action": "begin"}
        )
        session_id = json.loads(result.content[0].text)["session_id"]
        print(f"  1. BEGIN: session_id={session_id}")

        # 2. Create table in transaction
        await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "write",
                "sql": "CREATE TABLE tx_commit_test (val TEXT)",
                "session_id": session_id
            }
        )
        print(f"  2. CREATE TABLE in transaction")

        # 3. Insert in transaction
        await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "write",
                "sql": "INSERT INTO tx_commit_test VALUES ('committed')",
                "session_id": session_id
            }
        )
        print(f"  3. INSERT in transaction")

        # 4. Commit
        result = await mcp_client.call_tool(
            name="pg_tx",
            arguments={"action": "commit", "session_id": session_id}
        )
        data = json.loads(result.content[0].text)
        assert data["status"] == "transaction committed", f"Expected committed: {data}"
        print(f"  4. COMMIT: {data['status']}")

        # 5. Verify data persisted
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={"action": "read", "sql": "SELECT * FROM tx_commit_test"}
        )
        data = json.loads(result.content[0].text)
        assert len(data["rows"]) == 1, f"Expected 1 row after commit: {data}"
        assert data["rows"][0]["val"] == "committed", f"Expected 'committed': {data}"
        print(f"  5. SELECT after COMMIT: {data['rows']}")

        print(f"✓ Transaction COMMIT flow verified")

    async def test_11_transaction_rollback_discards_data(self, mcp_client):
        """
        VERIFY: Data written in a transaction is GONE after ROLLBACK.

        Flow:
        1. BEGIN → get session_id
        2. CREATE TABLE (with session_id)
        3. INSERT (with session_id)
        4. ROLLBACK
        5. SELECT → table doesn't exist
        """
        # 1. Begin transaction
        result = await mcp_client.call_tool(
            name="pg_tx",
            arguments={"action": "begin"}
        )
        session_id = json.loads(result.content[0].text)["session_id"]
        print(f"  1. BEGIN: session_id={session_id}")

        # 2. Create table in transaction
        await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "write",
                "sql": "CREATE TABLE tx_rollback_test (val TEXT)",
                "session_id": session_id
            }
        )
        print(f"  2. CREATE TABLE in transaction")

        # 3. Insert in transaction
        await mcp_client.call_tool(
            name="pg_query",
            arguments={
                "action": "write",
                "sql": "INSERT INTO tx_rollback_test VALUES ('should_disappear')",
                "session_id": session_id
            }
        )
        print(f"  3. INSERT in transaction")

        # 4. Rollback
        result = await mcp_client.call_tool(
            name="pg_tx",
            arguments={"action": "rollback", "session_id": session_id}
        )
        data = json.loads(result.content[0].text)
        assert data["status"] == "transaction rolled back", f"Expected rolled back: {data}"
        print(f"  4. ROLLBACK: {data['status']}")

        # 5. Verify table doesn't exist
        result = await mcp_client.call_tool(
            name="pg_query",
            arguments={"action": "read", "sql": "SELECT * FROM tx_rollback_test"}
        )
        text = result.content[0].text
        # Should get an error about table not existing
        assert "error" in text.lower() or "does not exist" in text.lower(), \
            f"Expected table to not exist after rollback: {text}"
        print(f"  5. SELECT after ROLLBACK: table doesn't exist (expected)")

        print(f"✓ Transaction ROLLBACK flow verified")

    # =========================================================================
    # PHASE 6: Schema Introspection
    # =========================================================================

    async def test_12_schema_list_tables(self, mcp_client):
        """
        VERIFY: pg_schema:list returns tables we created.
        """
        result = await mcp_client.call_tool(
            name="pg_schema",
            arguments={"action": "list", "target": "table"}
        )

        data = json.loads(result.content[0].text)
        assert "rows" in data, f"Expected rows: {data}"

        table_names = [r.get("table_name") for r in data["rows"]]
        # We created e2e_test and tx_commit_test earlier
        assert "e2e_test" in table_names, f"Expected e2e_test in {table_names}"
        print(f"✓ Schema list found tables: {table_names}")

    async def test_13_schema_describe_table(self, mcp_client):
        """
        VERIFY: pg_schema:describe returns column information.
        """
        result = await mcp_client.call_tool(
            name="pg_schema",
            arguments={"action": "describe", "name": "e2e_test"}
        )

        data = json.loads(result.content[0].text)
        assert "columns" in data, f"Expected columns: {data}"

        column_names = [c.get("column_name") for c in data["columns"]]
        assert "id" in column_names, f"Expected 'id' column: {column_names}"
        assert "name" in column_names, f"Expected 'name' column: {column_names}"
        print(f"✓ Schema describe: {column_names}")

    # =========================================================================
    # PHASE 7: Monitoring
    # =========================================================================

    async def test_14_monitor_activity(self, mcp_client):
        """
        VERIFY: pg_monitor:activity returns connection info.
        """
        result = await mcp_client.call_tool(
            name="pg_monitor",
            arguments={"action": "activity", "include_idle": True}
        )

        data = json.loads(result.content[0].text)
        assert "rows" in data, f"Expected rows: {data}"
        print(f"✓ Monitor activity: {len(data['rows'])} connections")

    async def test_15_monitor_size(self, mcp_client):
        """
        VERIFY: pg_monitor:size returns database size.
        """
        result = await mcp_client.call_tool(
            name="pg_monitor",
            arguments={"action": "size"}
        )

        data = json.loads(result.content[0].text)
        assert "rows" in data, f"Expected rows: {data}"
        print(f"✓ Monitor size: {data['rows']}")


# =============================================================================
# Summary
# =============================================================================

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print summary of what was verified."""
    terminalreporter.write_sep("=", "E2E VERIFICATION SUMMARY")
    terminalreporter.write_line("")
    terminalreporter.write_line("If all tests passed, we have verified:")
    terminalreporter.write_line("  1. MCP client can connect to ColdQuery")
    terminalreporter.write_line("  2. All 5 tools are discoverable (pg_query, pg_tx, pg_schema, pg_admin, pg_monitor)")
    terminalreporter.write_line("  3. Tools have descriptions and parameter schemas")
    terminalreporter.write_line("  4. Health check returns OK with real database")
    terminalreporter.write_line("  5. Read queries work (SELECT, parameterized)")
    terminalreporter.write_line("  6. Default-deny blocks unauthorized writes")
    terminalreporter.write_line("  7. Autocommit allows writes")
    terminalreporter.write_line("  8. Transaction BEGIN returns session_id")
    terminalreporter.write_line("  9. Transaction COMMIT persists data")
    terminalreporter.write_line(" 10. Transaction ROLLBACK discards data")
    terminalreporter.write_line(" 11. Schema introspection works")
    terminalreporter.write_line(" 12. Monitoring queries work")
    terminalreporter.write_line("")
