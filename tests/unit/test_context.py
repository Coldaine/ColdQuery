from unittest.mock import MagicMock
import pytest
from fastmcp.exceptions import ToolError

from coldquery.core.context import ActionContext, resolve_executor
from coldquery.core.executor import QueryExecutor
from coldquery.core.session import SessionManager

@pytest.fixture
def mock_executor():
    return MagicMock(spec=QueryExecutor)

@pytest.fixture
def mock_session_manager():
    return MagicMock(spec=SessionManager)

@pytest.mark.asyncio
async def test_resolve_executor_no_session_id(mock_executor, mock_session_manager):
    ctx = ActionContext(executor=mock_executor, session_manager=mock_session_manager)

    resolved_executor = await resolve_executor(ctx, None)

    assert resolved_executor is mock_executor
    mock_session_manager.get_session_executor.assert_not_called()

@pytest.mark.asyncio
async def test_resolve_executor_with_valid_session_id(mock_executor, mock_session_manager):
    mock_session_executor = MagicMock(spec=QueryExecutor)
    mock_session_manager.get_session_executor.return_value = mock_session_executor

    ctx = ActionContext(executor=mock_executor, session_manager=mock_session_manager)

    resolved_executor = await resolve_executor(ctx, "valid_session")

    assert resolved_executor is mock_session_executor
    mock_session_manager.get_session_executor.assert_called_once_with("valid_session")

@pytest.mark.asyncio
async def test_resolve_executor_with_invalid_session_id(mock_executor, mock_session_manager):
    mock_session_manager.get_session_executor.return_value = None

    ctx = ActionContext(executor=mock_executor, session_manager=mock_session_manager)

    with pytest.raises(ToolError, match="Invalid or expired session: invalid_session"):
        await resolve_executor(ctx, "invalid_session")

    mock_session_manager.get_session_executor.assert_called_once_with("invalid_session")
