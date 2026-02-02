"""
Live test script for ColdQuery MCP tools against real PostgreSQL.
Run with: python tests/live_test.py
Requires PostgreSQL running on localhost:5433 (docker compose up -d postgres)
"""
import asyncio
import json
import os
import sys
import traceback

# Ensure env vars are set for the test database
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5433")
os.environ.setdefault("DB_USER", "mcp")
os.environ.setdefault("DB_PASSWORD", "mcp")
os.environ.setdefault("DB_DATABASE", "mcp_test")

from coldquery.actions.admin.stats import stats_handler

# Import handler functions
from coldquery.actions.monitor.health import health_handler
from coldquery.actions.monitor.observability import activity_handler, connections_handler, locks_handler, size_handler
from coldquery.actions.query.read import read_handler
from coldquery.actions.query.write import write_handler
from coldquery.actions.schema.describe import describe_handler
from coldquery.actions.schema.list import list_handler as schema_list_handler
from coldquery.actions.tx.lifecycle import begin_handler, commit_handler
from coldquery.actions.tx.lifecycle import list_handler as tx_list_handler
from coldquery.core.context import ActionContext
from coldquery.core.executor import AsyncpgPoolExecutor
from coldquery.core.session import SessionManager

PASS = 0
FAIL = 0
ERRORS = []


def report(name: str, passed: bool, detail: str = ""):
    global PASS, FAIL
    if passed:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        ERRORS.append((name, detail))
        print(f"  FAIL: {name}")
        if detail:
            for line in detail.strip().split("\n"):
                print(f"        {line}")


