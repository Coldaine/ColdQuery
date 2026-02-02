"""
Testcontainers-based fixtures for integration testing.

This spins up an ephemeral PostgreSQL container automatically.
No pre-existing database required - just Docker.

Requirements:
- Docker daemon must be running
- pip install testcontainers[postgres]

Run: pytest tests/conftest_testcontainers.py -v
"""
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator

# Check if Docker is available
DOCKER_AVAILABLE = False
DOCKER_ERROR = None

try:
    import docker
    client = docker.from_env()
    client.ping()
    DOCKER_AVAILABLE = True
except Exception as e:
    DOCKER_ERROR = str(e)

# Skip all tests in this module if Docker isn't available
pytestmark = pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason=f"Docker not available: {DOCKER_ERROR}"
)


# ============================================================================
# Testcontainers Fixtures - Real ephemeral PostgreSQL
# ============================================================================

@pytest.fixture(scope="session")
def postgres_container():
    """
    Spin up a PostgreSQL container for the entire test session.

    This gives you a REAL PostgreSQL database that:
    - Starts automatically before tests
    - Is completely isolated (fresh each run)
    - Cleans up automatically after tests
    - Requires only Docker, no manual setup
    """
    if not DOCKER_AVAILABLE:
        pytest.skip(f"Docker not available: {DOCKER_ERROR}")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        image="postgres:16",
        username="test_user",
        password="test_pass",
        dbname="test_db",
    ) as postgres:
        # Override environment variables BEFORE any executor is used
        os.environ["DB_HOST"] = postgres.get_container_host_ip()
        os.environ["DB_PORT"] = postgres.get_exposed_port(5432)
        os.environ["DB_USER"] = postgres.username
        os.environ["DB_PASSWORD"] = postgres.password
        os.environ["DB_DATABASE"] = postgres.dbname

        yield postgres


@pytest_asyncio.fixture
async def tc_executor(postgres_container):
    """
    Fresh executor connected to the Testcontainers PostgreSQL.

    Creates a NEW executor instance (not the singleton) to avoid
    test pollution.
    """
    from coldquery.core.executor import AsyncpgPoolExecutor

    # Create fresh instance, not the singleton
    executor = AsyncpgPoolExecutor()

    yield executor

    # Cleanup
    await executor.disconnect(destroy=True)


@pytest_asyncio.fixture
async def tc_context(tc_executor):
    """
    Full ActionContext connected to ephemeral PostgreSQL.
    """
    from coldquery.core.session import SessionManager
    from coldquery.core.context import ActionContext

    session_manager = SessionManager(tc_executor)
    ctx = ActionContext(executor=tc_executor, session_manager=session_manager)

    yield ctx


@pytest_asyncio.fixture
async def tc_clean_db(tc_executor):
    """
    Ensure a clean database state before each test.
    Drops all user-created tables.
    """
    # Get list of tables
    result = await tc_executor.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
    """)

    # Drop each table
    for row in result.rows:
        table = row["tablename"]
        await tc_executor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')

    yield

    # Cleanup after test (optional, container will be destroyed anyway)


# ============================================================================
# Tests using Testcontainers
# ============================================================================

class TestWithTestcontainers:
    """
    These tests run against a REAL PostgreSQL in Docker.

    Run with: pytest tests/conftest_testcontainers.py -v

    Requirements:
    - Docker daemon must be running
    - pip install testcontainers[postgres]
    """

    async def test_health_check(self, tc_context):
        """Test that we can connect to the ephemeral database."""
        from coldquery.actions.monitor.health import health_handler
        import json

        result = await health_handler({}, tc_context)
        data = json.loads(result)

        assert data["status"] == "ok"

    async def test_create_and_query_table(self, tc_context, tc_clean_db):
        """Test full write → read cycle."""
        from coldquery.actions.query.write import write_handler
        from coldquery.actions.query.read import read_handler
        import json

        # Create table
        await write_handler({
            "sql": "CREATE TABLE test_items (id INT, name TEXT)",
            "autocommit": True,
        }, tc_context)

        # Insert data
        await write_handler({
            "sql": "INSERT INTO test_items VALUES (1, 'hello')",
            "autocommit": True,
        }, tc_context)

        # Query data
        result = await read_handler({
            "sql": "SELECT * FROM test_items"
        }, tc_context)
        data = json.loads(result)

        assert len(data["rows"]) == 1
        assert data["rows"][0]["name"] == "hello"

    async def test_transaction_commit(self, tc_context, tc_clean_db):
        """Test transaction lifecycle."""
        from coldquery.actions.tx.lifecycle import begin_handler, commit_handler
        from coldquery.actions.query.write import write_handler
        from coldquery.actions.query.read import read_handler
        import json

        # Create table first
        await write_handler({
            "sql": "CREATE TABLE tx_test (val TEXT)",
            "autocommit": True,
        }, tc_context)

        # Begin transaction
        result = await begin_handler({}, tc_context)
        session_id = json.loads(result)["session_id"]

        # Insert in transaction
        await write_handler({
            "sql": "INSERT INTO tx_test VALUES ('in_tx')",
            "session_id": session_id,
        }, tc_context)

        # Commit
        await commit_handler({"session_id": session_id}, tc_context)

        # Verify
        result = await read_handler({"sql": "SELECT * FROM tx_test"}, tc_context)
        data = json.loads(result)

        assert data["rows"][0]["val"] == "in_tx"

    async def test_transaction_rollback(self, tc_context, tc_clean_db):
        """Test that rollback discards changes."""
        from coldquery.actions.tx.lifecycle import begin_handler, rollback_handler
        from coldquery.actions.query.write import write_handler
        from coldquery.actions.query.read import read_handler
        import json

        # Create table first
        await write_handler({
            "sql": "CREATE TABLE rollback_test (val TEXT)",
            "autocommit": True,
        }, tc_context)

        # Begin transaction
        result = await begin_handler({}, tc_context)
        session_id = json.loads(result)["session_id"]

        # Insert in transaction
        await write_handler({
            "sql": "INSERT INTO rollback_test VALUES ('should_disappear')",
            "session_id": session_id,
        }, tc_context)

        # Rollback instead of commit
        await rollback_handler({"session_id": session_id}, tc_context)

        # Verify data was NOT persisted
        result = await read_handler({"sql": "SELECT * FROM rollback_test"}, tc_context)
        data = json.loads(result)

        assert len(data["rows"]) == 0

    async def test_default_deny_policy(self, tc_context):
        """Test that writes without auth are blocked."""
        from coldquery.actions.query.write import write_handler

        with pytest.raises(PermissionError):
            await write_handler({
                "sql": "CREATE TABLE should_fail (id INT)",
                # No autocommit, no session_id
            }, tc_context)

    async def test_parameterized_query(self, tc_context, tc_clean_db):
        """Test parameterized queries with $1, $2 placeholders."""
        from coldquery.actions.query.write import write_handler
        from coldquery.actions.query.read import read_handler
        import json

        # Create table
        await write_handler({
            "sql": "CREATE TABLE params_test (id INT, name TEXT)",
            "autocommit": True,
        }, tc_context)

        # Insert with parameters
        await write_handler({
            "sql": "INSERT INTO params_test VALUES ($1, $2)",
            "params": [42, "parameterized"],
            "autocommit": True,
        }, tc_context)

        # Query with parameters
        result = await read_handler({
            "sql": "SELECT * FROM params_test WHERE id = $1",
            "params": [42],
        }, tc_context)
        data = json.loads(result)

        assert len(data["rows"]) == 1
        assert data["rows"][0]["name"] == "parameterized"
