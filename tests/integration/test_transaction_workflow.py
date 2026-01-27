
import json
import pytest
from coldquery.tools.pg_tx import pg_tx
from coldquery.tools.pg_query import pg_query
from coldquery.core.context import ActionContext

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_begin_commit_workflow(real_context: ActionContext):
    """Verify that a transaction can be started, used, and committed."""
    # Setup table
    await pg_query(
        action="write",
        sql="CREATE TABLE users (id INT, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Begin transaction
    begin_result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(begin_result)["session_id"]
    assert session_id is not None

    # Insert data within transaction
    await pg_query(
        action="write",
        sql="INSERT INTO users (id, name) VALUES (1, 'Alice')",
        session_id=session_id,
        context=real_context,
    )

    # Commit transaction
    await pg_tx(action="commit", session_id=session_id, context=real_context)

    # Verify data is present after commit
    read_result = await pg_query(
        action="read", sql="SELECT * FROM users", context=real_context
    )
    data = json.loads(read_result)
    assert len(data["rows"]) == 1
    assert data["rows"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_rollback_workflow(real_context: ActionContext):
    """Verify that a transaction can be rolled back, discarding changes."""
    # Setup table
    await pg_query(
        action="write",
        sql="CREATE TABLE products (id INT, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Begin transaction
    begin_result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(begin_result)["session_id"]

    # Insert data
    await pg_query(
        action="write",
        sql="INSERT INTO products (id, name) VALUES (1, 'Laptop')",
        session_id=session_id,
        context=real_context,
    )

    # Rollback transaction
    await pg_tx(action="rollback", session_id=session_id, context=real_context)

    # Verify data is NOT present after rollback
    read_result = await pg_query(
        action="read", sql="SELECT * FROM products", context=real_context
    )
    data = json.loads(read_result)
    assert len(data["rows"]) == 0


@pytest.mark.asyncio
async def test_transaction_state_is_managed(real_context: ActionContext):
    """Verify session manager tracks and closes sessions correctly."""
    assert len(real_context.session_manager.get_all_sessions()) == 0

    # Begin transaction
    begin_result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(begin_result)["session_id"]

    assert len(real_context.session_manager.get_all_sessions()) == 1
    assert real_context.session_manager.get_session(session_id) is not None

    # Commit transaction
    await pg_tx(action="commit", session_id=session_id, context=real_context)

    assert len(real_context.session_manager.get_all_sessions()) == 0
    with pytest.raises(KeyError):
        real_context.session_manager.get_session(session_id)
