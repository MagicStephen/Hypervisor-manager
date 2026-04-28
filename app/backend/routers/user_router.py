from fastapi import APIRouter, Depends, Cookie
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from services.user_service import UserService
from database.database import get_db
from config import COOKIE_HTTPONLY, COOKIE_SECURE, COOKIE_SAMESITE, COOKIE_MAX_AGE

router = APIRouter()

@router.post("/login", response_model=dict)
def login(
    req: dict, 
    db: Session = Depends(get_db)
):
    """Autentizuje uživatele a nastaví autentizační cookie.

    Args:
        req (dict): Request body obsahující:
            - username (str): Uživatelské jméno
            - password (str): Heslo
        db (Session): Aktivní databázová session.

    Returns:
        JSONResponse: Odpověď obsahující informaci o úspěšné autentizaci.
        Zároveň nastavuje cookie:
            - user_token (str): Autentizační token uživatele

    Raises:
        HTTPException: Pokud jsou přihlašovací údaje neplatné.
    """
    result = UserService.login(req["username"], req["password"], db)
    token = result["user_token"]

    response = JSONResponse(content={"authenticated": True})

    response.set_cookie(
        key="user_token",
        value=token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE
    )

    return response


@router.get("/token_valid", response_model=dict)
def get_current_user(
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Ověří platnost autentizačního tokenu uživatele.

    Args:
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        dict: Výsledek validace tokenu

    Raises:
        HTTPException: Pokud dojde k chybě při validaci tokenu.
    """
    
    return UserService.validate_token(user_token, db)