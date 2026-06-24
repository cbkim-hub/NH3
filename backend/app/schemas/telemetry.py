from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SensorDataCreate(BaseModel):
    sensor_id: UUID = Field(alias="sensorId")
    measured_at: datetime = Field(alias="measuredAt")
    value: float
    unit: str
    quality: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] | None = Field(default=None, alias="rawPayload")

    model_config = ConfigDict(populate_by_name=True)


class SensorDataRead(BaseModel):
    id: UUID
    sensor_id: UUID = Field(alias="sensorId")
    measured_at: datetime = Field(alias="measuredAt")
    received_at: datetime = Field(alias="receivedAt")
    value: float
    unit: str
    quality: dict[str, Any]
    raw_payload: dict[str, Any] | None = Field(default=None, alias="rawPayload")
    created_at: datetime = Field(alias="createdAt")
    created_by: UUID | None = Field(default=None, alias="createdBy")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
