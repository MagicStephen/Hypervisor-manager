from sqlalchemy import Column, Integer, String
from database.database import Base
from security.Hash import hash_context

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    username = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)

    def set_password(self, password: str):
        self.password = hash_context.hash(password)

    def verify_password(self, password: str) -> bool:
        return hash_context.verify(password, self.password)