from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base

class ServerNode(Base):
    __tablename__ = "server_nodes"

    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, primary_key=True)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False, primary_key=True)

    server = relationship("Server", back_populates="server_nodes")
    node = relationship("Node", back_populates="server_nodes")