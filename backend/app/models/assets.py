from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.iam import Organization, User
    from app.models.monitoring import AIAnalysis, RiskEvent
    from app.models.telemetry import SensorData


class Pipeline(BaseModel, Base):
    __tablename__ = "pipelines"
    __table_args__ = (
        UniqueConstraint("code", name="uq_pipelines_code"),
        {"schema": "asset"},
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iam.organizations.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    pipeline_type: Mapped[str] = mapped_column(String(40), nullable=False)
    material: Mapped[str | None] = mapped_column(String(80), nullable=True)
    diameter_mm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    depth_m: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    length_m: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    risk_grade: Mapped[str | None] = mapped_column(String(1), nullable=True)
    installed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    geom: Mapped[Any] = mapped_column(Geometry("LINESTRING", srid=4326, spatial_index=True), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    organization: Mapped[Organization | None] = relationship(back_populates="pipelines")
    creator: Mapped[User | None] = relationship(back_populates="pipelines_created", foreign_keys="Pipeline.created_by")
    images: Mapped[list[PipelineImage]] = relationship(back_populates="pipeline", cascade="all, delete-orphan")
    sensors: Mapped[list[Sensor]] = relationship(back_populates="pipeline")
    ai_analyses: Mapped[list[AIAnalysis]] = relationship(back_populates="pipeline")
    risk_events: Mapped[list[RiskEvent]] = relationship(back_populates="pipeline")


class PipelineImage(BaseModel, Base):
    __tablename__ = "pipeline_images"
    __table_args__ = {"schema": "asset"}

    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    pipeline: Mapped[Pipeline] = relationship(back_populates="images")
    creator: Mapped[User | None] = relationship(back_populates="pipeline_images_created", foreign_keys="PipelineImage.created_by")


class Sensor(BaseModel, Base):
    __tablename__ = "sensors"
    __table_args__ = (
        UniqueConstraint("sensor_code", name="uq_sensors_sensor_code"),
        {"schema": "asset"},
    )

    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.pipelines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sensor_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Online", nullable=False)
    min_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    pipeline: Mapped[Pipeline | None] = relationship(back_populates="sensors")
    creator: Mapped[User | None] = relationship(back_populates="sensors_created", foreign_keys="Sensor.created_by")
    data_points: Mapped[list[SensorData]] = relationship(back_populates="sensor", cascade="all, delete-orphan")
    ai_analyses: Mapped[list[AIAnalysis]] = relationship(back_populates="sensor")
    risk_events: Mapped[list[RiskEvent]] = relationship(back_populates="sensor")
