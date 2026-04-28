"""Router pro správu uzlů platformy.

Tento modul obsahuje endpointy pro práci s uzly serverové platformy:

- čtení stavu uzlu,
- čtení metrik uzlu,
- práci s úložišti a jejich obsahem,
- nahrávání souborů do storage,
- čtení síťových rozhraní,
- vytvoření konzolového tokenu,
- websocket SSH konzoli k uzlu,
- čtení logů uzlu.
"""

from services.node_service import NodeService
from services.user_service import UserService
import json
import asyncio
import asyncssh

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    Cookie,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session
from database.database import get_db
from security.JWT_token import jwt_verify_console


router = APIRouter()


@router.post("/{nodeid}/status", response_model=dict)
def get_node_status(
    data: dict,
    serverid: int,
    nodeid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí stav uzlu podle požadovaných polí.

    Args:
        data: Slovník obsahující klíč ``fields`` se seznamem požadovaných stavových položek uzlu.
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Stavové informace o uzlu.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.get_node_summary(
        server_id=serverid,
        node_id=nodeid,
        fields=data["fields"],
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{nodeid}/metrics", response_model=list[dict])
def get_node_metrics(
    data: dict,
    serverid: int,
    nodeid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí časové metriky uzlu.

    Args:
        data: Parametry určující interval a další volby pro načtení metrik uzlu.
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        list[dict]: Seznam časových metrik uzlu.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.get_node_metrics(
        server_id=serverid,
        node_id=nodeid,
        opt_params=data,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{nodeid}/storage", response_model=list[dict])
def get_node_storage(
    serverid: int,
    nodeid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí seznam úložišť dostupných na uzlu.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        list[dict]: Seznam úložišť dostupných na uzlu.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.get_node_storage(
        server_id=serverid,
        node_id=nodeid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{nodeid}/storage/{storageid}/content", response_model=list[dict])
def get_node_storage_content(
    serverid: int,
    nodeid: str,
    storageid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí obsah vybraného úložiště na uzlu.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        storageid: Identifikátor úložiště.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        list[dict]: Obsah vybraného úložiště.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.get_node_storage_content(
        server_id=serverid,
        node_id=nodeid,
        storage_id=storageid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.delete("/{nodeid}/storage/{storageid}/content/{volid:path}", response_model=dict)
def delete_node_storage_content(
    serverid: int,
    nodeid: str,
    storageid: str,
    volid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Odstraní položku z obsahu úložiště.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        storageid: Identifikátor úložiště.
        volid: Identifikátor volume nebo cesty, která má být odstraněna.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Potvrzení o úspěšném odstranění položky z úložiště.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.delete_node_storage_content(
        server_id=serverid,
        node_id=nodeid,
        storage_id=storageid,
        vol_id=volid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{nodeid}/storage/{storageid}/upload", response_model=dict)
def upload_to_storage(
    serverid: int,
    nodeid: str,
    storageid: str,
    content: str = Form(...),
    file: UploadFile = File(...),
    request: Request = None,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Nahraje soubor do úložiště uzlu.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        storageid: Identifikátor cílového úložiště.
        content: Typ obsahu, do kterého má být soubor nahrán.
        file: Nahrávaný soubor.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Potvrzení o úspěšném nahrání souboru.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.upload_node_storage_file(
        server_id=serverid,
        node_id=nodeid,
        storage_id=storageid,
        content=content,
        file=file,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.get("/{nodeid}/networks", response_model=list[dict])
def node_networks(
    serverid: int,
    nodeid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí síťová rozhraní nebo sítě dostupné na uzlu.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        list[dict]: Seznam síťových rozhraní nebo sítí uzlu.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.get_node_networks(
        server_id=serverid,
        node_id=nodeid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{nodeid}/console/token", response_model=dict)
def create_node_console_session(
    serverid: int,
    nodeid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vytvoří krátkodobý konzolový token pro přístup k uzlu.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Informace obsahující vytvořený konzolový token.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.create_console_token(
        server_id=serverid,
        node_id=nodeid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.websocket("/{nodeid}/console")
async def node_console_ws(websocket: WebSocket, nodeid: str):
    """Zprostředkuje websocket SSH konzoli k uzlu.

    Endpoint přijme konzolový token v query parametru, ověří jej
    a následně naváže SSH spojení na cílový host. Poté přeposílá data
    mezi websocket klientem a SSH procesem běžícím na serveru.

    Args:
        websocket: Aktivní websocket spojení s klientem.
        nodeid: Identifikátor uzlu, ke kterému se konzole vztahuje.

    Returns:
        None: Endpoint průběžně zprostředkovává websocket komunikaci a nevrací standardní HTTP tělo odpovědi.
    """
    await websocket.accept()

    ssh_conn = None
    process = None

    try:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008)
            return

        console_data = jwt_verify_console(token)
        if not console_data:
            await websocket.close(code=1008)
            return

        raw = await websocket.receive_text()
        payload = json.loads(raw)

        if payload.get("type") != "auth":
            await websocket.close(code=1008)
            return

        ssh_username = payload.get("ssh_username")
        ssh_password = payload.get("ssh_password")
        ssh_port = int(payload.get("ssh_port", 22))
        cols = int(payload.get("cols", 120))
        rows = int(payload.get("rows", 30))

        if not ssh_username or not ssh_password:
            await websocket.close(code=1008)
            return

        ssh_conn = await asyncssh.connect(
            host=console_data["host"],
            port=ssh_port,
            username=ssh_username,
            password=ssh_password,
            known_hosts=None
        )

        process = await ssh_conn.create_process(
            term_type="xterm",
            term_size=(cols, rows)
        )

        async def ssh_to_ws():
            """Přeposílá výstup SSH procesu směrem ke websocket klientovi."""
            while True:
                data = await process.stdout.read(1024)
                if not data:
                    break
                await websocket.send_text(data)

        async def ws_to_ssh():
            """Přeposílá vstup websocket klienta do SSH procesu."""
            while True:
                raw_inner = await websocket.receive_text()
                inner = json.loads(raw_inner)

                msg_type = inner.get("type")

                if msg_type == "input":
                    process.stdin.write(inner["data"])

                elif msg_type == "resize":
                    process.term_size = (
                        int(inner["cols"]),
                        int(inner["rows"])
                    )

        await asyncio.gather(ssh_to_ws(), ws_to_ssh())

    except WebSocketDisconnect:
        pass

    except Exception as e:
        try:
            await websocket.send_text(f"\r\n[ERROR] {str(e)}\r\n")
        except Exception:
            pass

    finally:
        try:
            if process:
                process.stdin.close()
        except Exception:
            pass

        try:
            if ssh_conn:
                ssh_conn.close()
                await ssh_conn.wait_closed()
        except Exception:
            pass


@router.post("/{nodeid}/logs/{limit}", response_model=dict)
def get_node_logs(
    serverid: int,
    nodeid: str,
    request: Request,
    limit: int,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí logy uzlu.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        limit: Maximální počet vrácených log záznamů.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Logy uzlu.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return NodeService.get_node_logs(
        server_id=serverid,
        node_id=nodeid,
        limit=limit,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )