from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import asyncpg


@dataclass
class QueryResult:
    rows: List[Dict[str, Any]]
    row_count: Optional[int]
    fields: Optional[List[Dict[str, Any]]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows": self.rows,
            "row_count": self.row_count,
            "fields": self.fields,
        }


class QueryExecutor(Protocol):
    async def execute(
        self, sql: str, params: Optional[List[Any]] = None, timeout_ms: Optional[int] = None
    ) -> QueryResult: ...

    async def disconnect(self, destroy: bool = False) -> None: ...

    async def create_session(self) -> "QueryExecutor": ...


class AsyncpgSessionExecutor:
    def __init__(self, connection: asyncpg.Connection, pool: Optional[asyncpg.Pool] = None):
        self._connection = connection
        self._pool = pool

    async def execute(
        self, sql: str, params: Optional[List[Any]] = None, timeout_ms: Optional[int] = None
    ) -> QueryResult:
        if timeout_ms:
            await self._connection.execute(f"SET statement_timeout = {int(timeout_ms)}")

        try:
            # Check if the query is a SELECT statement
            if sql.strip().upper().startswith("SELECT"):
                results = await self._connection.fetch(sql, *(params or []))
                row_count = len(results)
                fields = (
                    [{"name": attr.name, "type": attr.type.__name__} for attr in results.columns]
                    if hasattr(results, "columns")
                    else []
                )
                return QueryResult(
                    rows=[dict(row) for row in results],
                    row_count=len(results),
                    fields=fields,
                )
            else:
                # For DML statements, use execute
                status_message = await self._connection.execute(sql, *(params or []))
                row_count_str = status_message.split()[-1] if status_message else "0"
                row_count = int(row_count_str) if row_count_str.isdigit() else 0
                return QueryResult(
                    rows=[],
                    row_count=row_count,
                    fields=[],
                )
        finally:
            if timeout_ms:
                await self._connection.execute("SET statement_timeout = 0")

    async def disconnect(self, destroy: bool = False) -> None:
        try:
            if self._pool:
                await self._pool.release(self._connection)
            else:
                await self._connection.close()
        except Exception:
            pass  # Connection may already be released or closed

    async def create_session(self) -> "QueryExecutor":
        return self


class AsyncpgPoolExecutor:
    _pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=os.environ.get("DB_HOST", "localhost"),
                port=int(os.environ.get("DB_PORT", 5433)),
                user=os.environ.get("DB_USER", "mcp"),
                password=os.environ.get("DB_PASSWORD", "mcp"),
                database=os.environ.get("DB_DATABASE", "mcp_test"),
            )
        return self._pool

    async def execute(
        self, sql: str, params: Optional[List[Any]] = None, timeout_ms: Optional[int] = None
    ) -> QueryResult:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            return await AsyncpgSessionExecutor(connection).execute(sql, params, timeout_ms)

    async def disconnect(self, destroy: bool = False) -> None:
        if self._pool:
            if destroy:
                self._pool.terminate()
            else:
                await self._pool.close()
            self._pool = None

    async def create_session(self) -> "QueryExecutor":
        pool = await self._get_pool()
        connection = await pool.acquire()
        return AsyncpgSessionExecutor(connection, pool)


# Singleton instance
db_executor = AsyncpgPoolExecutor()
