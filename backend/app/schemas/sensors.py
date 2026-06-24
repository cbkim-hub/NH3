from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SensorType(StrEnum):
    PRESSURE = "Pressure"
    FLOW = "Flow"
    VIBRATION = "Vibration"
    LEAKAGE = "Leakage"
    TEMPERATURE = "Temperature"


class SensorStatus(StrEnum):
    ONLINE = "Online"
    OFFLINE = "Offline"
    WARNING = "Warning"
    CRITICAL = "Critical"


class SensorBase(BaseModel):
    sensor_code: str = Field(alias="sensorCode", min_length=1, max_length=80, description="센서 고유 코드")
    name: str = Field(min_length=1, max_length=160, description="센서명")
    sensor_type: SensorType = Field(alias="sensorType", description="센서 타입")
    unit: str = Field(min_length=1, max_length=20, description="측정 단위")
    status: SensorStatus = Field(default=SensorStatus.ONLINE, description="센서 상태")
    min_value: float | None = Field(default=None, alias="minValue", description="정상 최소값")
    max_value: float | None = Field(default=None, alias="maxValue", description="정상 최대값")
    metadata_json: dict[str, Any] = Field(default_factory=dict, alias="metadata", description="센서 확장 메타데이터")

    model_config = ConfigDict(populate_by_name=True)


class SensorCreate(SensorBase):
    pipeline_id: UUID | None = Field(default=None, alias="pipelineId", description="설치 배관 ID")
    geometry: dict[str, Any] = Field(description="GeoJSON Point geometry. 예: {\"type\": \"Point\", \"coordinates\": [127.0, 37.5]}")


class SensorUpdate(BaseModel):
    pipeline_id: UUID | None = Field(default=None, alias="pipelineId")
    sensor_code: str | None = Field(default=None, alias="sensorCode", min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    sensor_type: SensorType | None = Field(default=None, alias="sensorType")
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    status: SensorStatus | None = None
    min_value: float | None = Field(default=None, alias="minValue")
    max_value: float | None = Field(default=None, alias="maxValue")
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")
    geometry: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class SensorRead(SensorBase):
    id: UUID
    pipeline_id: UUID | None = Field(default=None, alias="pipelineId")
    last_seen_at: datetime | None = Field(default=None, alias="lastSeenAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    created_by: UUID | None = Field(default=None, alias="createdBy")
    geometry: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SensorListResponse(BaseModel):
    items: list[SensorRead]
    total: int
    page: int
    size: int


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str | None = None
    geometry: dict[str, Any]
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]
    total: int
    page: int
    size: int
