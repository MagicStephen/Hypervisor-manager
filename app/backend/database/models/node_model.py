from sqlalchemy import Column, Integer, String
from database.database import Base
from sqlalchemy.orm import relationship

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    host = Column(String, nullable=False)

    cluster = Column(String, nullable=True)

    server_nodes = relationship("ServerNode", back_populates="node", cascade="all, delete-orphan")