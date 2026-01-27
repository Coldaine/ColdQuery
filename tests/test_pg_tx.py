import pytest
from unittest.mock import MagicMock, AsyncMock
from coldquery.tools.pg_tx import pg_tx
from coldquery.core.context import ActionContext

@pytest.fixture
def mock_context():
    mock_executor = AsyncMock()
    mock_session_manager = MagicMock()

    # Make async methods awaitable
    mock_session_manager.create_session = AsyncMock(return_value="test-session-123")
    mock_session_manager.close_session = AsyncMock()

    mock_session_manager.get_session_executor.return_value = mock_executor

    # for enrich_response mock
    mock_session = MagicMock()
    mock_session.expires_in = 10
    mock_session_manager.get_session.return_value = mock_session

    return ActionContext(executor=mock_executor, session_manager=mock_session_manager)

@pytest.mark.asyncio
async def test_begin_creates_session(mock_context):
    result = await pg_tx(action="begin", context=mock_context)
    assert "test-session-123" in result
    mock_context.session_manager.create_session.assert_called_once()

@pytest.mark.asyncio
async def test_commit_closes_session(mock_context):
    await pg_tx(action="commit", session_id="test-session", context=mock_context)
    mock_context.session_manager.close_session.assert_called_once_with("test-session")

@pytest.mark.asyncio
async def test_rollback_closes_session(mock_context):
    await pg_tx(action="rollback", session_id="test-session", context=mock_context)
    mock_context.session_manager.close_session.assert_called_once_with("test-session")

@pytest.mark.asyncio
async def test_savepoint_sanitizes_name(mock_context):
    executor = mock_context.session_manager.get_session_executor("test")
    await pg_tx(action="savepoint", session_id="test", savepoint_name="my_savepoint", context=mock_context)
    # The sanitize_identifier function will add quotes to the identifier
    executor.execute.assert_called_with('SAVEPOINT "my_savepoint"')

@pytest.mark.asyncio
async def test_list_returns_sessions(mock_context):
    mock_context.session_manager.list_sessions.return_value = [
        {"id": "session-1", "idle_time": 10, "expires_in": 1790}
    ]
    result = await pg_tx(action="list", context=mock_context)
    assert "session-1" in result
