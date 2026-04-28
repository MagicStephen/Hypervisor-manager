import os
from dotenv import load_dotenv

load_dotenv()

# --- CROSS VALIDATION --- #
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# --- BACKUP ROOT FOLDER --- #
BACKUP_ROOT = "/mnt/nfs/backups"

# --- REMOTE LOG FOLDER --- #
LOG_ROOT = "/var/log/remote"

# --- COOKIE CONFIG ---
COOKIE_HTTPONLY = True
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
COOKIE_MAX_AGE = int(os.getenv("COOKIE_MAX_AGE", 60 * 60 * 2))  # 2h