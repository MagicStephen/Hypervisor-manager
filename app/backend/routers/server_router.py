"""Router pro správu serverů uživatele.

Obsahuje endpointy pro:

- získání seznamu serverů uživatele
- připojení nového serveru
- opětovné připojení existujícího serveru

Všechny endpointy vyžadují validní autentizační token uložený v cookie
`user_token`.
"""
from fastapi import APIRouter, Depends, Cookie, Request
from sqlalchemy.orm import Session

from database.database import get_db
from services.user_service import UserService
from services.server_service import ServerService

router = APIRouter()

@router.get("/", response_model=list[dict])
def get_user_servers(
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Vrátí seznam serverů připojených k aktuálnímu uživateli.

    Args:
        request (Request): FastAPI request obsahující přístup ke sdílenému stavu aplikace.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        Seznam serverů uživatele. Každá položka obsahuje informace
        o serveru, například jeho ID, název, platformu nebo stav připojení.

    Raises:
        HTTPException: Pokud je token neplatný, chybí nebo se servery nepodaří načíst.
    """
    platform_gw = request.app.state.platform_gateway

    user_id = UserService.validate_token(
        token=user_token,
        db=db,
        flag_g_id=True
    )

    return ServerService.get_user_servers(
        user_id=user_id,
        platform_gw=platform_gw,
        db=db
    )


@router.post("/{platform}/connect", response_model=dict)
def server_connect(
    platform: str,
    data: dict,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Připojí nový server k uživatelskému účtu.

    Args:
        platform (str): Typ platformy serveru, například `proxmox` nebo `vmware`.
        data (dict): Request body obsahující:
            - servername (str): Název serveru.
            - host (str): Adresa nebo hostname serveru.
            - port (int): Komunikační port serveru.
            - username (str): Přihlašovací jméno.
            - password (str): Heslo.
        request (Request): FastAPI request pro přístup ke sdíleným službám aplikace.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        dict: Výsledek připojení serveru. Může obsahovat například stav operace,
        detail výsledku nebo identifikátor nově připojeného serveru.

    Raises:
        HTTPException: Pokud selže autentizace nebo připojení k serveru.
    """
    user_id = UserService.validate_token(user_token, db, True)

    platform_gw = request.app.state.platform_gateway

    res = ServerService.connect(
        server_name=data.get("servername"),
        platform=platform,
        host=data.get("host"),
        port=data.get("port"),
        username=data.get("username"),
        password=data.get("password"),
        user_id=user_id,
        platform_gw=platform_gw,
        db=db
    )

    return res


@router.post("/reconnect/{server_id}", response_model=dict)
def server_reconnect(
    server_id: int,
    data: dict,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Znovu připojí existující server k uživatelskému účtu.

    Endpoint se používá typicky v situaci, kdy došlo ke ztrátě připojení,
    změně přihlašovacích údajů nebo je potřeba obnovit přístup k již uloženému
    serveru.

    Args:
        server_id (int): Identifikátor serveru, který má být znovu připojen.
        data (dict): Request body obsahující:
            - password (str): Aktuální heslo k serveru.
        request (Request): FastAPI request pro přístup ke sdíleným službám aplikace.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        Seznam serverů uživatele. Každá položka obsahuje informace o serveru, například jeho ID, název, platformu nebo stav připojení. 

    Raises:
        HTTPException: Pokud je token neplatný, server neexistuje nebo reconnect selže.
    """
    user_service = UserService()
    user_id = user_service.validate_token(user_token, db, True)

    platform_gw = request.app.state.platform_gateway

    res = ServerService.reconnect(
        server_id=server_id,
        user_id=user_id,
        password=data.get("password"),
        platform_gw=platform_gw,
        db=db
    )

    return res
