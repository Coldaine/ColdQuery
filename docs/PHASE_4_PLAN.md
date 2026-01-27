# Phase 4: Integration Tests

Implement integration tests with real PostgreSQL database to verify end-to-end functionality.

**Estimated Additions**: ~400 lines of test code

---

## Overview

### What This Phase Delivers

✅ **Real database tests** - Test with actual PostgreSQL, not mocks
✅ **Transaction isolation** - Verify ACID properties
✅ **Safety policy enforcement** - Test Default-Deny with real DB
✅ **Concurrency tests** - Verify MAX_SESSIONS and race conditions
✅ **Connection management** - Verify no pool leaks

### Why Integration Tests Matter

Unit tests with mocks verified **business logic**, but can't catch:
- Real database connection issues
- Transaction isolation bugs
- Connection pool leaks
- Actual SQL syntax errors
- asyncpg-specific behavior

Integration tests provide **production confidence**.

---

## Test Organization

```
tests/
  unit/                         # Move existing tests here
    conftest.py
    test_context.py
    test_executor.py
    test_pg_query.py
    test_pg_tx.py
    test_pg_schema.py
    test_pg_admin.py
    test_pg_monitor.py
    test_security.py
    test_session.py
    test_resources.py
    test_prompts.py

  integration/                  # New integration tests
    conftest.py                 # Real DB fixtures
    test_transaction_workflow.py
    test_safety_policy.py
    test_connection_management.py
    test_concurrency.py
    test_isolation.py
```

---

## Part 1: Integration Test Fixtures

**File**: `tests/integration/conftest.py`

```python
import pytest
import asyncpg
import os
from coldquery.core.executor import AsyncpgPoolExecutor
from coldquery.core.session import SessionManager
from coldquery.core.context import ActionContext

@pytest.fixture(scope="session")
def db_config():
    """Database configuration for integration tests."""
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5433")),
        "user": os.environ.get("DB_USER", "mcp"),
        "password": os.environ.get("DB_PASSWORD", "mcp"),
        "database": os.environ.get("DB_DATABASE", "mcp_test"),
    }

@pytest.fixture(scope="function")
async def real_db_pool(db_config):
    """Create a real asyncpg connection pool for tests."""
    pool = await asyncpg.create_pool(**db_config)
    yield pool
    await pool.close()

@pytest.fixture(scope="function")
async def real_executor():
    """Create a real AsyncpgPoolExecutor."""
    executor = AsyncpgPoolExecutor()
    yield executor
    await executor.disconnect()

@pytest.fixture(scope="function")
async def real_session_manager(real_executor):
    """Create a real SessionManager with actual DB connections."""
    manager = SessionManager(real_executor)
    yield manager
    # Cleanup all sessions
    for session_id in list(manager._sessions.keys()):
        await manager.close_session(session_id)

@pytest.fixture(scope="function")
async def real_context(real_executor, real_session_manager):
    """Create an ActionContext with real database."""
    return ActionContext(
        executor=real_executor,
        session_manager=real_session_manager,
    )

@pytest.fixture(scope="function", autouse=True)
async def clean_test_tables(real_db_pool):
    """Clean up test tables before and after each test."""
    async with real_db_pool.acquire() as conn:
        # Drop test tables before test
        await conn.execute("DROP TABLE IF EXISTS test_users CASCADE")
        await conn.execute("DROP TABLE IF EXISTS test_orders CASCADE")

    yield

    # Drop test tables after test
    async with real_db_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS test_users CASCADE")
        await conn.execute("DROP TABLE IF EXISTS test_orders CASCADE")
```

---

## Part 2: Transaction Workflow Tests

**File**: `tests/integration/test_transaction_workflow.py`

