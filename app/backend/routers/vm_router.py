"""Router pro správu virtuálních strojů.

Tento modul obsahuje endpointy pro práci s virtuálními stroji:

- načítání šablon,
- vytváření a mazání VM,
- čtení stavu a metrik,
- změny stavu,
- práce se snapshoty,
- čtení a úpravy konfigurace,
- práce se zálohami,
- otevření konzole,
- čtení logů,
- websocket proxy pro VNC konzoli.
"""

from fastapi import APIRouter, Response, Depends, Body, Cookie, Request, WebSocket, status
from sqlalchemy.orm import Session
from database.database import get_db
import websockets
import asyncio
import ssl
from websockets.exceptions import ConnectionClosed

from services.user_service import UserService
from services.vm_service import VmService
from database.models.server_model import Server

router = APIRouter()


@router.get("/templates", response_model=list[dict])
def get_templates(
    serverid: int,
    nodeid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí dostupné šablony virtuálních strojů pro zadaný server a uzel.

    Args:
        serverid: Identifikátor serveru, ke kterému uzel patří.
        nodeid: Identifikátor uzlu, ze kterého se načítají VM šablony.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Seznam dostupných šablon virtuálních strojů.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_templates(
        server_id=serverid,
        node_id=nodeid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/", response_model=dict)
def vm_create(
    serverid: int,
    nodeid: str,
    request: Request,
    opts: dict = Body(...),
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vytvoří nový virtuální stroj na zadaném uzlu.

    Args:
        serverid: Identifikátor cílového serveru.
        nodeid: Identifikátor uzlu, na kterém se má VM vytvořit.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        opts: Konfigurační parametry virtuálního stroje, například CPU, RAM, disk nebo šablona.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Výsledek vytvoření virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.create_vm(
        server_id=serverid,
        node_id=nodeid,
        opt_parameters=opts,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.delete("/{vmid}", status_code=status.HTTP_204_NO_CONTENT)
def vm_destroy(
    serverid: int,
    nodeid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Odstraní virtuální stroj.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu, na kterém se virtuální stroj nachází.
        vmid: Identifikátor virtuálního stroje.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Response: Prázdná HTTP odpověď se stavovým kódem 204 No Content.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    VmService.destroy_vm(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{vmid}/status", response_model=dict)
def vm_status(
    serverid: int,
    nodeid: str,
    vmid: str,
    data: dict,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí stav virtuálního stroje podle požadovaných polí.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu, na kterém se virtuální stroj nachází.
        vmid: Identifikátor virtuálního stroje.
        data: Slovník obsahující klíč ``fields`` se seznamem požadovaných stavových položek.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Stavové informace o virtuálním stroji.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_status(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        params=data["fields"],
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )

@router.get("/{vmid}/capabilities", response_model=dict)
def get_templates(
    serverid: int,
    nodeid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_capabilities(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{vmid}/timemetrics", response_model=list[dict])
def vm_timemetrics(
    serverid: int,
    nodeid: str,
    vmid: str,
    data: dict,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí časové metriky virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu, na kterém se virtuální stroj nachází.
        vmid: Identifikátor virtuálního stroje.
        data: Parametry určující, jaké časové metriky mají být vráceny.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Seznam časových metrik virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_time_metrics(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        params=data,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{vmid}/status/{status}", response_model=dict)
def vm_status_change(
    serverid: int,
    nodeid: str,
    vmid: str,
    status: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Změní stav virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu, na kterém se virtuální stroj nachází.
        vmid: Identifikátor virtuálního stroje.
        status: Požadovaný nový stav virtuálního stroje, například start, stop nebo reboot.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Potvrzení o změně stavu virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.set_vm_status(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        status=status,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.get("/{vmid}/snapshots", response_model=list[dict])
def vm_snapshots(
    serverid: int,
    nodeid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí seznam snapshotů virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Seznam snapshotů virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_snapshots(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{vmid}/snapshot", status_code=status.HTTP_204_NO_CONTENT)
def vm_create_snapshot(
    data: dict,
    serverid: int,
    nodeid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vytvoří snapshot virtuálního stroje.

    Args:
        data: Parametry snapshotu, například jeho název nebo další volby vytvoření.
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Response: Prázdná HTTP odpověď se stavovým kódem 204 No Content.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    VmService.create_vm_snapshot(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        snap_data=data,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{vmid}/snapshot/{snapshotid}", status_code=status.HTTP_204_NO_CONTENT)
def vm_rollback_snapshot(
    serverid: int,
    nodeid: str,
    vmid: str,
    snapshotid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Obnoví virtuální stroj do vybraného snapshotu.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        snapshotid: Identifikátor snapshotu, do kterého se má VM obnovit.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Response: Prázdná HTTP odpověď se stavovým kódem 204 No Content.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    VmService.rollback_vm_snapshot(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        snapshotid=snapshotid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{vmid}/snapshot/{snapshotid}", status_code=status.HTTP_204_NO_CONTENT)
def vm_drop_snapshot(
    serverid: int,
    nodeid: str,
    snapshotid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Odstraní snapshot virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        snapshotid: Identifikátor snapshotu, který má být odstraněn.
        vmid: Identifikátor virtuálního stroje.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Response: Prázdná HTTP odpověď se stavovým kódem 204 No Content.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    VmService.drop_vm_snapshot(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        snapshotid=snapshotid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{vmid}/config", response_model=dict)
def vm_current_config(
    serverid: int,
    nodeid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí aktuální konfiguraci virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Aktuální konfigurace virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_config(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{vmid}/config", response_model=dict)
def vm_change_config(
    serverid: int,
    nodeid: str,
    vmid: str,
    data: dict,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Změní konfiguraci virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        data: Slovník s konfiguračními parametry, které mají být změněny.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Výsledek změny konfigurace virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.set_vm_config(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        optional_params=data,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.get("/{vmid}/backups", response_model=list[dict])
def vm_backups(
    serverid: int,
    nodeid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí seznam záloh virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns: 
        Seznam dostupných záloh virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_backups(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )


@router.post("/{vmid}/backup", status_code=status.HTTP_204_NO_CONTENT)
def vm_create_backup(
    serverid: int,
    nodeid: str,
    vmid: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vytvoří zálohu virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        Response: Prázdná HTTP odpověď se stavovým kódem 204 No Content.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    VmService.create_vm_backup(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        user_id=user_id,
        platform_gw=platform_gw,
        db=db,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{vmid}/console/{protocol}", response_model=dict)
def vm_console(
    serverid: int,
    nodeid: str,
    vmid: str,
    protocol: str,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí údaje potřebné pro otevření konzole virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        protocol: Požadovaný konzolový protokol, například vnc nebo webmks.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Informace potřebné pro připojení ke konzoli virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.open_vm_console(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        protocol=protocol,
        user_id=user_id,
        platform_gw=platform_gw,
        request=request,
        db=db,
    )


@router.get("/{vmid}/logs/{limit}", response_model=dict)
def vm_logs(
    serverid: int,
    nodeid: str,
    vmid: str,
    limit: int,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """Vrátí logy virtuálního stroje.

    Args:
        serverid: Identifikátor serveru.
        nodeid: Identifikátor uzlu.
        vmid: Identifikátor virtuálního stroje.
        limit: Maximální počet vrácených log záznamů.
        request: FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token: Autentizační token uživatele uložený v cookie.
        db: Aktivní databázová session.

    Returns:
        dict: Logy virtuálního stroje.
    """
    user_id = UserService.validate_token(user_token, db, True)
    platform_gw = request.app.state.platform_gateway

    return VmService.get_vm_logs(
        server_id=serverid,
        node_id=nodeid,
        vm_id=vmid,
        user_id=user_id,
        limit=limit,
        platform_gw=platform_gw,
        db=db,
    )


@router.websocket("/{vmid}/console/vnc")
async def vm_vnc_ws_proxy(
    websocket: WebSocket,
    serverid: int,
    nodeid: str,
    vmid: str,
):
    """Proxy websocket spojení mezi klientem a upstream VNC konzolí VM.

    Endpoint ověří uživatele podle cookie tokenu, získá informace o konzoli
    virtuálního stroje a následně přeposílá data mezi klientským websocketem
    a upstream websocket/TCP připojením na platformě.

    Args:
        websocket: Aktivní websocket spojení s klientem.
        serverid: Identifikátor serveru, ke kterému virtuální stroj patří.
        nodeid: Identifikátor uzlu, na kterém se virtuální stroj nachází.
        vmid: Identifikátor virtuálního stroje.
    """

    upstream_ws = None
    upstream_reader = None
    upstream_writer = None
    db = next(get_db())

    upstream_close_code = None
    upstream_close_reason = ""
    browser_close_code = None
    upstream_mode = None

    try:
        user_token = websocket.cookies.get("user_token")
        user_id = UserService.validate_token(user_token, db, True)

        platform_gw = websocket.app.state.platform_gateway

        server = (
            db.query(Server)
            .filter(Server.user_id == user_id, Server.id == serverid)
            .first()
        )

        if not server:
            await websocket.close(code=1008)
            return

        platform = server.platform.name.lower()

        session_id = platform_gw.sessions.get_id(
            user_id=user_id,
            platform=server.platform.name,
            host=server.host,
        )

        vm_api = platform_gw.get_vm_api(session_id)


        console_info = vm_api.open_console(
            nodeid,
            vmid,
            "vnc",
        )

        cookie_header = None
        upstream_subprotocols = None
        upstream_url = console_info.get("ws_url")

        if platform == "xen":
            upstream_mode = "ws"
            cookie_header = f"session_id={console_info['ticket']}"
            upstream_subprotocols = ["binary", "base64"]

        elif platform == "proxmox":
            upstream_mode = "ws"
            cookie_header = f"PVEAuthCookie={vm_api.conn.ticket}"

        elif platform == "kvm":
            upstream_mode = "ws" if upstream_url else "tcp"

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        await websocket.accept()

        if upstream_mode == "ws":
            connect_kwargs = {
                "uri": upstream_url,
                "max_size": None,
                "open_timeout": 10,
            }

            if upstream_url.startswith("wss://"):
                connect_kwargs["ssl"] = ssl_context

            if cookie_header:
                connect_kwargs["additional_headers"] = [("Cookie", cookie_header)]

            if upstream_subprotocols:
                connect_kwargs["subprotocols"] = upstream_subprotocols

            if platform == "xen":
                connect_kwargs["ping_interval"] = None
                connect_kwargs["ping_timeout"] = None
            else:
                connect_kwargs["ping_interval"] = 10
                connect_kwargs["ping_timeout"] = 30

            upstream_ws = await websockets.connect(**connect_kwargs)

        else:
            host = console_info["host"]
            port = console_info["port"]
            upstream_reader, upstream_writer = await asyncio.open_connection(host, port)

        async def browser_to_upstream():
            """Přeposílá data od klienta směrem k upstream konzoli."""
            nonlocal browser_close_code

            try:
                while True:
                    message = await websocket.receive()

                    if message["type"] == "websocket.disconnect":
                        browser_close_code = message.get("code")
                        break

                    data = None
                    if message.get("bytes") is not None:
                        data = message["bytes"]
                    elif message.get("text") is not None:
                        data = message["text"]

                    if data is None:
                        continue

                    if upstream_mode == "ws":
                        await upstream_ws.send(data)
                    else:
                        if isinstance(data, str):
                            data = data.encode("utf-8")
                        upstream_writer.write(data)
                        await upstream_writer.drain()

            except Exception:
                pass

        async def upstream_to_browser():
            """Přeposílá data z upstream konzole směrem ke klientovi."""
            nonlocal upstream_close_code, upstream_close_reason

            try:
                if upstream_mode == "ws":
                    while True:
                        message = await upstream_ws.recv()

                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                else:
                    while True:
                        chunk = await upstream_reader.read(65536)
                        if not chunk:
                            upstream_close_code = 1000
                            upstream_close_reason = "Upstream TCP connection closed"
                            break

                        await websocket.send_bytes(chunk)

            except ConnectionClosed as exc:
                upstream_close_code = getattr(exc, "code", None)
                upstream_close_reason = getattr(exc, "reason", "") or ""

            except Exception:
                pass

        browser_task = asyncio.create_task(browser_to_upstream())
        upstream_task = asyncio.create_task(upstream_to_browser())

        done, pending = await asyncio.wait(
            [browser_task, upstream_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        for task in pending:
            try:
                await task
            except Exception:
                pass

        try:
            if browser_close_code is not None:
                pass
            elif upstream_close_code in (1000, 1001):
                await websocket.close(code=1000)
            elif upstream_close_code == 1006:
                await websocket.close(
                    code=1011,
                    reason="Upstream console connection dropped",
                )
            elif upstream_close_code is not None:
                await websocket.close(
                    code=1011,
                    reason=upstream_close_reason or "Upstream console closed",
                )
            else:
                await websocket.close(code=1000)
        except Exception:
            pass

    except Exception:
        try:
            await websocket.close(code=1011, reason="Internal proxy error")
        except Exception:
            pass

    finally:
        try:
            if upstream_ws is not None:
                await upstream_ws.close()
        except Exception:
            pass

        try:
            if upstream_writer is not None:
                upstream_writer.close()
                await upstream_writer.wait_closed()
        except Exception:
            pass

        try:
            db.close()
        except Exception:
            pass 