async def main():
    global PASS, FAIL

    print("=" * 60)
    print("ColdQuery Live Test Suite")
    print("=" * 60)

    # Setup
    executor = AsyncpgPoolExecutor()
    session_manager = SessionManager(executor)
    ctx = ActionContext(executor=executor, session_manager=session_manager)

    try:
        # --- Test 1: pg_monitor health ---
        print("\n--- pg_monitor health ---")
        try:
            result = await health_handler({}, ctx)
            data = json.loads(result)
            report("health returns JSON", True)
            report("health status is ok", data.get("status") == "ok", f"Got: {data}")
        except Exception as e:
            report("health_handler", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 2: pg_query read ---
        print("\n--- pg_query read ---")
        try:
            result = await read_handler({"sql": "SELECT 1 as test"}, ctx)
            data = json.loads(result)
            report("read SELECT 1", True)
            report("read returns rows", len(data.get("rows", [])) == 1, f"Got: {data}")
            report("read row value correct", data["rows"][0].get("test") == 1, f"Got: {data['rows']}")
        except Exception as e:
            report("read_handler", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        try:
            result = await read_handler({"sql": "SELECT version()"}, ctx)
            data = json.loads(result)
            version_str = data["rows"][0].get("version", "")
            report("read version()", "PostgreSQL" in version_str, f"Got: {version_str}")
        except Exception as e:
            report("read version()", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 3: pg_schema list (empty db) ---
        print("\n--- pg_schema list ---")
        try:
            result = await schema_list_handler({"target": "table"}, ctx)
            data = json.loads(result)
            report("schema list tables", True)
            report("schema list returns rows key", "rows" in data, f"Keys: {list(data.keys())}")
        except Exception as e:
            report("schema list", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 4: pg_query write (autocommit) - CREATE TABLE ---
        print("\n--- pg_query write (autocommit) ---")
        try:
            result = await write_handler({
                "sql": "CREATE TABLE live_test (id INT, name TEXT)",
                "autocommit": True,
            }, ctx)
            data = json.loads(result)
            report("write CREATE TABLE", True)
        except Exception as e:
            report("write CREATE TABLE", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 5: pg_query write - INSERT ---
        try:
            result = await write_handler({
                "sql": "INSERT INTO live_test VALUES (1, 'hello')",
                "autocommit": True,
            }, ctx)
            data = json.loads(result)
            report("write INSERT", True)
            report("write row_count is 1", data.get("row_count") == 1, f"Got: {data}")
        except Exception as e:
            report("write INSERT", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 6: pg_query read - verify insert ---
        print("\n--- pg_query read (verify insert) ---")
        try:
            result = await read_handler({"sql": "SELECT * FROM live_test"}, ctx)
            data = json.loads(result)
            report("read live_test", len(data["rows"]) == 1, f"Got {len(data['rows'])} rows")
            report("read row data correct", data["rows"][0] == {"id": 1, "name": "hello"}, f"Got: {data['rows'][0]}")
        except Exception as e:
            report("read after insert", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 7: pg_tx begin ---
        print("\n--- pg_tx lifecycle ---")
        session_id = None
        try:
            result = await begin_handler({}, ctx)
            data = json.loads(result)
            session_id = data.get("session_id")
            report("tx begin", session_id is not None, f"Got: {data}")
            report("tx begin has status", data.get("status") == "transaction started", f"Got: {data}")
        except Exception as e:
            report("tx begin", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 8: pg_query write with session_id ---
        if session_id:
            try:
                result = await write_handler({
                    "sql": "INSERT INTO live_test VALUES (2, 'world')",
                    "session_id": session_id,
                }, ctx)
                data = json.loads(result)
                report("write in session", True)
            except Exception as e:
                report("write in session", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

            # --- Test 9: pg_tx commit ---
            try:
                result = await commit_handler({"session_id": session_id}, ctx)
                data = json.loads(result)
                report("tx commit", data.get("status") == "transaction committed", f"Got: {data}")
            except Exception as e:
                report("tx commit", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 10: pg_query read - verify both rows ---
        print("\n--- pg_query read (verify transaction) ---")
        try:
            result = await read_handler({"sql": "SELECT * FROM live_test ORDER BY id"}, ctx)
            data = json.loads(result)
            report("read after tx", len(data["rows"]) == 2, f"Got {len(data['rows'])} rows, expected 2")
        except Exception as e:
            report("read after tx", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 11: pg_monitor connections ---
        print("\n--- pg_monitor connections ---")
        try:
            result = await connections_handler({}, ctx)
            data = json.loads(result)
            report("monitor connections", "rows" in data, f"Keys: {list(data.keys())}")
        except Exception as e:
            report("monitor connections", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 12: pg_monitor size ---
        print("\n--- pg_monitor size ---")
        try:
            result = await size_handler({}, ctx)
            data = json.loads(result)
            report("monitor size", "rows" in data, f"Keys: {list(data.keys())}")
        except Exception as e:
            report("monitor size", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 13: pg_admin stats ---
        print("\n--- pg_admin stats ---")
        try:
            result = await stats_handler({"table": "live_test"}, ctx)
            data = json.loads(result)
            report("admin stats", True)
        except Exception as e:
            report("admin stats", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 14: pg_schema describe ---
        print("\n--- pg_schema describe ---")
        try:
            result = await describe_handler({"name": "live_test"}, ctx)
            data = json.loads(result)
            report("schema describe", True)
        except Exception as e:
            report("schema describe", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 15: Default-Deny test ---
        print("\n--- Default-Deny test ---")
        try:
            await write_handler({
                "sql": "INSERT INTO live_test VALUES (99, 'should fail')",
            }, ctx)
            report("default-deny blocks write", False, "Expected PermissionError but succeeded")
        except PermissionError:
            report("default-deny blocks write", True)
        except Exception as e:
            report("default-deny blocks write", False, f"Wrong exception: {type(e).__name__}: {e}")

        # --- Test 16: pg_monitor activity ---
        print("\n--- pg_monitor activity ---")
        try:
            result = await activity_handler({"include_idle": True}, ctx)
            data = json.loads(result)
            report("monitor activity", "rows" in data, f"Keys: {list(data.keys())}")
        except Exception as e:
            report("monitor activity", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 17: pg_monitor locks ---
        print("\n--- pg_monitor locks ---")
        try:
            result = await locks_handler({}, ctx)
            data = json.loads(result)
            report("monitor locks", "rows" in data, f"Keys: {list(data.keys())}")
        except Exception as e:
            report("monitor locks", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Test 18: pg_tx list ---
        print("\n--- pg_tx list ---")
        try:
            result = await tx_list_handler({}, ctx)
            data = json.loads(result)
            report("tx list", "sessions" in data, f"Got: {data}")
            report("tx list count is 0", data.get("count") == 0, f"Got count: {data.get('count')}")
        except Exception as e:
            report("tx list", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

        # --- Cleanup ---
        print("\n--- Cleanup ---")
        try:
            await write_handler({
                "sql": "DROP TABLE IF EXISTS live_test",
                "autocommit": True,
            }, ctx)
            report("cleanup DROP TABLE", True)
        except Exception as e:
            report("cleanup", False, f"{type(e).__name__}: {e}")

    finally:
        await executor.disconnect(destroy=True)

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 60)

    if ERRORS:
        print("\nFailed tests:")
        for name, detail in ERRORS:
            print(f"  - {name}")
            if detail:
                for line in detail.strip().split("\n")[:3]:
                    print(f"    {line}")

    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
