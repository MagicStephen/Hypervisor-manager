"""Modul obsahující servisní logiku pro správu automatizace serverů.

Tento modul zajišťuje konfiguraci autentizačních údajů pro automatizaci,
vytváření, načítání a mazání automatizačních úloh a serializaci tasků
pro výstup do API odpovědí.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session
from database.models.server_automation_auth_model import ServerAutomationAuth
from database.models.server_model import Server
from database.models.automation_task_model import AutomationTask
from security.Fernet import fernet_encrypt


class AutomationService:
    """Servisní třída pro správu automatizačních úloh a autentizace serveru.

    Třída poskytuje metody pro:

    - ověření přístupu uživatele k serveru,
    - správu automatizačních přihlašovacích údajů,
    - vytváření a mazání automatizačních tasků,
    - serializaci tasků pro API výstup.
    """

    @staticmethod
    def _get_user_server(server_id: int, user_id: str, db):
        """Vrátí server patřící konkrétnímu uživateli.

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            db: Aktivní databázová session.

        Returns:
            Server: Nalezený server patřící zadanému uživateli.

        Raises:
            HTTPException: Pokud server neexistuje nebo nepatří uživateli.
        """
        server = db.query(Server).filter(
            Server.id == server_id,
            Server.user_id == user_id
        ).first()

        if not server:
            raise HTTPException(status_code=404, detail="Server not found for this user")

        return server

    @staticmethod
    def serialize_task(task: AutomationTask) -> dict:
        """Převede automatizační úlohu na serializovatelný slovník.

        Metoda slouží k převodu databázového objektu `AutomationTask`
        do formátu vhodného pro API odpověď.

        Args:
            task: Automatizační úloha.

        Returns:
            task_info: Slovník obsahující serializovaná data tasku.
        """
        return {
            "id": task.id,
            "name": task.name,
            "enabled": task.enabled,
            "server_id": task.server_id,
            "parent_id": task.parent_id,
            "order_index": task.order_index,
            "node_id": task.node_id,
            "vm_id": task.vm_id,
            "action": task.action,
            "trigger_type": task.trigger_type,
            "cron_expression": task.cron_expression,
            "interval_seconds": task.interval_seconds,
            "run_at": task.run_at.isoformat() if task.run_at else None,
            "snapshot_name": task.snapshot_name,
            "duration_seconds": task.duration_seconds,
        }

    @staticmethod
    def get_automation_tasks(server_id: int, user_id: int, db: Session) -> list[dict]:
        """Vrátí seznam automatizačních úloh pro zadaný server.

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            db: Aktivní databázová session.

        Returns:
            tasks: Seznam serializovaných automatizačních úloh.
        """
        AutomationService._get_user_server(server_id, user_id, db)

        tasks = db.query(AutomationTask).filter(
            AutomationTask.server_id == server_id
        ).all()

        return [AutomationService.serialize_task(task) for task in tasks]

    @staticmethod
    def set_automation_auth(server_id: int, user_id: int, credentials: dict, db: Session) -> dict:
        """Nastaví autentizační údaje pro automatizaci serveru.

        Podporuje dvě varianty přihlášení:
        - uživatelské jméno a heslo,
        - token ID a token secret.

        V jednom požadavku lze použít pouze jeden typ autentizace.

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            credentials: Slovník s přihlašovacími údaji.
            db: Aktivní databázová session.

        Returns:
            auth_info: Informace o uložené autentizační konfiguraci.

        Raises:
            HTTPException: Pokud nejsou zadány platné přihlašovací údaje
                nebo pokud jsou zadány oba typy autentizace současně.
        """
        server = AutomationService._get_user_server(server_id, user_id, db)

        username = credentials.get("username")
        password = credentials.get("password")
        token_id = credentials.get("token_id")
        token_secret = credentials.get("token_secret")

        has_password_auth = bool(username and password)
        has_token_auth = bool(token_id and token_secret)

        if not (has_password_auth or has_token_auth):
            raise HTTPException(
                status_code=400,
                detail="Provide either username + password or token_id + token_secret"
            )

        if has_password_auth and has_token_auth:
            raise HTTPException(
                status_code=400,
                detail="Use either password auth or token auth, not both"
            )

        auth = None
        if server.auth_id:
            auth = db.query(ServerAutomationAuth).filter(
                ServerAutomationAuth.id == server.auth_id
            ).first()

        if not auth:
            auth = ServerAutomationAuth()
            db.add(auth)
            db.flush()

        if has_password_auth:
            auth.username = username
            auth.password_encrypted = fernet_encrypt(password)
            auth.token_id = None
            auth.token_secret_encrypted = None
        else:
            auth.username = None
            auth.password_encrypted = None
            auth.token_id = token_id
            auth.token_secret_encrypted = fernet_encrypt(token_secret)

        server.auth_id = auth.id

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        return {
            "configured": True,
            "id": auth.id,
            "username": auth.username,
            "has_password": bool(auth.password_encrypted),
            "has_token": bool(auth.token_secret_encrypted),
            "token_id": auth.token_id,
        }

    @staticmethod
    def delete_automation_auth(server_id: int, auth_id: int, user_id: int, db: Session) -> dict:
        """Odstraní autentizační údaje automatizace pro zadaný server.

        Args:
            server_id: Identifikátor serveru.
            auth_id: Identifikátor autentizačního záznamu.
            user_id: Identifikátor uživatele.
            db: Aktivní databázová session.

        Returns:
            result: Informace o úspěšném smazání autentizace.

        Raises:
            HTTPException: Pokud server nemá nastavenou autentizaci
                nebo pokud autentizační záznam neexistuje.
        """
        server = AutomationService._get_user_server(server_id, user_id, db)

        if not server.auth_id:
            raise HTTPException(status_code=404, detail="No auth configured for this server")

        auth = db.query(ServerAutomationAuth).filter(
            ServerAutomationAuth.id == auth_id
        ).first()

        if not auth:
            raise HTTPException(status_code=404, detail="Auth not found")

        server.auth_id = None
        db.delete(auth)

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        return {"deleted": True}

    @staticmethod
    def get_automation_auth(server_id: int, user_id: int, db: Session) -> dict:
        """Vrátí informace o nakonfigurované autentizaci pro server.

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            db: Aktivní databázová session.

        Returns:
            state: Stav konfigurace autentizace a základní metadata.
        """
        server = AutomationService._get_user_server(server_id, user_id, db)

        if not server.auth:
            return {"configured": False}

        return {
            "configured": True,
            "id": server.auth.id,
            "username": server.auth.username,
            "has_password": bool(server.auth.password_encrypted),
            "has_token": bool(server.auth.token_secret_encrypted),
            "token_id": server.auth.token_id,
        }

    @staticmethod
    def create_automation_task(server_id: int, user_id: int, data: dict, db: Session) -> dict:
        """Vytvoří novou automatizační úlohu.

        Metoda validuje vstupní data, ověřuje vazbu na parent task
        a podle typu triggeru kontroluje požadované parametry.

        Podporované akce:
        - `start`
        - `stop`
        - `restart`
        - `snapshot`

        Podporované trigery:
        - `cron`
        - `interval`
        - `once`

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            data: Vstupní data nové automatizační úlohy.
            db: Aktivní databázová session.

        Returns:
            result: Serializovaná vytvořená automatizační úloha.

        Raises:
            HTTPException: Pokud vstupní data nejsou validní
                nebo pokud parent task neexistuje.
        """
        server = AutomationService._get_user_server(server_id, user_id, db)

        name = data.get("name")
        enabled = data.get("enabled", True)
        vm_id = data.get("vm_id")
        node_id = data.get("node_id")
        action = data.get("action")
        trigger_type = data.get("trigger_type")

        cron_expression = data.get("cron_expression")
        interval_seconds = data.get("interval_seconds")
        run_at = data.get("run_at")

        snapshot_name = data.get("snapshot_name")
        duration_seconds = data.get("duration_seconds")

        parent_id = data.get("parent_id")
        order_index = data.get("order_index", 0)

        if not name:
            raise HTTPException(status_code=400, detail="Task name is required")

        if not vm_id:
            raise HTTPException(status_code=400, detail="vm_id is required")

        if not action:
            raise HTTPException(status_code=400, detail="action is required")

        allowed_actions = {"start", "stop", "restart", "snapshot"}
        if action not in allowed_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action. Allowed values: {', '.join(sorted(allowed_actions))}"
            )

        if parent_id is not None:
            parent_task = db.query(AutomationTask).filter(
                AutomationTask.id == parent_id,
                AutomationTask.server_id == server_id
            ).first()

            if not parent_task:
                raise HTTPException(status_code=404, detail="Parent task not found")

            if trigger_type or cron_expression or interval_seconds or run_at:
                raise HTTPException(
                    status_code=400,
                    detail="Child task cannot have its own trigger"
                )

            trigger_type = None
            cron_expression = None
            interval_seconds = None
            run_at = None

        else:
            allowed_trigger_types = {"cron", "interval", "once"}

            if trigger_type not in allowed_trigger_types:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid trigger_type. Allowed values: cron, interval, once"
                )

            if trigger_type == "cron" and not cron_expression:
                raise HTTPException(
                    status_code=400,
                    detail="cron_expression is required for cron trigger"
                )

            if trigger_type == "interval" and not interval_seconds:
                raise HTTPException(
                    status_code=400,
                    detail="interval_seconds is required for interval trigger"
                )

            if trigger_type == "once" and not run_at:
                raise HTTPException(
                    status_code=400,
                    detail="run_at is required for once trigger"
                )

        if action == "snapshot" and not snapshot_name:
            snapshot_name = "snapshot"

        task = AutomationTask(
            name=name,
            enabled=enabled,
            server_id=server.id,
            parent_id=parent_id,
            order_index=order_index,
            node_id=node_id,
            vm_id=vm_id,
            action=action,
            trigger_type=trigger_type,
            cron_expression=cron_expression if trigger_type == "cron" else None,
            interval_seconds=interval_seconds if trigger_type == "interval" else None,
            run_at=run_at if trigger_type == "once" else None,
            snapshot_name=snapshot_name if action == "snapshot" else None,
            duration_seconds=duration_seconds
        )

        db.add(task)

        try:
            db.commit()
            db.refresh(task)
        except Exception:
            db.rollback()
            raise

        return AutomationService.serialize_task(task)

    @staticmethod
    def delete_automation_task(server_id: int, task_id: int, user_id: int, db: Session) -> dict:
        """Odstraní automatizační úlohu.

        Args:
            server_id: Identifikátor serveru.
            task_id: Identifikátor automatizační úlohy.
            user_id: Identifikátor uživatele.
            db: Aktivní databázová session.

        Returns:
            result: Serializovaná data smazané úlohy.

        Raises:
            HTTPException: Pokud úloha neexistuje.
        """
        AutomationService._get_user_server(server_id, user_id, db)

        task = db.query(AutomationTask).filter(
            AutomationTask.id == task_id,
            AutomationTask.server_id == server_id
        ).first()

        if not task:
            raise HTTPException(status_code=404, detail="Automation task not found")

        task_data = AutomationService.serialize_task(task)

        db.delete(task)

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        return task_data