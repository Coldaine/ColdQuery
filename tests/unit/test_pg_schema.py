import pytest
from unittest.mock import MagicMock, AsyncMock
from coldquery.tools.pg_schema import pg_schema
from coldquery.core.context import ActionContext
from coldquery.core.executor import QueryResult

@pytest.fixture
def mock_context():
    mock_executor = AsyncMock()
    mock_session_manager = MagicMock()
    return ActionContext(executor=mock_executor, session_manager=mock_session_manager)

@pytest.mark.asyncio
async def test_list_tables(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(
        rows=[{"schema": "public", "name": "users", "owner": "postgres"}],
        row_count=1,
        fields=[],
    )

    result = await pg_schema(action="list", target="table", context=mock_context)
    assert "users" in result

@pytest.mark.asyncio
async def test_describe_table(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.side_effect = [
        QueryResult(rows=[{"column_name": "id", "data_type": "integer"}], row_count=1, fields=[]),
        QueryResult(rows=[{"name": "users_pkey"}], row_count=1, fields=[]),
    ]

    result = await pg_schema(action="describe", name="users", context=mock_context)
    assert "columns" in result

@pytest.mark.asyncio
async def test_create_requires_auth(mock_context):
    with pytest.raises(PermissionError):
        await pg_schema(action="create", sql="CREATE TABLE test (id INT)", context=mock_context)
