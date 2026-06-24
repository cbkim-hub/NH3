from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class NotificationChannel(StrEnum):
    IN_APP = "InApp"
    EMAIL = "Email"
    SMS = "SMS"


class NotificationStatus(StrEnum):
    PENDING = "Pending"
    SENT = "Sent"
    FAILED = "Failed"
    READ = "Read"


class DashboardAlertRead(BaseModel):
    id: UUID
    risk_event_id: UUID | None = Field(default=None, alias="riskEventId")
    recipient_id: UUID | None = Field(default=None, alias="recipientId")
    channel: NotificationChannel
    title: str
    message: str
    status: NotificationStatus
    sent_at: datetime | None = Field(default=None, alias="sentAt")
    read_at: datetime | None = Field(default=None, alias="readAt")
    payload: dict[str, Any]
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class DashboardAlertListResponse(BaseModel):
    items: list[DashboardAlertRead]
    total: int
    page: int
    size: int


class EmailNotificationRequest(BaseModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)
    risk_event_id: UUID | None = Field(default=None, alias="riskEventId")
    recipient_id: UUID | None = Field(default=None, alias="recipientId")
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class SmsNotificationRequest(BaseModel):
    to: str = Field(min_length=5, max_length=30, description="수신자 전화번호")
    message: str = Field(min_length=1, max_length=1000)
    risk_event_id: UUID | None = Field(default=None, alias="riskEventId")
    recipient_id: UUID | None = Field(default=None, alias="recipientId")
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class NotificationSendResponse(BaseModel):
    notification_id: UUID = Field(alias="notificationId")
    channel: NotificationChannel
    status: NotificationStatus
    provider_message_id: str | None = Field(default=None, alias="providerMessageId")

    model_config = ConfigDict(populate_by_name=True)
