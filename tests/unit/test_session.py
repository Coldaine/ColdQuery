import asyncio
from unittest.mock import MagicMock, AsyncMock
import pytest

from coldquery.core.session import SessionManager, MAX_SESSIONS
from coldquery.core.executor import QueryExecutor

@pytest.fixture
def mock_pool_executor():
    mock = MagicMock(spec=QueryExecutor)
    mock.create_session = AsyncMock()
    return mock

@pytest.mark.asyncio
async def test_create_session_success(mock_pool_executor):
    session_manager = SessionManager(mock_pool_executor)
    session_id = await session_manager.create_session()
    assert session_id is not None
    assert len(session_manager._sessions) == 1
    mock_pool_executor.create_session.assert_awaited_once()

@pytest.mark.asyncio
async def test_create_session_max_sessions(mock_pool_executor):
    session_manager = SessionManager(mock_pool_executor)
    session_manager._sessions = {f"session_{i}": MagicMock() for i in range(MAX_SESSIONS)}

    with pytest.raises(RuntimeError, match="Maximum number of concurrent sessions reached."):
        await session_manager.create_session()

@pytest.mark.asyncio
async def test_get_session_executor_valid(mock_pool_executor):
    session_manager = SessionManager(mock_pool_executor)
    session_id = await session_manager.create_session()

    executor = session_manager.get_session_executor(session_id)
    assert executor is not None

@pytest.mark.asyncio
async def test_get_session_executor_invalid():
    session_manager = SessionManager(MagicMock())
    executor = session_manager.get_session_executor("invalid_id")
    assert executor is None

@pytest.mark.asyncio
async def test_close_session(mock_pool_executor):
    session_manager = SessionManager(mock_pool_executor)
    session_id = await session_manager.create_session()

    # Get the mock executor to check if disconnect is called
    mock_session_executor = session_manager.get_session_executor(session_id)
    mock_session_executor.disconnect = AsyncMock()

    await session_manager.close_session(session_id)
    assert len(session_manager._sessions) == 0
    mock_session_executor.disconnect.assert_awaited_once_with(destroy=True)

@pytest.mark.asyncio
async def test_session_expiry(mock_pool_executor):
    # This requires a bit of manipulation to test the timer
    session_manager = SessionManager(mock_pool_executor)

    # Mock the event loop's call_later
    loop = asyncio.get_running_loop()
    loop.call_later = MagicMock()

    session_id = await session_manager.create_session()

    # Assert that the timer was set
    loop.call_later.assert_called_once()
    delay, callback = loop.call_later.call_args[0]

    # Simulate the timer expiring
    session_manager._expire_session = AsyncMock()
    callback() # This will create a task to call _expire_session
    await asyncio.sleep(0) # Allow the task to run

    session_manager._expire_session.assert_awaited_once_with(session_id)
