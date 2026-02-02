from unittest.mock import AsyncMock, MagicMock

import pytest

from coldquery.core.context import ActionContext
from coldquery.core.executor import QueryResult
from coldquery.resources.monitor_resources import activity_resource, health_resource
from coldquery.resources.schema_resources import table_resource, tables_resource


@pytest.fixture
def mock_context():
    mock_executor = AsyncMock()
    mock_session_manager = MagicMock()
    return ActionContext(executor=mock_executor, session_manager=mock_session_manager)

@pytest.mark.asyncio
async def test_tables_resource(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(
        rows=[{"schema": "public", "name": "users", "owner": "postgres"}],
        row_count=1,
        fields=[],
    )
    result = await tables_resource(mock_context)
    assert "users" in result

@pytest.mark.asyncio
async def test_table_resource(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.side_effect = [
        QueryResult(rows=[{"column_name": "id", "data_type": "integer"}], row_count=1, fields=[]),
        QueryResult(rows=[{"name": "users_pkey"}], row_count=1, fields=[]),
    ]
    result = await table_resource("public", "users", mock_context)
    assert "columns" in result

@pytest.mark.asyncio
async def test_health_resource(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(
        rows=[{"health_check": 1}],
        row_count=1,
        fields=[],
    )
    result = await health_resource(mock_context)
    assert '{"status": "ok"}' in result

@pytest.mark.asyncio
async def test_activity_resource(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(rows=[], row_count=0, fields=[])
    await activity_resource(mock_context)
    mock_executor.execute.assert_called_once()
