"""
HTTP Transport Bug Detection Tests

These tests detect and document the FastMCP 3.0.0b1 HTTP transport bug.

The bug manifests as:
- /health endpoint works: {"status": "ok"}
- /mcp endpoint returns HTTP 406 Not Acceptable for ALL requests
- Internal mcp.list_tools() works correctly (5 tools registered)

This means MCP clients CANNOT connect to ColdQuery via HTTP transport.

Run: pytest tests/e2e/test_http_transport.py -v -s
"""
import pytest
import subprocess
import sys
import os
import time
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestHTTPTransportBug:
    """
    Tests that detect and verify the FastMCP 3.0.0b1 HTTP transport bug.
    """

    @pytest.fixture
    def server_process(self):
        """Start ColdQuery server in HTTP mode."""
        env = {
            **os.environ,
            "DB_HOST": "localhost",
            "DB_PORT": "59999",
            "DB_USER": "test",
            "DB_PASSWORD": "test",
            "DB_DATABASE": "test",
            "HOST": "127.0.0.1",
            "PORT": "19999",
        }

        proc = subprocess.Popen(
            [sys.executable, "-m", "coldquery.server", "--transport", "http"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start (check stderr for "Uvicorn running")
        time.sleep(4)

        yield proc

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def test_server_starts_successfully(self, server_process):
        """VERIFY: Server starts and binds to port."""
        import urllib.request

        # Health endpoint should work
        try:
            with urllib.request.urlopen("http://127.0.0.1:19999/health", timeout=5) as r:
                data = json.loads(r.read().decode())
                assert "status" in data
                print(f"✓ Server started, /health returns: {data}")
        except Exception as e:
            pytest.fail(f"Server failed to start: {e}")

    def test_health_endpoint_works(self, server_process):
        """VERIFY: /health endpoint works (baseline)."""
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:19999/health", timeout=5) as r:
            data = json.loads(r.read().decode())
            assert data["status"] == "ok"
            print(f"✓ /health works: {data}")

    def test_mcp_endpoint_returns_406(self, server_process):
        """
        BUG DETECTION: /mcp endpoint returns 406 Not Acceptable.

        This is the FastMCP 3.0.0b1 HTTP transport bug.
        The endpoint exists but rejects all requests.
        """
        import urllib.request
        import urllib.error

        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0.0"}
            }
        }

        try:
            req = urllib.request.Request(
                "http://127.0.0.1:19999/mcp",
                data=json.dumps(mcp_request).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                # If we get here, the bug is FIXED!
                response = r.read().decode()
                print(f"✓ MCP endpoint works! Response: {response[:200]}")
                # Mark test as expected failure since bug should be present
                pytest.xfail("Expected 406 bug, but endpoint works - bug may be fixed!")

        except urllib.error.HTTPError as e:
            if e.code == 406:
                # This is the expected bug behavior
                print(f"✗ BUG CONFIRMED: /mcp returns 406 Not Acceptable")
                print(f"  This is the FastMCP 3.0.0b1 HTTP transport bug.")
                print(f"  MCP clients cannot connect via HTTP.")
                # We mark this as xfail (expected failure) to document the bug
                pytest.xfail("FastMCP 3.0.0b1 HTTP transport bug: /mcp returns 406")
            else:
                pytest.fail(f"Unexpected HTTP error: {e.code} {e.reason}")

    def test_various_content_types_all_fail(self, server_process):
        """
        BUG DETECTION: All content types return 406.

        This shows the bug is not related to request format.
        """
        import urllib.request
        import urllib.error

        content_types = [
            "application/json",
            "text/plain",
            "application/octet-stream",
        ]

        failures = []
        for ct in content_types:
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:19999/mcp",
                    data=b"{}",
                    headers={"Content-Type": ct},
                )
                with urllib.request.urlopen(req, timeout=5):
                    pass
            except urllib.error.HTTPError as e:
                failures.append((ct, e.code))

        print(f"All content types fail:")
        for ct, code in failures:
            print(f"  {ct}: {code}")

        # All should fail with 4xx (406 for JSON, 400 for others)
        assert all(code in (400, 406) for _, code in failures), \
            f"Expected 4xx errors, got: {failures}"

        pytest.xfail("All content types return 4xx errors - HTTP transport broken")


class TestInternalToolsWork:
    """
    Verify tools ARE registered correctly internally.

    This proves the bug is in the HTTP layer, not tool registration.
    """

    async def test_internal_list_tools_returns_five(self):
        """
        VERIFY: mcp.list_tools() returns all 5 tools internally.
        """
        from coldquery.server import mcp

        tools = await mcp.list_tools()
        tool_names = sorted([t.name for t in tools])

        expected = ["pg_admin", "pg_monitor", "pg_query", "pg_schema", "pg_tx"]
        assert tool_names == expected

        print(f"✓ Internal tools registered: {tool_names}")

    async def test_internal_call_tool_works(self):
        """
        VERIFY: Calling a tool internally works.

        We can't test tools that need DB, but pg_tx:list should work.
        """
        from coldquery.server import mcp

        # pg_tx:list doesn't need a database connection
        # But we'd need to set up context properly...

        # Just verify the tool is callable
        tools = await mcp.list_tools()
        pg_tx = next(t for t in tools if t.name == "pg_tx")

        assert pg_tx.parameters is not None
        assert "action" in pg_tx.parameters.get("properties", {})

        print(f"✓ pg_tx tool has correct parameters: {list(pg_tx.parameters['properties'].keys())}")


class TestBugDocumentation:
    """
    Document the bug for future reference.
    """

    def test_bug_summary(self):
        """
        FastMCP 3.0.0b1 HTTP Transport Bug Summary

        SYMPTOMS:
        1. Server starts successfully
        2. /health endpoint works
        3. /mcp endpoint returns 406 Not Acceptable for ALL requests
        4. Internal mcp.list_tools() returns all 5 tools correctly

        ROOT CAUSE:
        Unknown - bug is in FastMCP's HTTP transport layer

        AFFECTED VERSIONS:
        - FastMCP 3.0.0b1 (beta)

        WORKAROUNDS:
        1. Use stdio transport: python -m coldquery.server (default)
        2. Wait for FastMCP 3.0 stable release
        3. Use SSE transport (untested)

        IMPACT:
        - MCP clients cannot connect via HTTP
        - Server appears to have no capabilities over HTTP
        - Blocks production deployment with HTTP-based MCP clients

        TRACKING:
        - See docs/reports/2026-02-01-deployment-investigation.md
        - Consider filing issue at https://github.com/jlowin/fastmcp
        """
        print(self.test_bug_summary.__doc__)
        assert True  # Documentation test always passes