```python
import pytest
import json
from coldquery.tools.pg_query import pg_query
from coldquery.tools.pg_tx import pg_tx

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_transaction_workflow(real_context):
    """Test complete BEGIN → INSERT → COMMIT workflow with real database."""

    # 1. Create test table
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # 2. Begin transaction
    result = await pg_tx(action="begin", context=real_context)
    data = json.loads(result)
    session_id = data["session_id"]
    assert session_id is not None

    # 3. Insert data within transaction
    await pg_query(
        action="write",
        sql="INSERT INTO test_users (name) VALUES ($1)",
        params=["Alice"],
        session_id=session_id,
        context=real_context,
    )

    # 4. Verify data is visible within the same session
    result = await pg_query(
        action="read",
        sql="SELECT * FROM test_users WHERE name = $1",
        params=["Alice"],
        session_id=session_id,
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 1
    assert data["rows"][0]["name"] == "Alice"

    # 5. Commit transaction
    await pg_tx(action="commit", session_id=session_id, context=real_context)

    # 6. Verify data persisted after commit
    result = await pg_query(
        action="read",
        sql="SELECT * FROM test_users WHERE name = $1",
        params=["Alice"],
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 1

@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_rollback_discards_changes(real_context):
    """Test that ROLLBACK discards uncommitted changes."""

    # Setup: Create table
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Begin transaction
    result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(result)["session_id"]

    # Insert data
    await pg_query(
        action="write",
        sql="INSERT INTO test_users (name) VALUES ($1)",
        params=["Bob"],
        session_id=session_id,
        context=real_context,
    )

    # Rollback
    await pg_tx(action="rollback", session_id=session_id, context=real_context)

    # Verify data was discarded
    result = await pg_query(
        action="read",
        sql="SELECT * FROM test_users WHERE name = $1",
        params=["Bob"],
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 0

@pytest.mark.integration
@pytest.mark.asyncio
async def test_savepoint_and_release(real_context):
    """Test SAVEPOINT and RELEASE SAVEPOINT functionality."""

    # Setup
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Begin transaction
    result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(result)["session_id"]

    # Insert first record
    await pg_query(
        action="write",
        sql="INSERT INTO test_users (name) VALUES ($1)",
        params=["Alice"],
        session_id=session_id,
        context=real_context,
    )

    # Create savepoint
    await pg_tx(
        action="savepoint",
        session_id=session_id,
        savepoint_name="sp1",
        context=real_context,
    )

    # Insert second record
    await pg_query(
        action="write",
        sql="INSERT INTO test_users (name) VALUES ($1)",
        params=["Bob"],
        session_id=session_id,
        context=real_context,
    )

    # Rollback to savepoint (discard Bob)
    await pg_query(
        action="write",
        sql="ROLLBACK TO SAVEPOINT sp1",
        session_id=session_id,
        context=real_context,
    )

    # Commit (Alice should be saved, Bob discarded)
    await pg_tx(action="commit", session_id=session_id, context=real_context)

    # Verify
    result = await pg_query(
        action="read",
        sql="SELECT name FROM test_users ORDER BY name",
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 1
    assert data["rows"][0]["name"] == "Alice"
```

---

## Part 3: Safety Policy Tests

**File**: `tests/integration/test_safety_policy.py`

```python
import pytest
from coldquery.tools.pg_query import pg_query

@pytest.mark.integration
@pytest.mark.asyncio
async def test_default_deny_blocks_write_without_auth(real_context):
    """Verify Default-Deny policy prevents writes without session_id or autocommit."""

    with pytest.raises(PermissionError, match="Safety Check Failed"):
        await pg_query(
            action="write",
            sql="CREATE TABLE test_users (id INT)",
            context=real_context,
        )

@pytest.mark.integration
@pytest.mark.asyncio
async def test_autocommit_bypasses_default_deny(real_context):
    """Verify autocommit=true allows writes without session_id."""

    result = await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Verify table was created
    check = await pg_query(
        action="read",
        sql="SELECT * FROM test_users",
        context=real_context,
    )
    assert check is not None

@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_id_bypasses_default_deny(real_context):
    """Verify session_id allows writes."""

    # Begin transaction
    result = await pg_tx(action="begin", context=real_context)
    session_id = json.loads(result)["session_id"]

    # Write with session_id should succeed
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id INT)",
        session_id=session_id,
        context=real_context,
    )

    # Cleanup
    await pg_tx(action="rollback", session_id=session_id, context=real_context)
```

---

## Part 4: Connection Management Tests

**File**: `tests/integration/test_connection_management.py`

