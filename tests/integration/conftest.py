
import pytest
import asyncpg
import os
import json
from typing import AsyncGenerator

from coldquery.core.context import ActionContext
from coldquery.core.executor import AsyncpgPoolExecutor
from coldquery.core.session import SessionManager
from coldquery.config import get_settings

# --- Real Database Fixtures ---

@pytest.fixture(scope="session")
def event_loop():
    """Force pytest-asyncio to use the same event loop for all tests."""
    import asyncio
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def db_settings():
    """Load database settings from environment variables."""
    return get_settings()

@pytest.fixture(scope="session")
async def real_db_pool(db_settings) -> AsyncGenerator[asyncpg.Pool, None]:
    """Create and tear down a real asyncpg connection pool."""
    pool = await asyncpg.create_pool(
        user=db_settings.db_user,
        password=db_settings.db_password.get_secret_value(),
        database=db_settings.db_database,
        host=db_settings.db_host,
        port=db_settings.db_port,
    )
    yield pool
    await pool.close()

@pytest.fixture
async def real_executor(real_db_pool: asyncpg.Pool) -> AsyncpgPoolExecutor:
    """Fixture for a real database executor."""
    return AsyncpgPoolExecutor(real_db_pool)

@pytest.fixture
async def real_session_manager(real_executor: AsyncpgPoolExecutor) -> SessionManager:
    """Fixture for a real session manager."""
    return SessionManager(real_executor)

@pytest.fixture
async def real_context(real_executor: AsyncpgPoolExecutor, real_session_manager: SessionManager) -> ActionContext:
    """Fixture for a real ActionContext."""
    return ActionContext(executor=real_executor, session_manager=real_session_manager)

@pytest.fixture(autouse=True)
async def cleanup_db(real_db_pool: asyncpg.Pool):
    """Clean up the database by dropping all tables in the public schema."""
    yield
    async with real_db_pool.acquire() as conn:
        await conn.execute("""
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """)
