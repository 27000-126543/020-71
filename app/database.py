from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    post_title: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author_name: Mapped[str] = mapped_column(String(128), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scene: Mapped[str] = mapped_column(String(64), default="default")
    emotion_category: Mapped[str] = mapped_column(String(32), nullable=False)
    emotion_label: Mapped[str] = mapped_column(String(32), nullable=False)
    intensity_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    suggested_action: Mapped[str] = mapped_column(String(32), nullable=False)
    action_label: Mapped[str] = mapped_column(String(32), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class RuleConfig(Base):
    __tablename__ = "rule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    observe_threshold: Mapped[float] = mapped_column(Float, default=0.4)
    review_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    block_threshold: Mapped[float] = mapped_column(Float, default=0.9)
    negative_consecutive_count: Mapped[int] = mapped_column(Integer, default=3)
    negative_consecutive_window_minutes: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(64), default="default")
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    target_roles_json: Mapped[str] = mapped_column(Text, default="[]")
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    status: Mapped[str] = mapped_column(String(16), default="sent")
