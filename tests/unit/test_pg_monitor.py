from unittest.mock import AsyncMock, MagicMock

import pytest

from coldquery.core.context import ActionContext
from coldquery.core.executor import QueryResult
from coldquery.tools.pg_monitor import pg_monitor


@pytest.fixture
def mock_context():
    mock_executor = AsyncMock()
    mock_session_manager = MagicMock()
    return ActionContext(executor=mock_executor, session_manager=mock_session_manager)

@pytest.mark.asyncio
async def test_health_check_ok(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(
        rows=[{"health_check": 1}],
        row_count=1,
        fields=[],
    )
    result = await pg_monitor(action="health", context=mock_context)
    assert '{"status": "ok"}' in result

@pytest.mark.asyncio
async def test_activity_queries_db(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(rows=[], row_count=0, fields=[])
    await pg_monitor(action="activity", context=mock_context)
    mock_executor.execute.assert_called_once()

@pytest.mark.asyncio
async def test_connections_queries_db(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(rows=[], row_count=0, fields=[])
    await pg_monitor(action="connections", context=mock_context)
    mock_executor.execute.assert_called_once()

@pytest.mark.asyncio
async def test_locks_queries_db(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(rows=[], row_count=0, fields=[])
    await pg_monitor(action="locks", context=mock_context)
    mock_executor.execute.assert_called_once()

@pytest.mark.asyncio
async def test_size_queries_db(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(rows=[], row_count=0, fields=[])
    await pg_monitor(action="size", context=mock_context)
    mock_executor.execute.assert_called_once()
