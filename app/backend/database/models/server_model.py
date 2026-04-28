from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, index=True)

    host = Column(String, nullable=False)
    port = Column(Integer)
    username = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    
    platform = relationship("Platform", back_populates="servers")
    server_nodes = relationship("ServerNode", back_populates="server")

    auth_id = Column(Integer, ForeignKey("server_automation_auth.id"), nullable=True)
    auth = relationship("ServerAutomationAuth")