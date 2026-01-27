
import pytest
import asyncio
import json
from coldquery.tools.pg_tx import pg_tx
from coldquery.core.context import ActionContext
from coldquery.core.session import MAX_SESSIONS

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_multiple_sessions_can_run_concurrently(real_context: ActionContext):
    """Verify that two separate sessions can begin, run, and commit concurrently."""
    # Create a table for this test
    await real_context.executor.execute(
        "CREATE TABLE concurrency_test (id INT)"
    )

    # Begin two sessions
    session_a_id = json.loads(await pg_tx(action="begin", context=real_context))["session_id"]
    session_b_id = json.loads(await pg_tx(action="begin", context=real_context))["session_id"]

    assert session_a_id != session_b_id
    assert len(real_context.session_manager.get_all_sessions()) == 2

    # Use both sessions
    await real_context.session_manager.get_session_executor(session_a_id).execute(
        "INSERT INTO concurrency_test (id) VALUES (1)"
    )
    await real_context.session_manager.get_session_executor(session_b_id).execute(
        "INSERT INTO concurrency_test (id) VALUES (2)"
    )

    # Commit both sessions
    await pg_tx(action="commit", session_id=session_a_id, context=real_context)
    await pg_tx(action="commit", session_id=session_b_id, context=real_context)

    # Verify results
    result = await real_context.executor.execute("SELECT COUNT(*) FROM concurrency_test")
    assert result.rows[0]["count"] == 2
    assert len(real_context.session_manager.get_all_sessions()) == 0


@pytest.mark.asyncio
async def test_max_sessions_limit_is_enforced(real_context: ActionContext):
    """Verify that the server rejects new sessions when MAX_SESSIONS is reached."""
    session_ids = []

    # Create sessions up to the limit
    for _ in range(MAX_SESSIONS):
        session_id = json.loads(await pg_tx(action="begin", context=real_context))["session_id"]
        session_ids.append(session_id)

    assert len(real_context.session_manager.get_all_sessions()) == MAX_SESSIONS

    # The next attempt to create a session should fail
    with pytest.raises(RuntimeError, match="Maximum number of concurrent sessions reached"):
        await pg_tx(action="begin", context=real_context)

    # Clean up the created sessions
    for session_id in session_ids:
        await pg_tx(action="commit", session_id=session_id, context=real_context)

    assert len(real_context.session_manager.get_all_sessions()) == 0
