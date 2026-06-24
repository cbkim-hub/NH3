from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActionWorkOrderStatus(StrEnum):
    ISSUED = "Issued"
    ACKNOWLEDGED = "Acknowledged"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


class ActionPriority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ActionWorkOrderCreate(BaseModel):
    risk_event_id: UUID = Field(alias="riskEventId", description="작업 지시 대상 위험 이벤트 ID")
    assignee_id: UUID = Field(alias="assigneeId", description="현장 담당자 사용자 ID")
    title: str = Field(min_length=1, max_length=200, description="작업 지시 제목")
    instruction: str = Field(min_length=1, description="현장 작업 지시 내용")
    priority: ActionPriority = Field(default=ActionPriority.MEDIUM, description="작업 우선순위")
    due_at: datetime | None = Field(default=None, alias="dueAt", description="작업 완료 목표 시각")
    metadata: dict[str, Any] = Field(default_factory=dict, description="작업 지시 확장 메타데이터")

    model_config = ConfigDict(populate_by_name=True)


class ActionWorkOrderUpdate(BaseModel):
    assignee_id: UUID | None = Field(default=None, alias="assigneeId")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    instruction: str | None = Field(default=None, min_length=1)
    priority: ActionPriority | None = None
    due_at: datetime | None = Field(default=None, alias="dueAt")
    status: ActionWorkOrderStatus | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class ActionAssigneeRequest(BaseModel):
    assignee_id: UUID = Field(alias="assigneeId", description="새 담당자 사용자 ID")
    comment: str | None = Field(default=None, description="담당자 지정/변경 메모")

    model_config = ConfigDict(populate_by_name=True)


class ActionPhotoAttachRequest(BaseModel):
    photo_urls: list[str] = Field(alias="photoUrls", min_length=1, description="첨부할 현장 사진 URL 목록")
    comment: str | None = Field(default=None, description="사진 첨부 메모")
    metadata: dict[str, Any] = Field(default_factory=dict, description="사진 첨부 확장 메타데이터")

    model_config = ConfigDict(populate_by_name=True)


class ActionStatusChangeRequest(BaseModel):
    status: ActionWorkOrderStatus = Field(description="변경할 작업 상태")
    comment: str | None = Field(default=None, description="상태 변경 메모")

    model_config = ConfigDict(populate_by_name=True)


class FieldWorkReportRequest(BaseModel):
    comment: str = Field(min_length=1, description="현장 작업 진행 내용")
    photo_urls: list[str] = Field(default_factory=list, alias="photoUrls", description="현장 사진 URL 목록")
    metadata: dict[str, Any] = Field(default_factory=dict, description="현장 작업 확장 메타데이터")

    model_config = ConfigDict(populate_by_name=True)


class CompleteWorkReportRequest(BaseModel):
    summary: str = Field(min_length=1, description="완료 보고 요약")
    photo_urls: list[str] = Field(default_factory=list, alias="photoUrls", description="완료 증빙 사진 URL 목록")
    metadata: dict[str, Any] = Field(default_factory=dict, description="완료 보고 확장 메타데이터")

    model_config = ConfigDict(populate_by_name=True)


class ActionWorkOrderCloseRequest(BaseModel):
    comment: str | None = Field(default=None, description="작업 및 위험 이벤트 종결 메모")
    metadata: dict[str, Any] = Field(default_factory=dict, description="종결 처리 확장 메타데이터")

    model_config = ConfigDict(populate_by_name=True)


class ActionWorkOrderRead(BaseModel):
    id: UUID
    risk_event_id: UUID = Field(alias="riskEventId")
    assignee_id: UUID | None = Field(default=None, alias="assigneeId")
    issued_by_id: UUID | None = Field(default=None, alias="issuedById")
    title: str
    instruction: str
    priority: ActionPriority
    status: ActionWorkOrderStatus
    due_at: datetime | None = Field(default=None, alias="dueAt")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    completion_summary: str | None = Field(default=None, alias="completionSummary")
    metadata: dict[str, Any]
    photo_urls: list[str] = Field(alias="photoUrls")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    created_by: UUID | None = Field(default=None, alias="createdBy")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ActionWorkOrderListResponse(BaseModel):
    items: list[ActionWorkOrderRead]
    total: int
    page: int
    size: int


class ActionWorkflowSummary(BaseModel):
    risk_event_id: UUID = Field(alias="riskEventId")
    risk_event_status: str = Field(alias="riskEventStatus")
    work_order_status: ActionWorkOrderStatus = Field(alias="workOrderStatus")
    next_step: Literal["작업 지시", "현장 작업", "완료 보고", "종결"] = Field(alias="nextStep")

    model_config = ConfigDict(populate_by_name=True)
