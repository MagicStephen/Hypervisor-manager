
import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError 

# GENERATION JWT TICKET FOR ACCESS TO VPM APP
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

def jwt_create(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def jwt_verify(token: str) -> int | None:
    """
    Dekóduje JWT token a vrátí user_id, pokud je platný.
    Pokud token není platný nebo vypršel, vrátí None.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        
        return user_id
    
    except ExpiredSignatureError:
        return None
    
    except JWTError:
        return None
    
def jwt_create_console(user_id: int, server_id: int, node_id: str, platform: str, host: str, expires_seconds: int = 60):
    
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_seconds)

    payload = {
        "sub": str(user_id),
        "kind": "console",
        "server_id": server_id,
        "node_id": node_id,
        "platform": platform,
        "host": host,
        "exp": expire
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def jwt_verify_console(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("kind") != "console":
            return None

        return {
            "user_id": int(payload.get("sub")),
            "server_id": int(payload.get("server_id")),
            "node_id": payload.get("node_id"),
            "platform": payload.get("platform"),
            "host": payload.get("host"),
        }

    except ExpiredSignatureError:
        return None
    except JWTError:
        return None