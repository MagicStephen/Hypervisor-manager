from database.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship


class AutomationTaskRun(Base):
    __tablename__ = "automation_task_runs"

    id = Column(Integer, primary_key=True)
    task_id = Column(
        Integer,
        ForeignKey("automation_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )

    status = Column(String)
    message = Column(Text)

    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    task = relationship("AutomationTask", back_populates="runs")