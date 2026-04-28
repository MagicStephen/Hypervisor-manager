import os
from cryptography.fernet import Fernet

########################################################################
FERNET_KEY = os.getenv("FERNET_KEY")

if not FERNET_KEY:
    raise RuntimeError("FERNET_KEY environment variable is missing!")
########################################################################

FERNET = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None

def fernet_encrypt(password: str) -> str:
    return FERNET.encrypt(password.encode()).decode()

def fernet_decrypt(token: str) -> str:
    return FERNET.decrypt(token.encode()).decode()