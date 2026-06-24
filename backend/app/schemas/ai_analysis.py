from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AISeverity(StrEnum):
    NORMAL = "Normal"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class AIAnalysisRunRequest(BaseModel):
    pipeline_id: UUID | None = Field(default=None, alias="pipelineId", description="분석 대상 배관 ID. 미지정 시 전체 최근 데이터를 분석합니다.")
    window_minutes: int = Field(default=15, alias="windowMinutes", ge=1, le=1440, description="최근 센서 데이터 분석 윈도우")
    create_risk_event: bool = Field(default=True, alias="createRiskEvent", description="위험 점수가 임계값 이상이면 RiskEvent를 생성합니다.")
    risk_event_threshold: float = Field(default=75, alias="riskEventThreshold", ge=0, le=100, description="RiskEvent 생성 기준 점수")

    model_config = ConfigDict(populate_by_name=True)


class AISignalEvidence(BaseModel):
    detected: bool
    score_contribution: float = Field(alias="scoreContribution")
    latest_value: float | None = Field(default=None, alias="latestValue")
    baseline_value: float | None = Field(default=None, alias="baselineValue")
    change_percent: float | None = Field(default=None, alias="changePercent")
    reason: str

    model_config = ConfigDict(populate_by_name=True)


class AIAnalysisRead(BaseModel):
    id: UUID
    pipeline_id: UUID | None = Field(default=None, alias="pipelineId")
    sensor_id: UUID | None = Field(default=None, alias="sensorId")
    model_name: str = Field(alias="modelName")
    model_version: str = Field(alias="modelVersion")
    analysis_type: str = Field(alias="analysisType")
    risk_score: float = Field(alias="riskScore")
    severity: AISeverity
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")
    evidence: dict[str, Any]
    created_at: datetime = Field(alias="createdAt")
    created_by: UUID | None = Field(default=None, alias="createdBy")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AIAnalysisRunResponse(BaseModel):
    analysis: AIAnalysisRead
    risk_event_id: UUID | None = Field(default=None, alias="riskEventId")
    risk_event_created: bool = Field(alias="riskEventCreated")
    decision: str

    model_config = ConfigDict(populate_by_name=True)
