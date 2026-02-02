"""
Shared pytest fixtures for ColdQuery tests.

This file provides:
1. Testcontainers fixtures for ephemeral PostgreSQL (requires Docker)
2. Pytest markers configuration
"""
import os
import pytest
import pytest_asyncio


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")


# =============================================================================
# Docker/Testcontainers Availability Check
# =============================================================================

DOCKER_AVAILABLE = False
DOCKER_ERROR = None

try:
    import docker
    client = docker.from_env()
    client.ping()
    DOCKER_AVAILABLE = True
except Exception as e:
    DOCKER_ERROR = str(e)


# =============================================================================
# Testcontainers Fixtures (require Docker)
# =============================================================================

@pytest.fixture(scope="session")
def postgres_container():
    """
    Spin up a PostgreSQL container for the entire test session.

    Skips automatically if Docker is not available.
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
        os.environ["DB_HOST"] = postgres.get_container_host_ip()
        os.environ["DB_PORT"] = postgres.get_exposed_port(5432)
        os.environ["DB_USER"] = postgres.username
        os.environ["DB_PASSWORD"] = postgres.password
        os.environ["DB_DATABASE"] = postgres.dbname
        yield postgres


@pytest_asyncio.fixture
async def tc_executor(postgres_container):
    """Fresh executor connected to Testcontainers PostgreSQL."""
    from coldquery.core.executor import AsyncpgPoolExecutor

    executor = AsyncpgPoolExecutor()
    yield executor
    await executor.disconnect(destroy=True)


@pytest_asyncio.fixture
async def tc_context(tc_executor):
    """Full ActionContext connected to ephemeral PostgreSQL."""
    from coldquery.core.session import SessionManager
    from coldquery.core.context import ActionContext

    session_manager = SessionManager(tc_executor)
    yield ActionContext(executor=tc_executor, session_manager=session_manager)


@pytest_asyncio.fixture
async def tc_clean_db(tc_executor):
    """Drop all user tables before test."""
    result = await tc_executor.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    for row in result.rows:
        await tc_executor.execute(f'DROP TABLE IF EXISTS "{row["tablename"]}" CASCADE')
    yield
