import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List

from coldquery.core.executor import QueryExecutor, db_executor
from coldquery.core.logger import get_logger

logger = get_logger(__name__)

SESSION_TTL_MINUTES = 30
MAX_SESSIONS = 10

class SessionData:
    def __init__(self, executor: QueryExecutor):
        self.executor = executor
        self.last_accessed = datetime.now(timezone.utc)
        self.ttl_timer: Optional[asyncio.TimerHandle] = None

class SessionManager:
    def __init__(self, pool_executor: QueryExecutor):
        self._sessions: Dict[str, SessionData] = {}
        self._pool_executor = pool_executor

    async def create_session(self) -> str:
        if len(self._sessions) >= MAX_SESSIONS:
            raise RuntimeError("Maximum number of concurrent sessions reached.")

        session_id = str(uuid.uuid4())

        try:
            session_executor = await self._pool_executor.create_session()

            # Double-check after await (race condition protection)
            if len(self._sessions) >= MAX_SESSIONS:
                await session_executor.disconnect(destroy=True)
                raise RuntimeError("Maximum number of concurrent sessions reached.")

            session_data = SessionData(session_executor)
            self._sessions[session_id] = session_data
            self._reset_ttl(session_id)
            logger.info(f"Session created: {session_id}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    def get_session_executor(self, session_id: str) -> Optional[QueryExecutor]:
        session_data = self._sessions.get(session_id)
        if session_data:
            session_data.last_accessed = datetime.now(timezone.utc)
            self._reset_ttl(session_id)
            return session_data.executor
        return None

    async def close_session(self, session_id: str) -> None:
        session_data = self._sessions.pop(session_id, None)
        if session_data:
            if session_data.ttl_timer:
                session_data.ttl_timer.cancel()
            await session_data.executor.disconnect(destroy=True)
            logger.info(f"Session closed: {session_id}")

    def _reset_ttl(self, session_id: str) -> None:
        session_data = self._sessions.get(session_id)
        if not session_data:
            return

        if session_data.ttl_timer:
            session_data.ttl_timer.cancel()

        loop = asyncio.get_running_loop()
        session_data.ttl_timer = loop.call_later(
            timedelta(minutes=SESSION_TTL_MINUTES).total_seconds(),
            lambda: asyncio.create_task(self._expire_session(session_id)),
        )

    async def _expire_session(self, session_id: str) -> None:
        logger.warning(f"Session expired due to inactivity: {session_id}")
        await self.close_session(session_id)

    def list_sessions(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": session_id,
                "idle_time_seconds": (now - data.last_accessed).total_seconds(),
                "expires_in_seconds": (data.last_accessed + timedelta(minutes=SESSION_TTL_MINUTES) - now).total_seconds(),
            }
            for session_id, data in self._sessions.items()
        ]

# Singleton instance
session_manager = SessionManager(db_executor)
