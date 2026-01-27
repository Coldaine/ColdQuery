from unittest.mock import AsyncMock, MagicMock
import pytest

from coldquery.core.executor import AsyncpgPoolExecutor, AsyncpgSessionExecutor, QueryResult

@pytest.fixture
def mock_asyncpg_connection():
    mock = MagicMock()

    # Create a mock record that behaves like a dict when dict() is called on it
    mock_record = MagicMock()
    mock_record.keys.return_value = ["id"]
    mock_record.__getitem__.side_effect = lambda k: 1 if k == "id" else None
    mock_record.__iter__.return_value = iter(["id"])

    # Create mock result list with columns attribute
    mock_result = [mock_record]
    mock_result_with_columns = MagicMock()
    mock_result_with_columns.__iter__.return_value = iter(mock_result)
    mock_result_with_columns.__len__.return_value = 1

    mock_column = MagicMock()
    mock_column.name = "id"
    mock_column.type.__name__ = "int4"
    mock_result_with_columns.columns = [mock_column]

    mock.fetch = AsyncMock(return_value=mock_result_with_columns)

    # For DML statements, execute returns a status string
    mock.execute = AsyncMock(return_value="INSERT 0 1")

    mock.close = AsyncMock()
    mock.release = AsyncMock()
    return mock

@pytest.mark.asyncio
async def test_asyncpg_session_executor_execute_select(mock_asyncpg_connection):
    executor = AsyncpgSessionExecutor(mock_asyncpg_connection)
    result = await executor.execute("SELECT 1")

    assert isinstance(result, QueryResult)
    assert result.rows == [{"id": 1}]
    assert result.row_count == 1
    assert result.fields == [{"name": "id", "type": "int4"}]
    mock_asyncpg_connection.fetch.assert_awaited_once_with("SELECT 1")

@pytest.mark.asyncio
async def test_asyncpg_session_executor_execute_dml(mock_asyncpg_connection):
    executor = AsyncpgSessionExecutor(mock_asyncpg_connection)
    result = await executor.execute("INSERT INTO my_table VALUES (1)")

    assert isinstance(result, QueryResult)
    assert result.rows == []
    assert result.row_count == 1
    assert result.fields == []
    mock_asyncpg_connection.execute.assert_awaited_once_with("INSERT INTO my_table VALUES (1)")

@pytest.mark.asyncio
async def test_asyncpg_session_executor_disconnect(mock_asyncpg_connection):
    executor = AsyncpgSessionExecutor(mock_asyncpg_connection)
    await executor.disconnect()
    mock_asyncpg_connection.close.assert_awaited_once()

@pytest.fixture
def mock_asyncpg_pool(mock_asyncpg_connection):
    mock_pool = MagicMock()

    # The object returned by `acquire()` must be an async context manager
    # that can also be awaited directly.
    class AcquireMock(AsyncMock):
        async def __aenter__(self):
            return self.return_value

        async def __aexit__(self, *args):
            pass

        def __await__(self):
            async def inner():
                return self.return_value
            return inner().__await__()

    acquire_mock = AcquireMock(return_value=mock_asyncpg_connection)
    mock_pool.acquire.return_value = acquire_mock
    mock_pool.release = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_pool.terminate = AsyncMock()
    return mock_pool

@pytest.mark.asyncio
async def test_asyncpg_pool_executor_execute(monkeypatch, mock_asyncpg_pool):
    # Mock the create_pool function
    mock_create_pool = AsyncMock(return_value=mock_asyncpg_pool)
    monkeypatch.setattr("asyncpg.create_pool", mock_create_pool)

    executor = AsyncpgPoolExecutor()
    result = await executor.execute("SELECT 1")

    assert isinstance(result, QueryResult)
    mock_create_pool.assert_awaited_once()
    mock_asyncpg_pool.acquire.assert_called_once()

@pytest.mark.asyncio
async def test_asyncpg_pool_executor_disconnect(monkeypatch, mock_asyncpg_pool):
    mock_create_pool = AsyncMock(return_value=mock_asyncpg_pool)
    monkeypatch.setattr("asyncpg.create_pool", mock_create_pool)

    executor = AsyncpgPoolExecutor()
    await executor._get_pool() # Ensure the pool is created
    await executor.disconnect()

    mock_asyncpg_pool.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_asyncpg_pool_executor_create_session(monkeypatch, mock_asyncpg_pool):
    mock_create_pool = AsyncMock(return_value=mock_asyncpg_pool)
    monkeypatch.setattr("asyncpg.create_pool", mock_create_pool)

    executor = AsyncpgPoolExecutor()
    session_executor = await executor.create_session()

    assert isinstance(session_executor, AsyncpgSessionExecutor)
    mock_asyncpg_pool.acquire.assert_called_once()
