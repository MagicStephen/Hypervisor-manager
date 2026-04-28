from sqlalchemy import Column, Integer, String, Text
from database.database import Base


class ServerAutomationAuth(Base):
    __tablename__ = "server_automation_auth"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String, nullable=True)
    password_encrypted = Column(Text, nullable=True)

    token_id = Column(String, nullable=True)
    token_secret_encrypted = Column(Text, nullable=True)