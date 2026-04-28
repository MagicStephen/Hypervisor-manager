from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.database import Base


class AutomationTask(Base):
    __tablename__ = "automation_tasks"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)

    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    server = relationship("Server")

    parent_id = Column(Integer, ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=True)

    order_index = Column(Integer, nullable=False, default=0)

    node_id = Column(String, nullable=True)
    vm_id = Column(String, nullable=False)

    action = Column(String, nullable=False)
    trigger_type = Column(String, nullable=True)

    cron_expression = Column(String, nullable=True)
    interval_seconds = Column(Integer, nullable=True)
    run_at = Column(DateTime(timezone=True), nullable=True)

    snapshot_name = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    parent = relationship(
        "AutomationTask",
        remote_side=[id],
        back_populates="children"
    )

    children = relationship(
        "AutomationTask",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="AutomationTask.order_index",
    )

    runs = relationship(
        "AutomationTaskRun",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )