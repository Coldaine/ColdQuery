
import pytest
from coldquery.tools.pg_query import pg_query
from coldquery.tools.pg_tx import pg_tx
from coldquery.core.context import ActionContext
import json

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def setup_table(real_context: ActionContext):
    """Ensure the test table exists for each test."""
    await pg_query(
        action="write",
        sql="CREATE TABLE IF NOT EXISTS test_safety (id INT)",
        autocommit=True,
        context=real_context,
    )


@pytest.mark.asyncio
async def test_write_is_denied_by_default(real_context: ActionContext):
    """Verify 'write' action fails without 'autocommit' or 'session_id'."""
    with pytest.raises(PermissionError, match="Safety Check Failed"):
        await pg_query(
            action="write",
            sql="INSERT INTO test_safety (id) VALUES (1)",
            context=real_context,
        )


@pytest.mark.asyncio
async def test_write_is_allowed_with_autocommit(real_context: ActionContext):
    """Verify 'write' action succeeds with 'autocommit=True'."""
    await pg_query(
        action="write",
        sql="INSERT INTO test_safety (id) VALUES (1)",
        autocommit=True,
        context=real_context,
    )
    result = await pg_query(
        action="read", sql="SELECT COUNT(*) FROM test_safety", context=real_context
    )
    data = json.loads(result)
    assert data["rows"][0]["count"] == 1


@pytest.mark.asyncio
async def test_write_is_allowed_with_session_id(real_context: ActionContext):
    """Verify 'write' action succeeds with a valid 'session_id'."""
    begin_result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(begin_result)["session_id"]

    await pg_query(
        action="write",
        sql="INSERT INTO test_safety (id) VALUES (1)",
        session_id=session_id,
        context=real_context,
    )
    await pg_tx(action="commit", session_id=session_id, context=real_context)

    result = await pg_query(
        action="read", sql="SELECT COUNT(*) FROM test_safety", context=real_context
    )
    data = json.loads(result)
    assert data["rows"][0]["count"] == 1
