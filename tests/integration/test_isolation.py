
import pytest
import json
from coldquery.tools.pg_tx import pg_tx
from coldquery.tools.pg_query import pg_query
from coldquery.core.context import ActionContext

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_transaction_isolation_between_sessions(real_context: ActionContext):
    """Verify changes in one session are not visible in another until commit."""
    # Create a table
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Session A: Begin transaction
    result_a = await pg_tx(action="begin", context=real_context)
    session_a = json.loads(result_a)["session_id"]

    # Session A: Insert data
    await pg_query(
        action="write",
        sql="INSERT INTO test_users (name) VALUES ('Alice')",
        session_id=session_a,
        context=real_context,
    )

    # Session B: Begin another transaction
    result_b = await pg_tx(action="begin", context=real_context)
    session_b = json.loads(result_b)["session_id"]

    # Session B: Query from Session B - should NOT see Alice
    result = await pg_query(
        action="read",
        sql="SELECT * FROM test_users",
        session_id=session_b,
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 0

    # Session A: Commit transaction
    await pg_tx(action="commit", session_id=session_a, context=real_context)

    # Session B: Query again - should NOW see Alice
    result = await pg_query(
        action="read",
        sql="SELECT * FROM test_users",
        session_id=session_b,
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 1
    assert data["rows"][0]["name"] == "Alice"

    # Cleanup
    await pg_tx(action="commit", session_id=session_b, context=real_context)


@pytest.mark.asyncio
async def test_rollback_does_not_affect_other_sessions(real_context: ActionContext):
    """Verify that a rolled-back transaction does not affect other sessions."""
    # Create table and insert initial data
    await pg_query(
        action="write",
        sql="CREATE TABLE test_items (id INT)",
        autocommit=True,
        context=real_context,
    )
    await pg_query(
        action="write",
        sql="INSERT INTO test_items (id) VALUES (100)",
        autocommit=True,
        context=real_context,
    )

    # Session A: Begin and insert data
    session_a_id = json.loads(await pg_tx(action="begin", context=real_context))["session_id"]
    await pg_query(
        action="write",
        sql="INSERT INTO test_items (id) VALUES (1)",
        session_id=session_a_id,
        context=real_context,
    )

    # Session B: Begin and insert different data
    session_b_id = json.loads(await pg_tx(action="begin", context=real_context))["session_id"]
    await pg_query(
        action="write",
        sql="INSERT INTO test_items (id) VALUES (2)",
        session_id=session_b_id,
        context=real_context,
    )

    # Session A: Rollback
    await pg_tx(action="rollback", session_id=session_a_id, context=real_context)

    # Session B: Commit
    await pg_tx(action="commit", session_id=session_b_id, context=real_context)

    # Verify that only Session B's data and the initial data are present
    result = await pg_query(
        action="read", sql="SELECT * FROM test_items ORDER BY id", context=real_context
    )
    data = json.loads(result)
    assert len(data["rows"]) == 2
    assert data["rows"][0]["id"] == 2
    assert data["rows"][1]["id"] == 100
