from sqlalchemy.orm import Session

from security.JWT_token import jwt_create_console
from database.models.server_model import Server
from fastapi import HTTPException


from platforms.platform_gateway import PlatformGateway

class NodeService:

    @staticmethod
    def _get_user_server(server_id: int, user_id: str, db: Session) -> Server:
        server = db.query(Server).filter(
            Server.id == server_id,
            Server.user_id == user_id
        ).first()

        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        return server
    
    @staticmethod
    def _get_node_api(server: Server, user_id: str, platform_gw: PlatformGateway):
        try:
            session_id = platform_gw.sessions.get_id(
                user_id=user_id,
                platform=server.platform.name,
                host=server.host
            )
            return platform_gw.get_node_api(session_id)

        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @staticmethod
    def get_nodes(
        server_id: int,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session,
    ):
        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        return node_api.get_nodes()

    @staticmethod
    def get_node_summary(
        server_id: int,
        node_id: str,
        fields: list,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        
        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        return node_api.get_node_status(node_id, fields)
    
    @staticmethod
    def get_node_metrics(
        server_id: int,
        node_id: str,
        opt_params: dict,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        allowed_intervals = {"hour", "day", "week", "month", "year"}
        interval = opt_params.get("interval")

        if interval not in allowed_intervals:
            raise HTTPException(status_code=400, detail="Invalid interval")

        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        return node_api.get_node_time_metrics(
            node_id,
            interval,
            opt_params.get("cf"),
            opt_params.get("ds")
        )
    
    @staticmethod
    def get_node_storage(
        server_id: int,
        node_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        
        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        result = node_api.get_node_storage(node_id)
        return sorted(result, key=lambda storage: storage["storage"])
    
    @staticmethod
    def get_node_storage_content(
        server_id: int,
        node_id: str,
        storage_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ):
        
        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        result = node_api.get_node_storage_content(node_id, storage_id)

        return sorted(result, key=lambda storage: storage["volid"])

    @staticmethod
    def delete_node_storage_content(
        server_id: int,
        node_id: str,
        storage_id: str,
        vol_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        node_api.delete_node_storage_content(node_id, storage_id, vol_id)

        return {
            "message": "Storage content deleted successfully"
        }
    
    @staticmethod
    def upload_node_storage_file(
        server_id: int,
        node_id: str,
        storage_id: str,
        content: str,
        file,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        node_api.upload_node_storage_file(
            node_id,
            storage_id,
            content,
            file
        )
    
        return {
            "message": "Storage content uploaded successfully"
        }
    
    @staticmethod
    def get_node_networks(
        server_id: int,
        node_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:


        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        return node_api.get_node_networks(node_id)

    @staticmethod
    def get_node_logs(
        server_id: int,
        node_id: str,
        limit: int,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        
        server = NodeService._get_user_server(server_id, user_id, db)
        node_api = NodeService._get_node_api(server, user_id, platform_gw)

        return node_api.get_node_logs(node_id, limit)
    
    @staticmethod
    def create_console_token(
        server_id: int,
        node_id: str,
        user_id: str,
        platform_gw: PlatformGateway,
        db: Session
    ) -> dict:
        server = NodeService._get_user_server(server_id, user_id, db)

        try:
            platform_gw.sessions.get_id(
                user_id=user_id,
                platform=server.platform.name,
                host=server.host
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e))

        token = jwt_create_console(
            user_id=user_id,
            server_id=server_id,
            node_id=node_id,
            platform=server.platform.name,
            host=server.host,
            expires_seconds=60
        )

        return {
            "type": "ssh",
            "console_token": token,
        }