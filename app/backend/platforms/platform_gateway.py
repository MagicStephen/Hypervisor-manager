from sessions.session_manager import SessionManager, SessionContext
from platforms.platform_factory import PlatformFactory
from security.Fernet import fernet_decrypt
import time


class PlatformGateway:
    SESSION_TTL_SECONDS = 7200

    def __init__(self, session_manager: SessionManager):
        self.sessions = session_manager
        self.factory = PlatformFactory()

    # ---------- USER CONNECT ----------
    def connect(
        self,
        user_id: str,
        platform: str,
        host: str,
        port: int | None,
        username: str,
        password: str | None,
    ) -> str:
        
        conn = self._connect_platform(
            platform=platform,
            host=host,
            port=port,
            username=username,
            password=password,
        )

        ctx = SessionContext(
            user_id=user_id,
            platform=platform,
            host=host,
            connection=conn,
            expires_at=time.time() + self.SESSION_TTL_SECONDS,
        )

        return self.sessions.create(ctx)

    # ---------- AUTOMATION CONNECT ----------
    def connect_automation(self, server) -> str:
        auth = server.auth

        if not auth:
            raise ValueError("Automation auth not configured")

        password = (
            fernet_decrypt(auth.password_encrypted)
            if auth.password_encrypted
            else None
        )

        conn = self._connect_platform(
            platform=server.platform.name,
            host=server.host,
            port=server.port,
            username=auth.username,
            password=password,
        )

        automation_user_id = f"automation_server_{server.id}"

        ctx = SessionContext(
            user_id=automation_user_id,
            platform=server.platform.name,
            host=server.host,
            connection=conn,
            expires_at=time.time() + self.SESSION_TTL_SECONDS,
        )

        return self.sessions.create(ctx)

    # ---------- INTERNAL CONNECT ----------
    def _connect_platform(
        self,
        platform: str,
        host: str,
        port: int | None,
        username: str,
        password: str | None = None,
    ):
        conn = self.factory.create_connection(
            platform=platform,
            host=host,
            port=port,
        )

        conn.session_connect(username=username, password=password)
        
        return conn

    # ---------- API ACCESS (SESSION) ----------
    def get_cluster_api(self, session_id: str):
        ctx = self.sessions.get_ctx(session_id)
        return self.factory.create_cluster_api(ctx.platform, ctx.connection)

    def get_node_api(self, session_id: str):
        ctx = self.sessions.get_ctx(session_id)
        return self.factory.create_node_api(ctx.platform, ctx.connection)

    def get_vm_api(self, session_id: str):
        ctx = self.sessions.get_ctx(session_id)
        return self.factory.create_vm_api(ctx.platform, ctx.connection)