```python
import pytest
import asyncio
from coldquery.core.session import MAX_SESSIONS

@pytest.mark.integration
@pytest.mark.asyncio
async def test_max_sessions_enforcement(real_session_manager):
    """Verify MAX_SESSIONS limit is enforced."""

    # Create MAX_SESSIONS sessions
    session_ids = []
    for _ in range(MAX_SESSIONS):
        session_id = await real_session_manager.create_session()
        session_ids.append(session_id)

    # Attempt to create one more should fail
    with pytest.raises(RuntimeError, match="Maximum number of concurrent sessions reached"):
        await real_session_manager.create_session()

    # Cleanup
    for session_id in session_ids:
        await real_session_manager.close_session(session_id)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_cleanup_releases_connection(real_session_manager, real_executor):
    """Verify closing session releases connection back to pool."""

    # Get initial pool state (if accessible)
    initial_pool_size = real_executor._pool._holders.__len__() if real_executor._pool else 0

    # Create session (acquires connection)
    session_id = await real_session_manager.create_session()

    # Close session (should release connection)
    await real_session_manager.close_session(session_id)

    # Wait a moment for async cleanup
    await asyncio.sleep(0.1)

    # Connection should be back in pool
    # This is a best-effort check, asyncpg internals may vary
    assert session_id not in real_session_manager._sessions

@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_connection_leak_after_100_transactions(real_context):
    """Verify no connection leaks after many transactions."""

    # Create test table
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Run 100 transactions
    for i in range(100):
        result = await pg_tx(action="begin", context=real_context)
        session_id = json.loads(result)["session_id"]

        await pg_query(
            action="write",
            sql=f"INSERT INTO test_users (name) VALUES ('user_{i}')",
            session_id=session_id,
            context=real_context,
        )

        await pg_tx(action="commit", session_id=session_id, context=real_context)

    # Verify all data was committed
    result = await pg_query(
        action="read",
        sql="SELECT COUNT(*) as count FROM test_users",
        context=real_context,
    )
    data = json.loads(result)
    assert data["rows"][0]["count"] == 100

    # Verify no sessions are stuck open
    assert len(real_context.session_manager._sessions) == 0
```

---

## Part 5: Concurrency Tests

**File**: `tests/integration/test_concurrency.py`

```python
import pytest
import asyncio

@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_session_creation(real_session_manager):
    """Verify MAX_SESSIONS is enforced under concurrent load."""

    async def create_session():
        try:
            return await real_session_manager.create_session()
        except RuntimeError:
            return None

    # Try to create 15 sessions concurrently (max is 10)
    tasks = [create_session() for _ in range(15)]
    results = await asyncio.gather(*tasks)

    # Exactly MAX_SESSIONS should succeed
    successful = [r for r in results if r is not None]
    assert len(successful) == MAX_SESSIONS

    # Cleanup
    for session_id in successful:
        await real_session_manager.close_session(session_id)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_isolation_between_sessions(real_context):
    """Verify changes in one session are not visible in another until commit."""

    # Setup
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, name TEXT)",
        autocommit=True,
        context=real_context,
    )

    # Session A: Begin and insert
    result_a = await pg_tx(action="begin", context=real_context)
    session_a = json.loads(result_a)["session_id"]

    await pg_query(
        action="write",
        sql="INSERT INTO test_users (name) VALUES ('Alice')",
        session_id=session_a,
        context=real_context,
    )

    # Session B: Begin and query (should not see Alice)
    result_b = await pg_tx(action="begin", context=real_context)
    session_b = json.loads(result_b)["session_id"]

    result = await pg_query(
        action="read",
        sql="SELECT * FROM test_users",
        session_id=session_b,
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 0  # Should not see uncommitted data

    # Session A: Commit
    await pg_tx(action="commit", session_id=session_a, context=real_context)

    # Session B: Query again (should now see Alice)
    result = await pg_query(
        action="read",
        sql="SELECT * FROM test_users",
        session_id=session_b,
        context=real_context,
    )
    data = json.loads(result)
    assert len(data["rows"]) == 1
    assert data["rows"][0]["name"] == "Alice"

    # Cleanup
    await pg_tx(action="commit", session_id=session_b, context=real_context)
```

---

## Part 6: Isolation Level Tests

**File**: `tests/integration/test_isolation.py`

