from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.assets import Pipeline, PipelineImage, Sensor
    from app.models.monitoring import AIAnalysis, ActionHistory, Notification, RiskEvent
    from app.models.telemetry import SensorData

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("iam.users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("iam.roles.id", ondelete="CASCADE"), primary_key=True),
    schema="iam",
)


class Organization(BaseModel, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("code", name="uq_organizations_code"),
        {"schema": "iam"},
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.organizations.id", ondelete="SET NULL"), nullable=True
    )

    parent: Mapped[Organization | None] = relationship(remote_side="Organization.id", back_populates="children")
    children: Mapped[list[Organization]] = relationship(back_populates="parent")
    users: Mapped[list[User]] = relationship(back_populates="organization")
    pipelines: Mapped[list[Pipeline]] = relationship(back_populates="organization")


class Role(BaseModel, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("code", name="uq_roles_code"),
        {"schema": "iam"},
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")


class Tenant(BaseModel, Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "iam"}

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class User(BaseModel, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        {"schema": "iam"},
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("iam.tenants.id"), nullable=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.organizations.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)

    organization: Mapped[Organization | None] = relationship(back_populates="users")
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, back_populates="users")
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user", cascade="all, delete-orphan")

    pipelines_created: Mapped[list[Pipeline]] = relationship(back_populates="creator", foreign_keys="Pipeline.created_by")
    pipeline_images_created: Mapped[list[PipelineImage]] = relationship(back_populates="creator", foreign_keys="PipelineImage.created_by")
    sensors_created: Mapped[list[Sensor]] = relationship(back_populates="creator", foreign_keys="Sensor.created_by")
    sensor_data_created: Mapped[list[SensorData]] = relationship(back_populates="creator", foreign_keys="SensorData.created_by")
    ai_analyses_created: Mapped[list[AIAnalysis]] = relationship(back_populates="creator", foreign_keys="AIAnalysis.created_by")
    risk_events_created: Mapped[list[RiskEvent]] = relationship(back_populates="creator", foreign_keys="RiskEvent.created_by")
    notifications_created: Mapped[list[Notification]] = relationship(back_populates="creator", foreign_keys="Notification.created_by")
    action_histories_created: Mapped[list[ActionHistory]] = relationship(back_populates="creator", foreign_keys="ActionHistory.created_by")


class RefreshToken(BaseModel, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        {"schema": "iam"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
