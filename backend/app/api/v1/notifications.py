from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RoleCode, require_roles
from app.core.response import ApiResponse, ok
from app.core.websocket import dashboard_ws_manager
from app.models.iam import User
from app.models.monitoring import Notification
from app.schemas.notifications import (
    EmailNotificationRequest,
    NotificationChannel,
    NotificationSendResponse,
    NotificationStatus,
    SmsNotificationRequest,
)
from app.services.notification_service import notification_delivery_service

router = APIRouter()


@router.post(
    "/email",
    response_model=ApiResponse[NotificationSendResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Email 알림 발송",
    description="Dashboard/Risk Event 알림을 Email 채널로 발송하고 Notification 이력을 저장합니다. MVP에서는 mock provider를 사용합니다.",
)
def send_email_notification(
    payload: EmailNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    result = notification_delivery_service.send_email(str(payload.to), payload.subject, payload.message)
    notification = Notification(
        risk_event_id=payload.risk_event_id,
        recipient_id=payload.recipient_id,
        channel=NotificationChannel.EMAIL.value,
        title=payload.subject,
        message=payload.message,
        status=result.status.value,
        sent_at=datetime.now(timezone.utc) if result.status == NotificationStatus.SENT else None,
        payload={**payload.payload, "to": str(payload.to), "providerMessageId": result.provider_message_id},
        created_by=current_user.id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    dashboard_ws_manager.publish(
        "NotificationCreated",
        {
            "notificationId": str(notification.id),
            "riskEventId": str(notification.risk_event_id) if notification.risk_event_id else None,
            "recipientId": str(notification.recipient_id) if notification.recipient_id else None,
            "channel": notification.channel,
            "title": notification.title,
            "message": notification.message,
            "status": notification.status,
            "sentAt": notification.sent_at.isoformat() if notification.sent_at else None,
        },
    )
    return ok(
        NotificationSendResponse(
            notificationId=notification.id,
            channel=NotificationChannel.EMAIL,
            status=result.status,
            providerMessageId=result.provider_message_id,
        )
    )


@router.post(
    "/sms",
    response_model=ApiResponse[NotificationSendResponse],
    status_code=status.HTTP_201_CREATED,
    summary="SMS 알림 발송",
    description="Dashboard/Risk Event 알림을 SMS 채널로 발송하고 Notification 이력을 저장합니다. MVP에서는 mock provider를 사용합니다.",
)
def send_sms_notification(
    payload: SmsNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    result = notification_delivery_service.send_sms(payload.to, payload.message)
    notification = Notification(
        risk_event_id=payload.risk_event_id,
        recipient_id=payload.recipient_id,
        channel=NotificationChannel.SMS.value,
        title="SMS Alert",
        message=payload.message,
        status=result.status.value,
        sent_at=datetime.now(timezone.utc) if result.status == NotificationStatus.SENT else None,
        payload={**payload.payload, "to": payload.to, "providerMessageId": result.provider_message_id},
        created_by=current_user.id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    dashboard_ws_manager.publish(
        "NotificationCreated",
        {
            "notificationId": str(notification.id),
            "riskEventId": str(notification.risk_event_id) if notification.risk_event_id else None,
            "recipientId": str(notification.recipient_id) if notification.recipient_id else None,
            "channel": notification.channel,
            "title": notification.title,
            "message": notification.message,
            "status": notification.status,
            "sentAt": notification.sent_at.isoformat() if notification.sent_at else None,
        },
    )
    return ok(
        NotificationSendResponse(
            notificationId=notification.id,
            channel=NotificationChannel.SMS,
            status=result.status,
            providerMessageId=result.provider_message_id,
        )
    )


@router.post(
    "/{notification_id}/read",
    response_model=ApiResponse[dict[str, str]],
    summary="Dashboard 알림 읽음 처리",
    description="Dashboard Alert를 Read 상태로 변경합니다.",
)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.status = NotificationStatus.READ.value
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    return ok({"message": "Notification marked as read"})
