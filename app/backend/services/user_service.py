from sqlalchemy.orm import Session
from fastapi import HTTPException
from database.models.user_model import User
from security.JWT_token import jwt_create, jwt_verify


class UserService:
    """Servisní třída pro autentizaci uživatele a validaci JWT tokenu."""

    @staticmethod
    def login(username: str, password: str, db: Session) -> dict:
        """Přihlásí uživatele na základě uživatelského jména a hesla.

        Metoda nejprve ověří přihlašovací údaje uživatele a následně
        vytvoří přístupový JWT token.

        Args:
            username: Uživatelské jméno.
            password: Heslo uživatele.
            db: Aktivní databázová session.

        Returns:
            dict: Slovník obsahující vygenerovaný přístupový token
                ve tvaru `{"user_token": <token>}`.

        Raises:
            HTTPException: Pokud jsou přihlašovací údaje neplatné.
            HTTPException: Pokud se nepodaří vygenerovat token.
        """
        user_id = UserService._validate_credentials(username, password, db)
        token = UserService._create_access_token(user_id)

        return {
            "user_token": token
        }

    @staticmethod
    def validate_token(token: str, db: Session, flag_g_id: bool = False):
        """Ověří platnost JWT tokenu a existenci odpovídajícího uživatele.

        Metoda kontroluje, zda byl token předán, zda je platný
        a zda uživatel uvedený v tokenu existuje v databázi.

        Args:
            token: JWT token předaný klientem.
            db: Aktivní databázová session.
            flag_g_id: Pokud je nastaven na `True`, metoda vrací ID uživatele
                místo standardní validační odpovědi.

        Returns:
            dict: Slovník `{"valid": True}`, pokud je token platný
                a `flag_g_id` je `False`.
            int: ID uživatele, pokud je token platný a `flag_g_id` je `True`.

        Raises:
            HTTPException: Pokud token chybí.
            HTTPException: Pokud je token neplatný nebo expirovaný.
            HTTPException: Pokud uživatel z tokenu neexistuje.
        """
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Missing authentication token."
            )

        user_id = jwt_verify(token)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token."
            )

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token."
            )

        if flag_g_id:
            return user_id

        return {
            "valid": True
        }

    @staticmethod
    def _validate_credentials(username: str, password: str, db: Session) -> int:
        """Ověří přihlašovací údaje uživatele.

        Vyhledá uživatele podle uživatelského jména a porovná zadané heslo
        s uloženým heslem.

        Args:
            username: Uživatelské jméno.
            password: Heslo uživatele.
            db: Aktivní databázová session.

        Returns:
            int: ID autentizovaného uživatele.

        Raises:
            HTTPException: Pokud je uživatelské jméno nebo heslo neplatné.
        """
        user = db.query(User).filter(User.username == username).first()

        if user and user.verify_password(password):
            return user.id

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )

    @staticmethod
    def _create_access_token(user_id: int) -> str:
        """Vytvoří přístupový JWT token pro zadaného uživatele.

        Args:
            user_id: Jedinečné ID uživatele.

        Returns:
            str: Vygenerovaný JWT token.

        Raises:
            HTTPException: Pokud se token nepodaří vytvořit.
        """
        token = jwt_create(user_id)

        if token:
            return token

        raise HTTPException(
            status_code=500,
            detail="Failed to generate access token."
        )