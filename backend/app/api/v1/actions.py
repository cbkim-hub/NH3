from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RoleCode, require_roles
from app.core.response import ApiResponse, ok
from app.core.websocket import dashboard_ws_manager
from app.models.iam import User
from app.models.monitoring import ActionHistory, ActionWorkOrder, RiskEvent
from app.schemas.actions import (
    ActionAssigneeRequest,
    ActionPhotoAttachRequest,
    ActionStatusChangeRequest,
    ActionWorkOrderCloseRequest,
    ActionWorkOrderCreate,
    ActionWorkOrderListResponse,
    ActionWorkOrderRead,
    ActionWorkOrderStatus,
    ActionWorkOrderUpdate,
    ActionWorkflowSummary,
    CompleteWorkReportRequest,
    FieldWorkReportRequest,
)

router = APIRouter()


def _to_work_order_read(work_order: ActionWorkOrder) -> ActionWorkOrderRead:
    return ActionWorkOrderRead(
        id=work_order.id,
        riskEventId=work_order.risk_event_id,
        assigneeId=work_order.assignee_id,
        issuedById=work_order.issued_by_id,
        title=work_order.title,
        instruction=work_order.instruction,
        priority=work_order.priority,
        status=work_order.status,
        dueAt=work_order.due_at,
        startedAt=work_order.started_at,
        completedAt=work_order.completed_at,
        completionSummary=work_order.completion_summary,
        metadata=work_order.metadata_json,
        photoUrls=work_order.photo_urls,
        createdAt=work_order.created_at,
        updatedAt=work_order.updated_at,
        createdBy=work_order.created_by,
    )


def _create_history(
    db: Session,
    event: RiskEvent,
    actor: User,
    action_type: str,
    status_from: str | None,
    status_to: str | None,
    comment: str | None,
    photo_urls: list[str] | None = None,
    metadata: dict | None = None,
) -> ActionHistory:
    history = ActionHistory(
        risk_event_id=event.id,
        actor_id=actor.id,
        action_type=action_type,
        status_from=status_from,
        status_to=status_to,
        comment=comment,
        action_at=datetime.now(timezone.utc),
        metadata_json=metadata or {},
        photo_urls=photo_urls or [],
        created_by=actor.id,
    )
    db.add(history)
    return history


def _publish_action_event(event_type: str, work_order: ActionWorkOrder, event: RiskEvent) -> None:
    dashboard_ws_manager.publish(
        event_type,
        {
            "workOrderId": str(work_order.id),
            "riskEventId": str(event.id),
            "riskEventStatus": event.status,
            "workOrderStatus": work_order.status,
            "assigneeId": str(work_order.assignee_id) if work_order.assignee_id else None,
            "title": work_order.title,
            "occurredAt": datetime.now(timezone.utc).isoformat(),
        },
    )


