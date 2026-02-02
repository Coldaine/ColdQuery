"""
Mock-based handler tests.

These tests verify tool handlers work correctly using mocked database responses.
Fast execution, no database required.

Run: pytest tests/unit/test_mcp_protocol.py -v
"""
import pytest
import json
from typing import Any, Dict, List, Optional

from coldquery.core.executor import QueryResult


class MockQueryExecutor:
    """Mock executor that returns canned responses."""

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        self.responses = responses or {}
        self.executed_queries: List[str] = []

    async def execute(
        self, sql: str, params: Optional[List[Any]] = None, timeout_ms: Optional[int] = None
    ) -> QueryResult:
        self.executed_queries.append(sql)

        for pattern, response in self.responses.items():
            if pattern.lower() in sql.lower():
                return QueryResult(
                    rows=response.get("rows", []),
                    row_count=response.get("row_count", len(response.get("rows", []))),
                    fields=response.get("fields", []),
                )

        if sql.strip().upper().startswith("SELECT"):
            return QueryResult(rows=[{"result": 1}], row_count=1, fields=[])
        return QueryResult(rows=[], row_count=1, fields=[])

    async def disconnect(self, destroy: bool = False) -> None:
        pass

    async def create_session(self) -> "MockQueryExecutor":
        return self


class MockSessionData:
    def __init__(self, session_id: str, executor: MockQueryExecutor):
        self.id = session_id
        self.executor = executor
        self.expires_in = 30.0


class MockSessionManager:
    """Mock session manager matching SessionManager interface."""

    def __init__(self):
        self._sessions: Dict[str, MockSessionData] = {}
        self._counter = 0

    async def create_session(self) -> str:
        self._counter += 1
        session_id = f"mock-session-{self._counter}"
        self._sessions[session_id] = MockSessionData(session_id, MockQueryExecutor())
        return session_id

    def get_session(self, session_id: str) -> Optional[MockSessionData]:
        return self._sessions.get(session_id)

    def get_session_executor(self, session_id: str) -> Optional[MockQueryExecutor]:
        session = self._sessions.get(session_id)
        return session.executor if session else None

    async def close_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [{"id": sid, "idle_time_seconds": 0, "expires_in_seconds": 1800} for sid in self._sessions]


@pytest.fixture
def mock_executor():
    return MockQueryExecutor(responses={
        "select 1": {"rows": [{"test": 1}], "row_count": 1},
    })


@pytest.fixture
def mock_session_manager():
    return MockSessionManager()


@pytest.fixture
def mock_context(mock_executor, mock_session_manager):
    from coldquery.core.context import ActionContext
    return ActionContext(executor=mock_executor, session_manager=mock_session_manager)


class TestHandlersWithMocks:
    """Test handlers with mocked database - fast, no DB required."""

    async def test_read_returns_data(self, mock_context):
        from coldquery.actions.query.read import read_handler
        result = await read_handler({"sql": "SELECT 1 as test"}, mock_context)
        assert json.loads(result)["rows"][0]["test"] == 1

    async def test_health_check(self):
        from coldquery.actions.monitor.health import health_handler
        from coldquery.core.context import ActionContext

        executor = MockQueryExecutor(responses={
            "select 1": {"rows": [{"health_check": 1}], "row_count": 1}
        })
        ctx = ActionContext(executor=executor, session_manager=None)

        result = await health_handler({}, ctx)
        assert json.loads(result)["status"] == "ok"

    async def test_write_blocked_without_auth(self, mock_context):
        from coldquery.actions.query.write import write_handler

        with pytest.raises(PermissionError):
            await write_handler({"sql": "INSERT INTO test VALUES (1)"}, mock_context)

    async def test_write_allowed_with_autocommit(self, mock_context):
        from coldquery.actions.query.write import write_handler

        result = await write_handler({
            "sql": "INSERT INTO test VALUES (1)",
            "autocommit": True,
        }, mock_context)
        assert json.loads(result)["row_count"] == 1

    async def test_transaction_lifecycle(self, mock_context):
        from coldquery.actions.tx.lifecycle import begin_handler, commit_handler
        from coldquery.actions.query.write import write_handler

        # Begin
        result = await begin_handler({}, mock_context)
        session_id = json.loads(result)["session_id"]
        assert session_id.startswith("mock-session-")

        # Write
        await write_handler({"sql": "INSERT INTO test VALUES (1)", "session_id": session_id}, mock_context)

        # Commit
        result = await commit_handler({"session_id": session_id}, mock_context)
        assert json.loads(result)["status"] == "transaction committed"

    async def test_schema_list(self, mock_context):
        mock_context.executor.responses["information_schema"] = {
            "rows": [{"table_schema": "public", "table_name": "users"}]
        }
        from coldquery.actions.schema.list import list_handler

        result = await list_handler({"target": "table"}, mock_context)
        assert "rows" in json.loads(result)
