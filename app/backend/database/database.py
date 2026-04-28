# core/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# načte proměnné z .env (např. DATABASE_URL)
load_dotenv()

# URL databáze, pokud není v .env, použije default SQLite soubor
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# vytvoření engine pro SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # nutné pro SQLite
)

# session pro CRUD operace
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base třída pro všechny ORM modely
Base = declarative_base()

def get_db():
    """
    Funkce pro získání DB session, která se automaticky zavře po requestu
    """
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()