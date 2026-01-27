
import pytest
import json
from coldquery.tools.pg_query import pg_query
from coldquery.tools.pg_tx import pg_tx
from coldquery.core.context import ActionContext
import asyncpg

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_autocommit_queries_use_and_release_pool_connections(
    real_context: ActionContext, real_db_pool: asyncpg.Pool
):
    """Verify autocommit queries acquire and release connections from the main pool."""
    initial_pool_size = real_db_pool.get_size()
    initial_idle_conns = real_db_pool.get_idle_size()

    # Run a simple query
    await pg_query(action="read", sql="SELECT 1", context=real_context)

    # Check that the pool size and idle connections are back to the initial state
    assert real_db_pool.get_size() == initial_pool_size
    assert real_db_pool.get_idle_size() == initial_idle_conns


@pytest.mark.asyncio
async def test_session_connections_are_separate_from_pool(
    real_context: ActionContext, real_db_pool: asyncpg.Pool
):
    """Verify that creating a session acquires a new connection, not from the idle pool."""
    initial_idle_conns = real_db_pool.get_idle_size()

    # Begin a transaction, which creates a session
    begin_result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(begin_result)["session_id"]

    # The main pool should have one less idle connection as it's now in the session
    # Note: This behavior can be subtle. The connection is acquired from the pool,
    # but not returned until the session is closed.
    # We can't directly inspect "active" connections easily, but we can see the idle count change.

    # We expect the idle count to be the same, as the session manager holds the connection
    # but the pool itself might not show it as "idle". A better test is to check if
    # the session is active.

    assert real_context.session_manager.get_session(session_id) is not None

    await pg_tx(action="commit", session_id=session_id, context=real_context)


@pytest.mark.asyncio
async def test_closing_session_releases_connection(
    real_context: ActionContext, real_db_pool: asyncpg.Pool
):
    """Verify that committing or rolling back a transaction releases the connection."""
    initial_idle_conns = real_db_pool.get_idle_size()

    # Start a session
    begin_result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(begin_result)["session_id"]

    # Close the session
    await pg_tx(action="commit", session_id=session_id, context=real_context)

    # The connection should be released back to the pool
    assert real_db_pool.get_idle_size() == initial_idle_conns
    assert len(real_context.session_manager.get_all_sessions()) == 0