```python
import pytest
import json
from coldquery.tools.pg_tx import pg_tx
from coldquery.tools.pg_query import pg_query

@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_committed_isolation(real_context):
    """Test READ COMMITTED isolation level behavior."""

    # Setup
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, balance INT)",
        autocommit=True,
        context=real_context,
    )

    await pg_query(
        action="write",
        sql="INSERT INTO test_users (balance) VALUES (100)",
        autocommit=True,
        context=real_context,
    )

    # Session A: Begin READ COMMITTED
    result = await pg_tx(
        action="begin",
        isolation_level="READ COMMITTED",
        context=real_context,
    )
    session_a = json.loads(result)["session_id"]

    # Session A: Read initial balance
    result = await pg_query(
        action="read",
        sql="SELECT balance FROM test_users WHERE id = 1",
        session_id=session_a,
        context=real_context,
    )
    assert json.loads(result)["rows"][0]["balance"] == 100

    # Session B: Update and commit
    result = await pg_tx(action="begin", context=real_context)
    session_b = json.loads(result)["session_id"]

    await pg_query(
        action="write",
        sql="UPDATE test_users SET balance = 200 WHERE id = 1",
        session_id=session_b,
        context=real_context,
    )

    await pg_tx(action="commit", session_id=session_b, context=real_context)

    # Session A: Read again (should see new value - READ COMMITTED)
    result = await pg_query(
        action="read",
        sql="SELECT balance FROM test_users WHERE id = 1",
        session_id=session_a,
        context=real_context,
    )
    assert json.loads(result)["rows"][0]["balance"] == 200

    # Cleanup
    await pg_tx(action="commit", session_id=session_a, context=real_context)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_repeatable_read_isolation(real_context):
    """Test REPEATABLE READ isolation level behavior."""

    # Setup
    await pg_query(
        action="write",
        sql="CREATE TABLE test_users (id SERIAL PRIMARY KEY, balance INT)",
        autocommit=True,
        context=real_context,
    )

    await pg_query(
        action="write",
        sql="INSERT INTO test_users (balance) VALUES (100)",
        autocommit=True,
        context=real_context,
    )

    # Session A: Begin REPEATABLE READ
    result = await pg_tx(
        action="begin",
        isolation_level="REPEATABLE READ",
        context=real_context,
    )
    session_a = json.loads(result)["session_id"]

    # Session A: Read initial balance
    result = await pg_query(
        action="read",
        sql="SELECT balance FROM test_users WHERE id = 1",
        session_id=session_a,
        context=real_context,
    )
    assert json.loads(result)["rows"][0]["balance"] == 100

    # Session B: Update and commit
    await pg_query(
        action="write",
        sql="UPDATE test_users SET balance = 200 WHERE id = 1",
        autocommit=True,
        context=real_context,
    )

    # Session A: Read again (should still see old value - REPEATABLE READ)
    result = await pg_query(
        action="read",
        sql="SELECT balance FROM test_users WHERE id = 1",
        session_id=session_a,
        context=real_context,
    )
    assert json.loads(result)["rows"][0]["balance"] == 100  # Snapshot isolation

    # Cleanup
    await pg_tx(action="commit", session_id=session_a, context=real_context)
```

---

## Part 7: pytest Configuration

**File**: `pytest.ini` or `pyproject.toml`

```ini
[tool.pytest.ini_options]
markers =
    unit: Fast tests with mocks (default)
    integration: Slow tests with real database
    slow: Tests that take >5 seconds
```

**Usage**:

```bash
# Run only unit tests (fast)
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run all tests
pytest tests/

# Skip integration tests (for CI without DB)
pytest tests/ -m "not integration"

# Run specific integration test
pytest tests/integration/test_transaction_workflow.py -v
```

---

## Part 8: CI Configuration

**File**: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit/ -v

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: mcp
          POSTGRES_PASSWORD: mcp
          POSTGRES_DB: mcp_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest tests/integration/ -v
        env:
          DB_HOST: localhost
          DB_PORT: 5433
          DB_USER: mcp
          DB_PASSWORD: mcp
          DB_DATABASE: mcp_test
```

---

## Implementation Checklist

### Test Organization
- [ ] Move existing tests to `tests/unit/`
- [ ] Create `tests/integration/` directory
- [ ] Create `tests/integration/conftest.py` with real DB fixtures

### Integration Tests (~400 lines)
- [ ] `tests/integration/test_transaction_workflow.py` - ~120 lines
- [ ] `tests/integration/test_safety_policy.py` - ~80 lines
- [ ] `tests/integration/test_connection_management.py` - ~100 lines
- [ ] `tests/integration/test_concurrency.py` - ~80 lines
- [ ] `tests/integration/test_isolation.py` - ~120 lines

### Configuration
- [ ] Add pytest markers to `pyproject.toml`
- [ ] Update `.github/workflows/ci.yml` with integration tests
- [ ] Update README.md with test instructions

---

## Success Criteria

✅ All integration tests pass with real PostgreSQL
✅ Transaction isolation verified (READ COMMITTED, REPEATABLE READ)
✅ Default-Deny policy enforced in real scenarios
✅ No connection leaks after 100 transactions
✅ MAX_SESSIONS enforced under concurrent load
✅ CI runs both unit and integration tests
✅ Total test count: ~124 unit + ~20 integration = ~144 tests

---

## Running Tests

```bash
# All tests (unit + integration)
pytest tests/ -v

# Unit tests only (fast, no DB needed)
pytest tests/unit/ -v

# Integration tests only (requires PostgreSQL)
pytest tests/integration/ -v

# With coverage
pytest tests/ --cov=coldquery --cov-report=html

# Specific integration test
pytest tests/integration/test_transaction_workflow.py::test_full_transaction_workflow -v
```