def _load_work_order(db: Session, work_order_id: UUID) -> ActionWorkOrder:
    work_order = db.get(ActionWorkOrder, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action work order not found")
    return work_order


def _load_event_for_work_order(db: Session, work_order: ActionWorkOrder) -> RiskEvent:
    event = db.get(RiskEvent, work_order.risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    return event


def _sync_risk_event_status(event: RiskEvent, work_order_status: str) -> None:
    if work_order_status == ActionWorkOrderStatus.IN_PROGRESS.value:
        event.status = "InProgress"
    elif work_order_status == ActionWorkOrderStatus.COMPLETED.value:
        event.status = "Resolved"
        event.resolved_at = event.resolved_at or datetime.now(timezone.utc)
    elif work_order_status == ActionWorkOrderStatus.CLOSED.value:
        event.status = "Closed"


def _workflow_summary(event: RiskEvent, work_order: ActionWorkOrder) -> ActionWorkflowSummary:
    if work_order.status in {ActionWorkOrderStatus.ISSUED.value, ActionWorkOrderStatus.ACKNOWLEDGED.value}:
        next_step = "현장 작업"
    elif work_order.status == ActionWorkOrderStatus.IN_PROGRESS.value:
        next_step = "완료 보고"
    elif work_order.status in {ActionWorkOrderStatus.COMPLETED.value, ActionWorkOrderStatus.CLOSED.value}:
        next_step = "종결"
    else:
        next_step = "작업 지시"
    return ActionWorkflowSummary(
        riskEventId=event.id,
        riskEventStatus=event.status,
        workOrderStatus=work_order.status,
        nextStep=next_step,
    )


@router.get(
    "/work-orders",
    response_model=ApiResponse[ActionWorkOrderListResponse],
    summary="작업 지시 목록 조회",
    description="위험 이벤트 기반 작업 지시를 페이지네이션과 상태/담당자/이벤트 필터로 조회합니다.",
)
def list_work_orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    work_status: ActionWorkOrderStatus | None = Query(default=None, alias="status"),
    risk_event_id: UUID | None = Query(default=None, alias="riskEventId"),
    assignee_id: UUID | None = Query(default=None, alias="assigneeId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    filters = []
    if work_status is not None:
        filters.append(ActionWorkOrder.status == work_status.value)
    if risk_event_id is not None:
        filters.append(ActionWorkOrder.risk_event_id == risk_event_id)
    if assignee_id is not None:
        filters.append(ActionWorkOrder.assignee_id == assignee_id)

    total = db.scalar(select(func.count()).select_from(ActionWorkOrder).where(*filters)) or 0
    rows = db.scalars(
        select(ActionWorkOrder)
        .where(*filters)
        .order_by(ActionWorkOrder.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return ok(ActionWorkOrderListResponse(items=[_to_work_order_read(row) for row in rows], total=total, page=page, size=size))


@router.post(
    "/work-orders",
    response_model=ApiResponse[ActionWorkOrderRead],
    status_code=status.HTTP_201_CREATED,
    summary="작업 지시 생성",
    description="위험 이벤트 발생 후 담당자에게 작업을 지시하고 이벤트 상태를 Investigating으로 전환합니다.",
)
def create_work_order(
    payload: ActionWorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    event = db.get(RiskEvent, payload.risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    assignee = db.get(User, payload.assignee_id)
    if assignee is None or assignee.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found or inactive")

    status_from = event.status
    event.assignee_id = payload.assignee_id
    if event.status == "Open":
        event.status = "Investigating"

    work_order = ActionWorkOrder(
        risk_event_id=event.id,
        assignee_id=payload.assignee_id,
        issued_by_id=current_user.id,
        title=payload.title,
        instruction=payload.instruction,
        priority=payload.priority.value,
        status=ActionWorkOrderStatus.ISSUED.value,
        due_at=payload.due_at,
        metadata_json=payload.metadata,
        created_by=current_user.id,
    )
    db.add(work_order)
    _create_history(
        db,
        event,
        current_user,
        action_type="WorkOrderIssued",
        status_from=status_from,
        status_to=event.status,
        comment=payload.instruction,
        metadata={"workOrderTitle": payload.title, "assigneeId": str(payload.assignee_id), "priority": payload.priority.value},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Action work order could not be created") from exc
    db.refresh(work_order)
    _publish_action_event("ActionWorkOrderCreated", work_order, event)
    return ok(_to_work_order_read(work_order))


@router.get(
    "/work-orders/{work_order_id}",
    response_model=ApiResponse[ActionWorkOrderRead],
    summary="작업 지시 상세 조회",
    description="작업 지시 상세 정보와 현재 처리 상태를 조회합니다.",
)
def get_work_order(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    return ok(_to_work_order_read(_load_work_order(db, work_order_id)))


@router.patch(
    "/work-orders/{work_order_id}",
    response_model=ApiResponse[ActionWorkOrderRead],
    summary="작업 지시 수정",
    description="담당자, 지시 내용, 우선순위, 목표일 또는 상태를 부분 수정합니다.",
)
def update_work_order(
    work_order_id: UUID,
    payload: ActionWorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    work_order = _load_work_order(db, work_order_id)
    event = _load_event_for_work_order(db, work_order)
    work_order_status_from = work_order.status
    event_status_from = event.status
    update_data = payload.model_dump(exclude_unset=True, by_alias=False)

    if payload.assignee_id is not None:
        assignee = db.get(User, payload.assignee_id)
        if assignee is None or assignee.status != "active":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found or inactive")
        event.assignee_id = payload.assignee_id

    for field, value in update_data.items():
        if isinstance(value, ActionWorkOrderStatus):
            value = value.value
        elif hasattr(value, "value"):
            value = value.value
        if field == "metadata":
            work_order.metadata_json = value or {}
        else:
            setattr(work_order, field, value)

    if payload.status is not None:
        if payload.status == ActionWorkOrderStatus.IN_PROGRESS and work_order.started_at is None:
            work_order.started_at = datetime.now(timezone.utc)
        if payload.status == ActionWorkOrderStatus.COMPLETED and work_order.completed_at is None:
            work_order.completed_at = datetime.now(timezone.utc)
        _sync_risk_event_status(event, payload.status.value)

    _create_history(
        db,
        event,
        current_user,
        action_type="WorkOrderUpdated",
        status_from=event_status_from,
        status_to=event.status,
        comment="작업 지시 정보 수정",
        metadata={
            "workOrderId": str(work_order.id),
            "workOrderStatusFrom": work_order_status_from,
            "workOrderStatusTo": work_order.status,
            "updatedFields": sorted(update_data.keys()),
        },
    )
    db.commit()
    db.refresh(work_order)
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_to_work_order_read(work_order))


@router.post(
    "/work-orders/{work_order_id}/assign",
    response_model=ApiResponse[ActionWorkOrderRead],
    summary="작업 담당자 지정",
    description="작업 지시 담당자를 지정/변경하고 연결된 RiskEvent의 assignee_id도 함께 갱신합니다.",
)
def assign_work_order(
    work_order_id: UUID,
    payload: ActionAssigneeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    work_order = _load_work_order(db, work_order_id)
    event = _load_event_for_work_order(db, work_order)
    assignee = db.get(User, payload.assignee_id)
    if assignee is None or assignee.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found or inactive")

    previous_assignee_id = work_order.assignee_id
    work_order.assignee_id = payload.assignee_id
    event.assignee_id = payload.assignee_id
    _create_history(
        db,
        event,
        current_user,
        "WorkOrderAssigned",
        event.status,
        event.status,
        payload.comment,
        metadata={
            "workOrderId": str(work_order.id),
            "previousAssigneeId": str(previous_assignee_id) if previous_assignee_id else None,
            "assigneeId": str(payload.assignee_id),
        },
    )
    db.commit()
    db.refresh(work_order)
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_to_work_order_read(work_order))


@router.post(
    "/work-orders/{work_order_id}/photos",
    response_model=ApiResponse[ActionWorkOrderRead],
    summary="현장 사진 첨부",
    description="현장 작업 사진 URL을 작업 지시에 누적 저장하고 ActionHistory에 사진 첨부 이력을 남깁니다.",
)
def attach_work_order_photos(
    work_order_id: UUID,
    payload: ActionPhotoAttachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    work_order = _load_work_order(db, work_order_id)
    event = _load_event_for_work_order(db, work_order)
    work_order.photo_urls = [*work_order.photo_urls, *payload.photo_urls]
    _create_history(
        db,
        event,
        current_user,
        "FieldPhotosAttached",
        event.status,
        event.status,
        payload.comment,
        photo_urls=payload.photo_urls,
        metadata={"workOrderId": str(work_order.id), **payload.metadata},
    )
    db.commit()
    db.refresh(work_order)
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_to_work_order_read(work_order))


@router.post(
    "/work-orders/{work_order_id}/status",
    response_model=ApiResponse[ActionWorkflowSummary],
    summary="작업 상태 변경",
    description="작업 지시 상태를 변경하고 InProgress/Completed/Closed 상태는 연결된 RiskEvent 상태와 동기화합니다.",
)
def change_work_order_status(
    work_order_id: UUID,
    payload: ActionStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    work_order = _load_work_order(db, work_order_id)
    event = _load_event_for_work_order(db, work_order)
    work_order_status_from = work_order.status
    event_status_from = event.status
    work_order.status = payload.status.value
    if payload.status == ActionWorkOrderStatus.IN_PROGRESS and work_order.started_at is None:
        work_order.started_at = datetime.now(timezone.utc)
    if payload.status == ActionWorkOrderStatus.COMPLETED and work_order.completed_at is None:
        work_order.completed_at = datetime.now(timezone.utc)
    _sync_risk_event_status(event, payload.status.value)
    _create_history(
        db,
        event,
        current_user,
        "WorkOrderStatusChanged",
        event_status_from,
        event.status,
        payload.comment,
        metadata={
            "workOrderId": str(work_order.id),
            "workOrderStatusFrom": work_order_status_from,
            "workOrderStatusTo": payload.status.value,
        },
    )
    db.commit()
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_workflow_summary(event, work_order))


@router.post(
    "/work-orders/{work_order_id}/acknowledge",
    response_model=ApiResponse[ActionWorkflowSummary],
    summary="작업 지시 확인",
    description="현장 담당자가 작업 지시를 확인하고 상태를 Acknowledged로 변경합니다.",
)
def acknowledge_work_order(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    work_order = _load_work_order(db, work_order_id)
    event = db.get(RiskEvent, work_order.risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    status_from = work_order.status
    work_order.status = ActionWorkOrderStatus.ACKNOWLEDGED.value
    _create_history(db, event, current_user, "WorkOrderAcknowledged", status_from, work_order.status, "작업 지시 확인")
    db.commit()
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_workflow_summary(event, work_order))


@router.post(
    "/work-orders/{work_order_id}/start",
    response_model=ApiResponse[ActionWorkflowSummary],
    summary="현장 작업 시작",
    description="현장 작업을 시작하고 작업 지시 및 위험 이벤트 상태를 InProgress로 전환합니다.",
)
def start_field_work(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    work_order = _load_work_order(db, work_order_id)
    event = db.get(RiskEvent, work_order.risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    status_from = event.status
    work_order.status = ActionWorkOrderStatus.IN_PROGRESS.value
    work_order.started_at = work_order.started_at or datetime.now(timezone.utc)
    event.status = "InProgress"
    _create_history(db, event, current_user, "FieldWorkStarted", status_from, event.status, "현장 작업 시작")
    db.commit()
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_workflow_summary(event, work_order))


@router.post(
    "/work-orders/{work_order_id}/field-report",
    response_model=ApiResponse[ActionWorkOrderRead],
    summary="현장 작업 보고",
    description="현장 작업 진행 내용과 사진을 기록하고 작업 상태를 InProgress로 유지합니다.",
)
def report_field_work(
    work_order_id: UUID,
    payload: FieldWorkReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    work_order = _load_work_order(db, work_order_id)
    event = db.get(RiskEvent, work_order.risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    status_from = event.status
    work_order.status = ActionWorkOrderStatus.IN_PROGRESS.value
    work_order.started_at = work_order.started_at or datetime.now(timezone.utc)
    work_order.photo_urls = [*work_order.photo_urls, *payload.photo_urls]
    event.status = "InProgress"
    _create_history(
        db,
        event,
        current_user,
        "FieldWorkReported",
        status_from,
        event.status,
        payload.comment,
        photo_urls=payload.photo_urls,
        metadata={"workOrderId": str(work_order.id), **payload.metadata},
    )
    db.commit()
    db.refresh(work_order)
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_to_work_order_read(work_order))


@router.post(
    "/work-orders/{work_order_id}/complete-report",
    response_model=ApiResponse[ActionWorkflowSummary],
    summary="완료 보고",
    description="완료 보고 내용과 사진을 저장하고 작업 지시를 Completed, 위험 이벤트를 Resolved로 전환합니다.",
)
def complete_field_work(
    work_order_id: UUID,
    payload: CompleteWorkReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    work_order = _load_work_order(db, work_order_id)
    event = db.get(RiskEvent, work_order.risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    status_from = event.status
    now = datetime.now(timezone.utc)
    work_order.status = ActionWorkOrderStatus.COMPLETED.value
    work_order.completed_at = now
    work_order.completion_summary = payload.summary
    work_order.photo_urls = [*work_order.photo_urls, *payload.photo_urls]
    work_order.metadata_json = {**work_order.metadata_json, **payload.metadata}
    event.status = "Resolved"
    event.resolved_at = now
    _create_history(
        db,
        event,
        current_user,
        "CompletionReported",
        status_from,
        event.status,
        payload.summary,
        photo_urls=payload.photo_urls,
        metadata={"workOrderId": str(work_order.id), **payload.metadata},
    )
    db.commit()
    _publish_action_event("ActionWorkOrderUpdated", work_order, event)
    return ok(_workflow_summary(event, work_order))


@router.post(
    "/work-orders/{work_order_id}/close",
    response_model=ApiResponse[ActionWorkflowSummary],
    summary="작업 및 위험 이벤트 종결",
    description="완료 보고 이후 작업 지시를 Closed로 전환하고 연결된 RiskEvent를 Closed 상태로 종료합니다.",
)
def close_work_order(
    work_order_id: UUID,
    payload: ActionWorkOrderCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    work_order = _load_work_order(db, work_order_id)
    event = _load_event_for_work_order(db, work_order)
    event_status_from = event.status
    work_order_status_from = work_order.status
    now = datetime.now(timezone.utc)

    work_order.status = ActionWorkOrderStatus.CLOSED.value
    work_order.completed_at = work_order.completed_at or now
    if payload.comment and not work_order.completion_summary:
        work_order.completion_summary = payload.comment
    work_order.metadata_json = {
        **work_order.metadata_json,
        "closeReport": {"comment": payload.comment, **payload.metadata},
    }
    event.status = "Closed"
    event.resolved_at = event.resolved_at or now

    _create_history(
        db,
        event,
        current_user,
        "RiskEventClosed",
        event_status_from,
        event.status,
        payload.comment,
        metadata={
            "workOrderId": str(work_order.id),
            "workOrderStatusFrom": work_order_status_from,
            "workOrderStatusTo": work_order.status,
            **payload.metadata,
        },
    )
    db.commit()
    _publish_action_event("ActionWorkOrderClosed", work_order, event)
    return ok(_workflow_summary(event, work_order))
