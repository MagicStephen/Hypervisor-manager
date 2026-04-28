"""Modul obsahující servisní logiku pro správu virtuálních strojů.

Tento modul poskytuje operace pro práci s virtuálními stroji uživatele,
včetně jejich vytváření, mazání, změny stavu, práce se snapshoty,
konfigurací, zálohami, logy a konzolovým připojením.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import BACKUP_ROOT
from database.models.server_model import Server
from platforms.platform_gateway import PlatformGateway


class VmService:
    """Servisní třída pro správu virtuálních strojů.
    
    Třída zajišťuje přístup k API virtuálních strojů prostřednictvím platform gateway. 
    Umožňuje na serveru konkrétního uživatele spouštět operace nad virtuálními stroji a zároveň zpracovává chyby vzniklé při komunikaci.
    """

    @staticmethod
    def _get_user_server(server_id: int, user_id: str, db: Session) -> Server:
        """Vrátí server patřící zadanému uživateli.

        Metoda vyhledá server podle jeho identifikátoru a současně ověří,
        že server náleží danému uživateli.

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            db: Aktivní databázová session.

        Returns:
            Server: Nalezený server uživatele.

        Raises:
            HTTPException: Pokud server neexistuje nebo nepatří uživateli.
        """

        server = db.query(Server).filter(
            Server.id == server_id,
            Server.user_id == user_id
        ).first()

        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        return server

    @staticmethod
    def _get_vm_api(server: Server, user_id: str, platform_gw: PlatformGateway):
        """Vrátí instanci API pro práci s virtuálními stroji.

        Metoda získá session ID pro daného uživatele a server a následně
        vrátí VM API objekt použitelný pro další operace.

        Args:
            server: Server objekt, ke kterému se má API navázat.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.

        Returns:
            object: Object VmAPI konkrétní platformy pro práci s virtuálními stroji.

        Raises:
            HTTPException: Pokud dojde k chybě komunikace s platformou nebo při získávání session/API objektu.
        """
        try:
            session_id = platform_gw.sessions.get_id(
                user_id=user_id,
                platform=server.platform.name,
                host=server.host
            )

            return platform_gw.get_vm_api(session_id)

        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_vms(
        server_id: int,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí seznam virtuálních strojů na daném serveru.

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Kolekce virtuálních strojů na daném serveru.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)
        return vm_api.get_vms()

    @staticmethod
    def create_vm(
        server_id: int,
        node_id: str,
        user_id: str,
        opt_parameters: dict,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vytvoří nový virtuální stroj.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu, na kterém má být VM vytvořen.
            user_id: Identifikátor uživatele.
            opt_parameters: Volitelné parametry pro vytvoření VM.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Výsledek operace vrácený platform API.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.create_vm(node_id, opt_parameters)

    @staticmethod
    def destroy_vm(
        server_id: int,
        node_id: str,
        user_id: str,
        vm_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Odstraní virtuální stroj.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            user_id: Identifikátor uživatele.
            vm_id: Identifikátor virtuálního stroje.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        vm_api.destroy_vm(node_id, vm_id)

    @staticmethod
    def get_vm_status(
        server_id: int,
        node_id: str,
        vm_id: str,
        user_id: str,
        params: list,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí stav virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            user_id: Identifikátor uživatele.
            params: Seznam požadovaných stavových parametrů.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Stavové informace virtuálního stroje.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.get_vm_status(node_id, vm_id, params)

        
    @staticmethod
    def get_vm_capabilities(server_id, node_id, vm_id, user_id, platform_gw, db):

        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.get_vm_capabilities()
    
    @staticmethod
    def get_vm_time_metrics(
        server_id: int,
        node_id: str,
        vm_id: str,
        user_id: str,
        params: dict,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí časové metriky virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            user_id: Identifikátor uživatele.
            params: Parametry určující požadované metriky.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Časové metriky virtuálního stroje.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.get_vm_time_metrics(node_id, vm_id, params)

    @staticmethod
    def set_vm_status(
        server_id: int,
        node_id: str,
        vm_id: str,
        status: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        """Změní stav virtuálního stroje.

        Podporované stavy jsou: `start`, `stop`, `shutdown`, `suspend`,
        `reset`, `reboot`, `resume`.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            status: Požadovaný nový stav VM.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            dict: Potvrzení o změně stavu VM.

        Raises:
            HTTPException: Pokud je požadovaný stav nepodporovaný.
        """
        allowed_statuses = {
            "start", "stop", "shutdown", "suspend", "reset", "reboot", "resume"
        }

        if status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported VM status '{status}'"
            )

        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        vm_api.set_vm_status(node_id, vm_id, status)

        return {
            "message": f"VM changed state to {status}"
        }

    @staticmethod
    def get_vm_snapshots(
        server_id: int,
        node_id: str,
        vm_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí seznam snapshotů virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Seznam snapshotů virtuálního stroje.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)
        return vm_api.manage_vm_snapshots(node_id, vm_id)

    @staticmethod
    def create_vm_snapshot(
        server_id: int,
        node_id: str,
        vm_id: str,
        snap_data: dict,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vytvoří snapshot virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            snap_data: Data potřebná pro vytvoření snapshotu.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)
        vm_api.manage_vm_snapshots(node_id, vm_id, snap_data)

    @staticmethod
    def drop_vm_snapshot(
        server_id: int,
        node_id: str,
        vm_id: str,
        snapshotid: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        """Odstraní snapshot virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            snapshotid: Identifikátor snapshotu.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)
        vm_api.drop_vm_snapshot(node_id, vm_id, snapshotid)

    @staticmethod
    def rollback_vm_snapshot(
        server_id: int,
        node_id: str,
        vm_id: str,
        snapshotid: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        """Provede rollback virtuálního stroje do zvoleného snapshotu.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            snapshotid: Identifikátor snapshotu.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.
            
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)
        vm_api.rollback_vm_snapshot(node_id, vm_id, snapshotid)

    @staticmethod
    def get_vm_templates(
        server_id: int,
        node_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí dostupné šablony virtuálních strojů pro daný uzel.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Dostupné VM šablony.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.get_vm_templates(node_id)

    @staticmethod
    def get_vm_config(
        server_id: int,
        node_id: str,
        vm_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí konfiguraci virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Konfigurační data virtuálního stroje.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.get_vm_config(node_id, vm_id)

    @staticmethod
    def set_vm_config(
        server_id: int,
        node_id: str,
        vm_id: str,
        optional_params: dict,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Upraví konfiguraci virtuálního stroje.

        Pokud změna konfigurace vyžaduje restart nebo vypnutí běžícího VM,
        metoda provede potřebnou akci automaticky podle odpovědi platform API.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            optional_params: Parametry konfigurace, které mají být změněny.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Výsledek operace vrácený platform API.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        result = vm_api.set_vm_config(
            node_id,
            vm_id,
            optional_params
        )

        required_action = result.get("required_action")
        was_running = result.get("was_running")

        if required_action == "shutdown" and was_running:
            vm_api.set_vm_status(node_id, vm_id, "shutdown")
            vm_api.set_vm_status(node_id, vm_id, "start")

        return result

    @staticmethod
    def get_vm_backups(
        server_id: int,
        node_id: str,
        vm_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí seznam záloh virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Seznam dostupných záloh virtuálního stroje.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.get_vm_backups(
            node_id,
            vm_id,
        )

    @staticmethod
    def create_vm_backup(
        server_id: int,
        node_id: str,
        vm_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vytvoří zálohu virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Výsledek operace vytvoření zálohy.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.create_vm_backup(
            node_id,
            vm_id,
            BACKUP_ROOT
        )

    @staticmethod
    def get_vm_logs(
        server_id: int,
        node_id: str,
        vm_id: str,
        limit: int,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        """Vrátí logy virtuálního stroje.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            limit: Maximální počet vrácených log záznamů.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            object: Logy virtuálního stroje.
        """
        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        return vm_api.get_vm_logs(node_id, vm_id, limit)

    @staticmethod
    def get_console_conn(
        server_id: int,
        node_id: str,
        vm_id: str,
        user_id: str,
        protocol: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        """Vrátí parametry pro konzolové připojení k virtuálnímu stroji.

        Podporované protokoly jsou `vnc` a `spice`.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            user_id: Identifikátor uživatele.
            protocol: Požadovaný konzolový protokol.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            dict: Slovník obsahující parametry pro připojení ke konzoli.

        Raises:
            HTTPException: Pokud je požadovaný protokol nepodporovaný.
        """
        if protocol not in {"vnc", "spice"}:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported console protocol: {protocol}"
            )

        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        result = vm_api.open_console(
            node_id,
            vm_id,
            protocol
        )

        return {
            "protocol": result.get("protocol", protocol),
            "host": result.get("host"),
            "port": result.get("port"),
            "ticket": result.get("ticket"),
            "ws_url": result.get("ws_url"),
        }

    @staticmethod
    def open_vm_console(
        server_id: int,
        node_id: str,
        vm_id: str,
        protocol: str,
        user_id: str,
        platform_gw: PlatformGateway,
        request,
        db: Session
    ) -> dict:
        """Otevře konzolové připojení k virtuálnímu stroji.

        Metoda připraví připojovací údaje pro webovou konzoli virtuálního stroje.
        Pro protokol `vnc` navíc sestaví websocket URL podle aktuálního requestu.

        Args:
            server_id: Identifikátor serveru.
            node_id: Identifikátor uzlu.
            vm_id: Identifikátor virtuálního stroje.
            protocol: Požadovaný konzolový protokol (`vnc` nebo `webmks`).
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            request: Aktuální HTTP request objekt.
            db: Aktivní databázová session.

        Returns:
            dict: Slovník s informacemi potřebnými pro otevření konzole.

        Raises:
            HTTPException: Pokud je požadovaný protokol nepodporovaný.
        """
        if protocol not in {"vnc", "webmks"}:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported console protocol: {protocol}"
            )

        server = VmService._get_user_server(server_id, user_id, db)
        vm_api = VmService._get_vm_api(server, user_id, platform_gw)

        console_info = vm_api.open_console(
            node_id,
            vm_id,
            protocol,
        )

        if protocol == "vnc":
            ws_scheme = "wss" if request.url.scheme == "https" else "ws"
            host = request.headers.get("host")
            ws_url = (
                f"{ws_scheme}://{host}/servers/{server_id}/vms/{vm_id}/console/vnc"
                f"?nodeid={node_id}"
            )

            return {
                "protocol": "vnc",
                "ws_url": ws_url,
                "password": console_info["ticket"]
            }

        return {
            "protocol": "webmks",
            "ws_url": console_info["ws_url"],
            "ticket": console_info["ticket"]
        }