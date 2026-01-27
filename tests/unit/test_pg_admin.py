import pytest
from unittest.mock import MagicMock, AsyncMock
from coldquery.tools.pg_admin import pg_admin
from coldquery.core.context import ActionContext
from coldquery.core.executor import QueryResult

@pytest.fixture
def mock_context():
    mock_executor = AsyncMock()
    mock_session_manager = MagicMock()
    return ActionContext(executor=mock_executor, session_manager=mock_session_manager)

@pytest.mark.asyncio
async def test_vacuum_requires_auth(mock_context):
    with pytest.raises(PermissionError):
        await pg_admin(action="vacuum", table="users", context=mock_context, autocommit=False)

@pytest.mark.asyncio
async def test_stats_handler_requires_table(mock_context):
    with pytest.raises(ValueError, match="'table' is required for stats action"):
        await pg_admin(action="stats", context=mock_context)

@pytest.mark.asyncio
async def test_reindex_requires_table(mock_context):
    with pytest.raises(ValueError, match="'table' parameter is required for reindex action"):
        await pg_admin(action="reindex", context=mock_context, autocommit=True)

@pytest.mark.asyncio
async def test_settings_set_requires_auth(mock_context):
    with pytest.raises(PermissionError):
        await pg_admin(action="settings", setting_name="work_mem", setting_value="16MB", context=mock_context, autocommit=False)

@pytest.mark.asyncio
async def test_settings_get_is_readonly(mock_context):
    mock_executor = mock_context.executor
    mock_executor.execute.return_value = QueryResult(
        rows=[{"work_mem": "4MB"}],
        row_count=1,
        fields=[],
    )
    await pg_admin(action="settings", setting_name="work_mem", context=mock_context)
    mock_executor.execute.assert_called_once()
