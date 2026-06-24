from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import RoleCode, require_roles
from app.core.database import get_db
from app.core.response import ApiResponse, ok
from app.models.monitoring import Notification
from app.schemas.notifications import DashboardAlertListResponse, DashboardAlertRead, NotificationChannel, NotificationStatus
from app.models.iam import User

router = APIRouter()


class DashboardOverview(BaseModel):
    active_alerts: int = 0
    critical_alerts: int = 0
    active_sensors: int = 0
    pipeline_count: int = 0


@router.get("/overview")
def overview(
    current_user: User = Depends(
        require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)
    ),
):
    return ok(DashboardOverview())


def _to_dashboard_alert(notification: Notification) -> DashboardAlertRead:
    return DashboardAlertRead(
        id=notification.id,
        riskEventId=notification.risk_event_id,
        recipientId=notification.recipient_id,
        channel=notification.channel,
        title=notification.title,
        message=notification.message,
        status=notification.status,
        sentAt=notification.sent_at,
        readAt=notification.read_at,
        payload=notification.payload,
        createdAt=notification.created_at,
    )


@router.get(
    "/alerts",
    response_model=ApiResponse[DashboardAlertListResponse],
    summary="Dashboard Alert 목록",
    description="Dashboard에서 표시할 InApp/Email/SMS 알림 목록을 페이지네이션과 채널/상태 필터로 조회합니다.",
)
def dashboard_alerts(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    channel: NotificationChannel | None = None,
    alert_status: NotificationStatus | None = Query(default=None, alias="status"),
    recipient_id: UUID | None = Query(default=None, alias="recipientId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    filters = []
    if channel is not None:
        filters.append(Notification.channel == channel.value)
    if alert_status is not None:
        filters.append(Notification.status == alert_status.value)
    if recipient_id is not None:
        filters.append(Notification.recipient_id == recipient_id)

    total = db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
    notifications = db.scalars(
        select(Notification).where(*filters).order_by(Notification.created_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return ok(DashboardAlertListResponse(items=[_to_dashboard_alert(item) for item in notifications], total=total, page=page, size=size))
