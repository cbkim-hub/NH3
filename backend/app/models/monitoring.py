from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.assets import Pipeline, Sensor
    from app.models.iam import User


class AIAnalysis(BaseModel, Base):
    __tablename__ = "ai_analyses"
    __table_args__ = {"schema": "monitoring"}

    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.pipelines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sensor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.sensors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    pipeline: Mapped[Pipeline | None] = relationship(back_populates="ai_analyses")
    sensor: Mapped[Sensor | None] = relationship(back_populates="ai_analyses")
    creator: Mapped[User | None] = relationship(back_populates="ai_analyses_created", foreign_keys="AIAnalysis.created_by")
    risk_events: Mapped[list[RiskEvent]] = relationship(back_populates="ai_analysis")


class RiskEvent(BaseModel, Base):
    __tablename__ = "risk_events"
    __table_args__ = {"schema": "monitoring"}

    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.pipelines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sensor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.sensors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ai_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitoring.ai_analyses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Open", nullable=False, index=True)
    location: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    pipeline: Mapped[Pipeline | None] = relationship(back_populates="risk_events")
    sensor: Mapped[Sensor | None] = relationship(back_populates="risk_events")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    ai_analysis: Mapped[AIAnalysis | None] = relationship(back_populates="risk_events")
    creator: Mapped[User | None] = relationship(back_populates="risk_events_created", foreign_keys="RiskEvent.created_by")
    notifications: Mapped[list[Notification]] = relationship(back_populates="risk_event", cascade="all, delete-orphan")
    action_histories: Mapped[list[ActionHistory]] = relationship(back_populates="risk_event", cascade="all, delete-orphan")
    work_orders: Mapped[list[ActionWorkOrder]] = relationship(back_populates="risk_event", cascade="all, delete-orphan")


class Notification(BaseModel, Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "monitoring"}

    risk_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitoring.risk_events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Pending", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    risk_event: Mapped[RiskEvent | None] = relationship(back_populates="notifications")
    recipient: Mapped[User | None] = relationship(foreign_keys=[recipient_id])
    creator: Mapped[User | None] = relationship(back_populates="notifications_created", foreign_keys="Notification.created_by")


class ActionWorkOrder(BaseModel, Base):
    __tablename__ = "action_work_orders"
    __table_args__ = {"schema": "monitoring"}

    risk_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitoring.risk_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    issued_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(30), default="Medium", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Issued", nullable=False, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    photo_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    risk_event: Mapped[RiskEvent] = relationship(back_populates="work_orders")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    issued_by: Mapped[User | None] = relationship(foreign_keys=[issued_by_id])
    creator: Mapped[User | None] = relationship(foreign_keys="ActionWorkOrder.created_by")


class ActionHistory(BaseModel, Base):
    __tablename__ = "action_histories"
    __table_args__ = {"schema": "monitoring"}

    risk_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitoring.risk_events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status_from: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status_to: Mapped[str | None] = mapped_column(String(30), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    photo_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    risk_event: Mapped[RiskEvent | None] = relationship(back_populates="action_histories")
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])
    creator: Mapped[User | None] = relationship(back_populates="action_histories_created", foreign_keys="ActionHistory.created_by")
