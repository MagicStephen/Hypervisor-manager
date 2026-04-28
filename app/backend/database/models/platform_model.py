from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)

    servers = relationship("Server", back_populates="platform")