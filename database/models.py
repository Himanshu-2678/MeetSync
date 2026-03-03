from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, ForeignKey, func, Index, Float
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Meeting(Base):
    __tablename__ = "meetings"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    filename          = Column(String(255), nullable=False)
    transcript        = Column(Text, nullable=True)
    summary           = Column(Text, nullable=True)
    processing_status = Column(String(20), nullable=False, default="processing")
    created_at        = Column(TIMESTAMP, server_default=func.now())
    session_id        = Column(String(36), nullable=True, index=True)  

    tasks = relationship("Task", back_populates="meeting", cascade="all, delete-orphan")
    metrics = relationship("Meeting Metrics", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    __table_args__ = (
        Index("ix_meetings_processing_status", "processing_status"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id      = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    description     = Column(Text, nullable=False)
    owner           = Column(String(255), nullable=False)
    deadline_raw    = Column(Text, nullable=True)
    deadline_parsed = Column(Date, nullable=True)
    priority        = Column(String(10), nullable=False)
    status          = Column(String(20), nullable=False, default="pending")
    created_at      = Column(TIMESTAMP, server_default=func.now())

    meeting = relationship("Meeting", back_populates="tasks")

    __table_args__ = (
        UniqueConstraint("meeting_id", "description", name="uq_task_meeting_description"),
    )


class MeetingMetrics(Base):
    __tablename__ = "meeting_metrics"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id               = Column(Integer, ForeignKey("meetings.id"), nullable=False, unique=True)
    processing_time_seconds  = Column(Float, nullable=True)
    transcript_word_count    = Column(Integer, nullable=True)
    gemini_retry_count       = Column(Integer, nullable=False, default=0)
    status                   = Column(String(20), nullable=False)
    failure_reason           = Column(Text, nullable=True)
    created_at               = Column(TIMESTAMP, server_default=func.now())

    meeting = relationship("Meeting", back_populates="metrics")