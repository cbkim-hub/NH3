from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineBase(BaseModel):
    code: str = Field(min_length=1, max_length=80, description="배관 고유 코드")
    name: str = Field(min_length=1, max_length=160, description="배관명")
    pipeline_type: str = Field(alias="pipelineType", description="배관 유형")
    material: str | None = Field(default=None, max_length=80, description="배관 재질")
    diameter_mm: float | None = Field(default=None, alias="diameterMm", description="직경(mm)")
    depth_m: float | None = Field(default=None, alias="depthM", description="매설 깊이(m)")
    length_m: float | None = Field(default=None, alias="lengthM", description="배관 길이(m)")
    risk_grade: str | None = Field(default=None, alias="riskGrade", description="위험 등급")
    installed_at: date | None = Field(default=None, alias="installedAt", description="설치일")
    properties: dict[str, Any] = Field(default_factory=dict, description="확장 속성")

    model_config = ConfigDict(populate_by_name=True)


class PipelineCreate(PipelineBase):
    organization_id: UUID | None = Field(default=None, alias="organizationId")
    geometry: dict[str, Any] = Field(
        description="GeoJSON LineString geometry. 예: {\"type\": \"LineString\", \"coordinates\": [[127.0, 37.5], [127.1, 37.6]]}"
    )


class PipelineUpdate(BaseModel):
    organization_id: UUID | None = Field(default=None, alias="organizationId")
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    pipeline_type: str | None = Field(default=None, alias="pipelineType")
    material: str | None = Field(default=None, max_length=80)
    diameter_mm: float | None = Field(default=None, alias="diameterMm")
    depth_m: float | None = Field(default=None, alias="depthM")
    length_m: float | None = Field(default=None, alias="lengthM")
    risk_grade: str | None = Field(default=None, alias="riskGrade")
    installed_at: date | None = Field(default=None, alias="installedAt")
    properties: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class PipelineRead(PipelineBase):
    id: UUID
    organization_id: UUID | None = Field(default=None, alias="organizationId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    created_by: UUID | None = Field(default=None, alias="createdBy")
    geometry: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PipelineListResponse(BaseModel):
    items: list[PipelineRead]
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
