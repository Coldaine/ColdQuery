import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coldquery.actions.query.explain import explain_handler
from coldquery.actions.query.read import read_handler
from coldquery.actions.query.transaction import transaction_handler
from coldquery.actions.query.write import write_handler
from coldquery.core.context import ActionContext
from coldquery.core.executor import QueryResult
from coldquery.core.session import SessionData as Session
from coldquery.core.session import SessionManager
from coldquery.middleware.session_echo import enrich_response
from coldquery.tools.pg_query import pg_query

# Mocks
mock_executor = AsyncMock()
mock_session_manager = MagicMock(spec=SessionManager)
mock_session_manager.get_session = MagicMock()
mock_context = ActionContext(
    executor=mock_executor, session_manager=mock_session_manager
)


@pytest.fixture(autouse=True)
def reset_mocks():
    mock_executor.reset_mock()
    mock_session_manager.reset_mock()


# Test Cases
@pytest.mark.asyncio
async def test_read_action_returns_rows():
    mock_executor.execute.return_value = QueryResult(
        rows=[{"id": 1}], row_count=1, fields=[]
    )
    params = {"sql": "SELECT * FROM users"}
    result = await read_handler(params, mock_context)
    data = json.loads(result)
    assert data["rows"] == [{"id": 1}]
    mock_executor.execute.assert_called_once_with("SELECT * FROM users", None)


@pytest.mark.asyncio
async def test_read_action_missing_sql():
    with pytest.raises(ValueError, match="'sql' parameter is required"):
        await read_handler({}, mock_context)


@pytest.mark.asyncio
async def test_write_action_blocked_without_auth():
    with pytest.raises(PermissionError, match="Safety Check Failed"):
        await write_handler({"sql": "DELETE FROM users"}, mock_context)


@pytest.mark.asyncio
async def test_write_action_succeeds_with_autocommit():
    mock_executor.execute.return_value = QueryResult(
        rows=[], row_count=1, fields=[]
    )
    params = {"sql": "DELETE FROM users", "autocommit": True}
    await write_handler(params, mock_context)
    mock_executor.execute.assert_called_once()


@pytest.mark.asyncio
async def test_write_action_succeeds_with_session_id():
    mock_session_executor = AsyncMock()
    mock_session_executor.execute.return_value = QueryResult(
        rows=[], row_count=1, fields=[]
    )
    mock_session_manager.get_session_executor.return_value = mock_session_executor
    mock_session = MagicMock()
    mock_session.expires_in = 10
    mock_session_manager.get_session.return_value = mock_session
    params = {"sql": "DELETE FROM users", "session_id": "test_session"}
    await write_handler(params, mock_context)
    mock_session_executor.execute.assert_called_once()


@pytest.mark.asyncio
async def test_write_action_missing_sql():
    with pytest.raises(ValueError, match="'sql' parameter is required"):
        await write_handler({"autocommit": True}, mock_context)


@pytest.mark.asyncio
async def test_explain_builds_correct_sql_with_analyze():
    params = {"sql": "SELECT 1", "analyze": True}
    await explain_handler(params, mock_context)
    mock_executor.execute.assert_called_with(
        "EXPLAIN ANALYZE FORMAT JSON SELECT 1", None
    )


@pytest.mark.asyncio
async def test_explain_builds_correct_sql_without_analyze():
    params = {"sql": "SELECT 1", "analyze": False}
    await explain_handler(params, mock_context)
    mock_executor.execute.assert_called_with("EXPLAIN FORMAT JSON SELECT 1", None)


@pytest.mark.asyncio
async def test_explain_action_missing_sql():
    with pytest.raises(ValueError, match="'sql' parameter is required"):
        await explain_handler({}, mock_context)


@pytest.mark.asyncio
async def test_transaction_commits_batch():
    mock_session_manager.create_session.return_value = "temp_session"
    mock_session_manager.get_session_executor.return_value = mock_executor
    mock_executor.execute.return_value = QueryResult(rows=[], row_count=1, fields=[])
    mock_session = MagicMock()
    mock_session.expires_in = 10
    mock_session_manager.get_session.return_value = mock_session
    operations = [
        {"sql": "INSERT INTO users VALUES (1)"},
        {"sql": "UPDATE users SET name = 'test' WHERE id = 1"},
    ]
    params = {"operations": operations}

    await transaction_handler(params, mock_context)

    assert mock_executor.execute.call_count == 4  # BEGIN, INSERT, UPDATE, COMMIT
    mock_session_manager.close_session.assert_called_with("temp_session")


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_failure():
    mock_session_manager.create_session.return_value = "temp_session"
    mock_session_manager.get_session_executor.return_value = mock_executor
    mock_executor.execute.side_effect = [
        None,  # BEGIN
        None,  # INSERT
        RuntimeError("DB error"),  # UPDATE fails
        None,  # ROLLBACK
    ]
    operations = [
        {"sql": "INSERT INTO users VALUES (1)"},
        {"sql": "UPDATE users SET name = 'test' WHERE id = 1"},
    ]
    params = {"operations": operations}

    with pytest.raises(RuntimeError, match="Transaction failed at operation 1"):
        await transaction_handler(params, mock_context)

    assert mock_executor.execute.call_count == 4  # BEGIN, INSERT, ROLLBACK
    mock_session_manager.close_session.assert_called_with("temp_session")


@pytest.mark.asyncio
async def test_transaction_action_missing_operations():
    with pytest.raises(ValueError, match="'operations' parameter is required"):
        await transaction_handler({}, mock_context)


@pytest.mark.asyncio
async def test_pg_query_tool_dispatches_to_correct_handler():
    mock_executor.execute.return_value = QueryResult(
        rows=[], row_count=0, fields=[]
    )
    mock_session_manager.get_session_executor.return_value = mock_executor
    mock_executor.execute.side_effect = None
    await pg_query(action="read", sql="SELECT 1", context=mock_context)
    mock_executor.execute.assert_called_once_with("SELECT 1", None)


@pytest.mark.asyncio
async def test_pg_query_tool_unknown_action():
    with pytest.raises(ValueError, match="Unknown action: foo"):
        await pg_query(action="foo", sql="SELECT 1", context=mock_context)


@pytest.mark.asyncio
async def test_middleware_enrich_response_near_expiry():
    mock_session = MagicMock()
    mock_session.id = "test_session"
    mock_session.expires_in = 4
    mock_session_manager.get_session.return_value = mock_session

    result = {"rows": []}
    enriched_result = enrich_response(
        result, "test_session", mock_session_manager
    )
    data = json.loads(enriched_result)
    assert "active_session" in data
    assert data["active_session"]["hint"] == "Warning: Session expiring soon. Commit your work shortly."

@pytest.mark.asyncio
async def test_middleware_enrich_response_not_near_expiry():
    mock_session = MagicMock()
    mock_session.id = "test_session"
    mock_session.expires_in = 10
    mock_session_manager.get_session.return_value = mock_session

    result = {"rows": []}
    enriched_result = enrich_response(
        result, "test_session", mock_session_manager
    )
    data = json.loads(enriched_result)
    assert "active_session" not in data

@pytest.mark.asyncio
async def test_middleware_enrich_response_no_session_id():
    result = {"rows": []}
    enriched_result = enrich_response(
        result, None, mock_session_manager
    )
    data = json.loads(enriched_result)
    assert "active_session" not in data
