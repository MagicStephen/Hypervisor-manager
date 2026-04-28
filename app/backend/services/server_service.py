"""Modul obsahující servisní logiku pro správu serverů.

Tento modul zajišťuje připojení nového serveru k uživateli, opětovné
navázání spojení s existujícím serverem a načítání seznamu serverů
uživatele včetně informace o jejich dostupnosti a topologii clusteru.
"""

from database.models.node_model import Node
from database.models.platform_model import Platform
from database.models.server_node_model import ServerNode
from database.models.server_model import Server
from sqlalchemy import or_
from fastapi import HTTPException
from platforms.platform_gateway import PlatformGateway
from sqlalchemy.orm import Session


class ServerService:
    """Servisní třída pro správu serverů uživatele.

    Třída poskytuje metody pro:

    - připojení nového serveru,
    - obnovení spojení s existujícím serverem,
    - načtení serverů patřících uživateli.
    """

    @staticmethod
    def connect(
        server_name: str,
        platform: str,
        host: str,
        port: int,
        username: str,
        password: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session,
    ) -> dict:
        """Připojí nový server k uživatelskému účtu.

        Metoda nejprve ověří existenci platformy a zkontroluje, zda uživatel
        již nemá server se stejným názvem nebo hostem. Následně se pokusí
        navázat spojení přes platform gateway, načíst topologii clusteru
        a uložit server i jeho uzly do databáze.

        Args:
            server_name: Uživatelský název serveru.
            platform: Název platformy, ke které se server vztahuje.
            host: Adresa serveru.
            port: Port serveru.
            username: Přihlašovací jméno.
            password: Heslo k serveru.
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            resources: Topologie clusteru a zdroje vrácené platform API.

        Raises:
            HTTPException: Pokud platforma neexistuje.
            HTTPException: Pokud server se stejným názvem nebo hostem již existuje.
            HTTPException: Pokud uživatel už má jiný server napojený na stejný uzel.
            HTTPException: Pokud dojde k chybě při komunikaci s platformou.
        """
        platform_exists = db.query(Platform).filter(Platform.name == platform).first()

        if not platform_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Platform '{platform}' not found."
            )

        server_exists = db.query(Server).filter(
            Server.user_id == user_id,
            or_(
                Server.name == server_name,
                Server.host == host
            )
        ).first()

        if server_exists:
            raise HTTPException(
                status_code=409,
                detail=f"Server '{server_name}' at '{host}' already exists."
            )

        try:
            platform_gw.connect(
                user_id=user_id,
                platform=platform,
                host=host,
                port=port,
                username=username,
                password=password
            )

            session_id = platform_gw.sessions.get_id(
                user_id=user_id,
                platform=platform,
                host=host
            )
            resources = platform_gw.get_cluster_api(session_id).get_cluster_topology()

        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))

        for cluster in resources.get("clusters", []):
            for node in cluster.get("nodes", []):
                node_host = node.get("host")

                node_exists = db.query(Node).filter(
                    Node.host == node_host
                ).first()

                if not node_exists:
                    continue

                existing_server = db.query(Server).join(ServerNode).filter(
                    ServerNode.node_id == node_exists.id,
                    Server.user_id == user_id
                ).first()

                if existing_server:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"You already have server '{existing_server.name}' "
                            f"for node with address '{node_exists.host}'"
                        )
                    )

        try:
            new_server = Server(
                name=server_name,
                host=host,
                port=port,
                username=username,
                user_id=user_id,
                platform_id=platform_exists.id
            )
            db.add(new_server)
            db.flush()

            for cluster in resources.get("clusters", []):
                cluster_name = cluster.get("cluster", "")

                for node in cluster.get("nodes", []):
                    node_host = node.get("host")

                    db_node = db.query(Node).filter(
                        Node.host == node_host
                    ).first()

                    if not db_node:
                        db_node = Node(
                            name=node.get("name"),
                            host=node_host,
                            cluster=cluster_name
                        )
                        db.add(db_node)
                        db.flush()

                    link = ServerNode(
                        server_id=new_server.id,
                        node_id=db_node.id
                    )
                    db.add(link)

            db.commit()

        except Exception:
            db.rollback()
            raise

        return resources

    @staticmethod
    def reconnect(
        server_id: int,
        user_id: str,
        password: str,
        platform_gw: PlatformGateway,
        db: Session,
    ) -> dict:
        """Obnoví spojení s existujícím serverem.

        Metoda načte server uživatele, zkusí se k němu znovu připojit
        s novým heslem, aktualizuje topologii clusteru a doplní do databáze
        případné nové uzly a vazby mezi serverem a uzly.

        Args:
            server_id: Identifikátor serveru.
            user_id: Identifikátor uživatele.
            password: Heslo použité pro nové připojení.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            resources: Topologie clusteru a zdroje vrácené platform API.

        Raises:
            HTTPException: Pokud server uživateli nepatří nebo neexistuje.
            HTTPException: Pokud dojde k chybě při komunikaci s platformou.
        """
        server = db.query(Server).filter(
            Server.id == server_id,
            Server.user_id == user_id
        ).first()

        if not server:
            raise HTTPException(
                status_code=404,
                detail="Server not found for this user"
            )

        try:
            platform_gw.connect(
                user_id=user_id,
                platform=server.platform.name,
                host=server.host,
                port=server.port,
                username=server.username,
                password=password
            )

            session_id = platform_gw.sessions.get_id(
                user_id=user_id,
                platform=server.platform.name,
                host=server.host
            )
            resources = platform_gw.get_cluster_api(session_id).get_cluster_topology()

        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))

        try:
            for cluster in resources.get("clusters", []):
                cluster_name = cluster.get("cluster", "")

                for node in cluster.get("nodes", []):
                    node_host = node.get("host")

                    db_node = db.query(Node).filter(
                        Node.host == node_host
                    ).first()

                    if not db_node:
                        db_node = Node(
                            name=node.get("name"),
                            host=node_host,
                            cluster=cluster_name,
                            platform_id=server.platform_id
                        )
                        db.add(db_node)
                        db.flush()

                    link_exists = db.query(ServerNode).filter(
                        ServerNode.server_id == server.id,
                        ServerNode.node_id == db_node.id
                    ).first()

                    if not link_exists:
                        db.add(
                            ServerNode(
                                server_id=server.id,
                                node_id=db_node.id
                            )
                        )

            db.commit()

        except Exception:
            db.rollback()
            raise

        return resources

    @staticmethod
    def get_user_servers(user_id: str, platform_gw: PlatformGateway, db) -> list[dict]:
        """Vrátí seznam serverů patřících uživateli.

        U každého serveru se metoda pokusí získat aktivní session a načíst
        topologii clusteru. Pokud se to nepovede, server je označen jako
        nepřipojený.

        Args:
            user_id: Identifikátor uživatele.
            platform_gw: Gateway pro komunikaci s platformou.
            db: Aktivní databázová session.

        Returns:
            resources: Seznam serverů s informacemi o připojení a topologii.
        """
        servers = db.query(Server).filter(Server.user_id == user_id).all()

        result = []

        for s in servers:
            topology = {}
            connected = False

            try:
                session_id = platform_gw.sessions.get_id(
                    user_id=user_id,
                    platform=s.platform.name,
                    host=s.host
                )

                topology = platform_gw.get_cluster_api(session_id).get_cluster_topology()
                connected = True

            except Exception:
                connected = False
                topology = {}

            result.append({
                "server_id": s.id,
                "name": s.name,
                "host": s.host,
                "platform": s.platform.name,
                "username": s.username,
                "connected": connected,
                "clusters": topology.get("clusters", [])
            })

        return result