"""
Integration test fixtures for ColdQuery with REAL PostgreSQL database.

KNOWN ISSUES (Tests Currently Failing):
---------------------------------------
These integration tests are INTENTIONALLY FAILING due to async/event loop bugs
that need to be fixed. They are committed to main to make the technical debt
visible and trackable.

Root Causes:
1. Event loop management: "RuntimeError: Future attached to different loop"
   - Fixture cleanup happens in wrong event loop context
   - Affects ALL tests during teardown

2. Connection lifecycle: "InterfaceError: connection has been released back to pool"
   - Session cleanup tries to close already-released connections
   - Affects 9/13 tests

3. Missing API: SessionManager.get_all_sessions() doesn't exist
   - Should use list_sessions() instead
   - Affects 1 test

See docs/OBSERVATIONS.md and GitHub Issue #29 for detailed analysis.

TODO: Fix these issues before considering integration tests production-ready.
"""

import pytest
import asyncpg
import os
import json
from typing import AsyncGenerator

from coldquery.core.context import ActionContext
from coldquery.core.executor import AsyncpgPoolExecutor
from coldquery.core.session import SessionManager

# --- Real Database Fixtures ---
# NOTE: These fixtures have async lifecycle bugs - see module docstring above

@pytest.fixture(scope="session")
async def real_db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Create and tear down a real asyncpg connection pool."""
    pool = await asyncpg.create_pool(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5433")),
        user=os.environ.get("DB_USER", "mcp"),
        password=os.environ.get("DB_PASSWORD", "mcp"),
        database=os.environ.get("DB_DATABASE", "mcp_test"),
    )
    yield pool
    await pool.close()

@pytest.fixture
async def real_executor() -> AsyncGenerator[AsyncpgPoolExecutor, None]:
    """Fixture for a real database executor."""
    executor = AsyncpgPoolExecutor()
    yield executor
    await executor.disconnect()

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
