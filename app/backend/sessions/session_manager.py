import uuid
import time
from dataclasses import dataclass
import threading
from fastapi import HTTPException

@dataclass
class SessionContext:
    user_id: str
    platform: str
    host: str
    connection: object
    expires_at: float


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, SessionContext] = {}
        self._lock = threading.RLock()

    def get_all_active(self) -> list[SessionContext]:
        with self._lock:
            now = time.time()
            return [
                ctx for ctx in self._sessions.values()
                if ctx.expires_at >= now
            ]

    def create(self, ctx: SessionContext) -> str:
        with self._lock:
            session_id = str(uuid.uuid4())
            self._sessions[session_id] = ctx
            return session_id

    def get_id(self, user_id: str, platform: str, host: str) -> str:
        with self._lock:
            now = time.time()

            for key, ctx in self._sessions.items():
                if (
                    ctx.user_id == user_id
                    and ctx.platform == platform
                    and ctx.host == host
                ):
                    if ctx.expires_at >= now:
                        return key

            raise HTTPException(status_code=404, detail="Session not found for this user")

    def get_ctx(self, session_id: str) -> SessionContext:
        with self._lock:
            ctx = self._sessions.get(session_id)

            if not ctx:
                raise HTTPException(status_code=404, detail="Invalid session id")

            if ctx.expires_at < time.time():
                del self._sessions[session_id]
                raise HTTPException(status_code=410, detail="Session expired")

            return ctx

    def delete(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup(self):
        with self._lock:
            now = time.time()

            for sid, ctx in list(self._sessions.items()):
                if ctx.expires_at < now:
                    del self._sessions[sid]