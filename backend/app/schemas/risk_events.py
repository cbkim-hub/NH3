from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RiskSeverity(StrEnum):
    NORMAL = "Normal"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class RiskEventStatus(StrEnum):
    OPEN = "Open"
    INVESTIGATING = "Investigating"
    IN_PROGRESS = "InProgress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class RiskEventBase(BaseModel):
    event_code: str = Field(alias="eventCode", min_length=1, max_length=80, description="위험 이벤트 고유 코드")
    title: str = Field(min_length=1, max_length=200, description="이벤트 제목")
    description: str | None = Field(default=None, description="이벤트 설명")
    pipeline_id: UUID | None = Field(default=None, alias="pipelineId", description="관련 배관 ID")
    sensor_id: UUID | None = Field(default=None, alias="sensorId", description="관련 센서 ID")
    assignee_id: UUID | None = Field(default=None, alias="assigneeId", description="담당자 사용자 ID")
    severity: RiskSeverity = Field(description="위험도 등급")
    risk_score: float = Field(alias="riskScore", ge=0, le=100, description="위험 점수 0~100")
    status: RiskEventStatus = Field(default=RiskEventStatus.OPEN, description="처리 상태")
    location: dict[str, Any] | None = Field(default=None, description="GeoJSON Point location")
    detected_at: datetime = Field(alias="detectedAt", description="탐지 시각")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt", description="해결 시각")
    evidence: dict[str, Any] = Field(default_factory=dict, description="AI/룰 기반 판단 근거")

    model_config = ConfigDict(populate_by_name=True)


class RiskEventCreate(RiskEventBase):
    pass


class RiskEventUpdate(BaseModel):
    event_code: str | None = Field(default=None, alias="eventCode", min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    pipeline_id: UUID | None = Field(default=None, alias="pipelineId")
    sensor_id: UUID | None = Field(default=None, alias="sensorId")
    assignee_id: UUID | None = Field(default=None, alias="assigneeId")
    severity: RiskSeverity | None = None
    risk_score: float | None = Field(default=None, alias="riskScore", ge=0, le=100)
    status: RiskEventStatus | None = None
    location: dict[str, Any] | None = None
    detected_at: datetime | None = Field(default=None, alias="detectedAt")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")
    evidence: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class RiskEventRead(RiskEventBase):
    id: UUID
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    created_by: UUID | None = Field(default=None, alias="createdBy")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class RiskEventListResponse(BaseModel):
    items: list[RiskEventRead]
    total: int
    page: int
    size: int


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str | None = None
    geometry: dict[str, Any] | None
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]
    total: int
    page: int
    size: int


class RiskEventStats(BaseModel):
    total: int
    open: int
    investigating: int
    in_progress: int = Field(alias="inProgress")
    resolved: int
    closed: int
    critical: int
    high: int
    average_risk_score: float = Field(alias="averageRiskScore")

    model_config = ConfigDict(populate_by_name=True)


class RiskSeverityAggregate(BaseModel):
    severity: RiskSeverity
    count: int
    average_risk_score: float = Field(alias="averageRiskScore")

    model_config = ConfigDict(populate_by_name=True)


class RiskEventAssignRequest(BaseModel):
    assignee_id: UUID = Field(alias="assigneeId", description="담당자 사용자 ID")
    comment: str | None = Field(default=None, description="배정 메모")

    model_config = ConfigDict(populate_by_name=True)


class ActionHistoryCreate(BaseModel):
    action_type: str = Field(alias="actionType", min_length=1, max_length=80, description="조치 유형")
    status_to: RiskEventStatus | None = Field(default=None, alias="statusTo", description="변경할 이벤트 상태")
    comment: str | None = Field(default=None, description="조치 메모")
    photo_urls: list[str] = Field(default_factory=list, alias="photoUrls", description="첨부 사진 URL 목록")
    metadata: dict[str, Any] = Field(default_factory=dict, description="조치 확장 메타데이터")

    model_config = ConfigDict(populate_by_name=True)


class RiskEventCompleteRequest(BaseModel):
    comment: str | None = Field(default=None, description="완료 메모")
    photo_urls: list[str] = Field(default_factory=list, alias="photoUrls", description="완료 증빙 사진 URL 목록")

    model_config = ConfigDict(populate_by_name=True)


class ActionHistoryRead(BaseModel):
    id: UUID
    risk_event_id: UUID | None = Field(default=None, alias="riskEventId")
    actor_id: UUID | None = Field(default=None, alias="actorId")
    action_type: str = Field(alias="actionType")
    status_from: str | None = Field(default=None, alias="statusFrom")
    status_to: str | None = Field(default=None, alias="statusTo")
    comment: str | None = None
    action_at: datetime = Field(alias="actionAt")
    metadata_json: dict[str, Any] = Field(alias="metadata")
    photo_urls: list[str] = Field(alias="photoUrls")
    created_at: datetime = Field(alias="createdAt")
    created_by: UUID | None = Field(default=None, alias="createdBy")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
