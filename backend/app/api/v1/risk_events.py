from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RoleCode, require_roles
from app.core.response import ApiResponse, ok
from app.core.websocket import dashboard_ws_manager
from app.models.iam import User
from app.models.monitoring import ActionHistory, RiskEvent
from app.schemas.risk_events import (
    ActionHistoryCreate,
    ActionHistoryRead,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    RiskEventAssignRequest,
    RiskEventCompleteRequest,
    RiskEventCreate,
    RiskEventListResponse,
    RiskEventRead,
    RiskEventStats,
    RiskEventStatus,
    RiskEventUpdate,
    RiskSeverity,
    RiskSeverityAggregate,
)

router = APIRouter()

SORTABLE_COLUMNS = {
    "detectedAt": RiskEvent.detected_at,
    "createdAt": RiskEvent.created_at,
    "riskScore": RiskEvent.risk_score,
    "severity": RiskEvent.severity,
    "status": RiskEvent.status,
}


def _location_from_geojson(location: dict | None) -> object | None:
    if location is None:
        return None
    if location.get("type") != "Point":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Risk event location must be a GeoJSON Point")
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(location)), 4326)


def _risk_event_query():
    return select(RiskEvent, func.ST_AsGeoJSON(RiskEvent.location).label("location_geojson"))


def _row_to_risk_event_read(row) -> RiskEventRead:
    event: RiskEvent = row.RiskEvent
    location = json.loads(row.location_geojson) if row.location_geojson else None
    return RiskEventRead(
        id=event.id,
        eventCode=event.event_code,
        title=event.title,
        description=event.description,
        pipelineId=event.pipeline_id,
        sensorId=event.sensor_id,
        assigneeId=event.assignee_id,
        severity=event.severity,
        riskScore=float(event.risk_score),
        status=event.status,
        location=location,
        detectedAt=event.detected_at,
        resolvedAt=event.resolved_at,
        evidence=event.evidence,
        createdAt=event.created_at,
        updatedAt=event.updated_at,
        createdBy=event.created_by,
    )


def _to_feature(event: RiskEventRead) -> GeoJSONFeature:
    return GeoJSONFeature(
        id=str(event.id),
        geometry=event.location,
        properties=event.model_dump(by_alias=True, exclude={"location"}),
    )


def _build_filters(
    severity: RiskSeverity | None,
    event_status: RiskEventStatus | None,
    pipeline_id: UUID | None,
    sensor_id: UUID | None,
    detected_from: datetime | None,
    detected_to: datetime | None,
) -> list:
    filters = []
    if severity is not None:
        filters.append(RiskEvent.severity == severity.value)
    if event_status is not None:
        filters.append(RiskEvent.status == event_status.value)
    if pipeline_id is not None:
        filters.append(RiskEvent.pipeline_id == pipeline_id)
    if sensor_id is not None:
        filters.append(RiskEvent.sensor_id == sensor_id)
    if detected_from is not None:
        filters.append(RiskEvent.detected_at >= detected_from)
    if detected_to is not None:
        filters.append(RiskEvent.detected_at <= detected_to)
    return filters


@router.get(
    "/stats",
    response_model=ApiResponse[RiskEventStats],
    summary="위험 이벤트 통계",
    description="Dashboard KPI에서 사용할 위험 이벤트 상태/등급/평균 위험도 통계를 반환합니다.",
)
def risk_event_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    rows = db.execute(select(RiskEvent.status, RiskEvent.severity, RiskEvent.risk_score)).all()
    total = len(rows)
    status_counts = {status.value: 0 for status in RiskEventStatus}
    severity_counts = {severity.value: 0 for severity in RiskSeverity}
    risk_sum = 0.0
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
        risk_sum += float(row.risk_score)
    return ok(
        RiskEventStats(
            total=total,
            open=status_counts[RiskEventStatus.OPEN.value],
            investigating=status_counts[RiskEventStatus.INVESTIGATING.value],
            inProgress=status_counts[RiskEventStatus.IN_PROGRESS.value],
            resolved=status_counts[RiskEventStatus.RESOLVED.value],
            closed=status_counts[RiskEventStatus.CLOSED.value],
            critical=severity_counts[RiskSeverity.CRITICAL.value],
            high=severity_counts[RiskSeverity.HIGH.value],
            averageRiskScore=round(risk_sum / total, 2) if total else 0.0,
        )
    )


@router.get(
    "/recent",
    response_model=ApiResponse[list[RiskEventRead]],
    summary="최근 위험 이벤트",
    description="Dashboard 실시간 이벤트 패널에서 사용할 최근 위험 이벤트 목록을 반환합니다.",
)
def recent_risk_events(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    rows = db.execute(_risk_event_query().order_by(RiskEvent.detected_at.desc()).limit(limit)).all()
    return ok([_row_to_risk_event_read(row) for row in rows])


@router.get(
    "/by-severity",
    response_model=ApiResponse[list[RiskSeverityAggregate]],
    summary="위험등급별 집계",
    description="위험등급별 이벤트 수와 평균 위험 점수를 집계합니다.",
)
def risk_events_by_severity(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    rows = db.execute(
        select(RiskEvent.severity, func.count(RiskEvent.id), func.avg(RiskEvent.risk_score)).group_by(RiskEvent.severity)
    ).all()
    return ok(
        [
            RiskSeverityAggregate(
                severity=row.severity,
                count=row[1],
                averageRiskScore=round(float(row[2] or 0), 2),
            )
            for row in rows
        ]
    )


@router.get(
    "",
    response_model=ApiResponse[RiskEventListResponse | GeoJSONFeatureCollection],
    summary="위험 이벤트 목록 조회",
    description="위험 이벤트를 페이지네이션, 필터링, 정렬로 조회합니다. `responseFormat=geojson`을 지정하면 GeoJSON FeatureCollection으로 반환합니다.",
)
def list_risk_events(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    severity: RiskSeverity | None = None,
    event_status: RiskEventStatus | None = Query(default=None, alias="status"),
    pipeline_id: UUID | None = Query(default=None, alias="pipelineId"),
    sensor_id: UUID | None = Query(default=None, alias="sensorId"),
    detected_from: datetime | None = Query(default=None, alias="detectedFrom"),
    detected_to: datetime | None = Query(default=None, alias="detectedTo"),
    sort_by: Literal["detectedAt", "createdAt", "riskScore", "severity", "status"] = Query(default="detectedAt", alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
    response_format: Literal["json", "geojson"] = Query(default="json", alias="responseFormat"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    filters = _build_filters(severity, event_status, pipeline_id, sensor_id, detected_from, detected_to)
    total = db.scalar(select(func.count()).select_from(RiskEvent).where(*filters)) or 0
    sort_column = SORTABLE_COLUMNS[sort_by]
    order_clause = asc(sort_column) if sort_order == "asc" else desc(sort_column)
    rows = db.execute(
        _risk_event_query().where(*filters).order_by(order_clause).offset((page - 1) * size).limit(size)
    ).all()
    items = [_row_to_risk_event_read(row) for row in rows]
    if response_format == "geojson":
        return ok(GeoJSONFeatureCollection(features=[_to_feature(item) for item in items], total=total, page=page, size=size))
    return ok(RiskEventListResponse(items=items, total=total, page=page, size=size))


@router.post(
    "",
    response_model=ApiResponse[RiskEventRead],
    status_code=status.HTTP_201_CREATED,
    summary="위험 이벤트 등록",
    description="위험 이벤트와 GeoJSON Point location을 등록합니다.",
)
def create_risk_event(
    payload: RiskEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    event = RiskEvent(
        event_code=payload.event_code,
        title=payload.title,
        description=payload.description,
        pipeline_id=payload.pipeline_id,
        sensor_id=payload.sensor_id,
        assignee_id=payload.assignee_id,
        severity=payload.severity.value,
        risk_score=payload.risk_score,
        status=payload.status.value,
        location=_location_from_geojson(payload.location),
        detected_at=payload.detected_at,
        resolved_at=payload.resolved_at,
        evidence=payload.evidence,
        created_by=current_user.id,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Risk event code already exists or related asset is invalid") from exc
    row = db.execute(_risk_event_query().where(RiskEvent.id == event.id)).one()
    item = _row_to_risk_event_read(row)
    dashboard_ws_manager.publish(
        "RiskEventCreated",
        {
            "riskEventId": str(item.id),
            "eventCode": item.event_code,
            "title": item.title,
            "severity": item.severity,
            "riskScore": item.risk_score,
            "status": item.status,
            "pipelineId": str(item.pipeline_id) if item.pipeline_id else None,
            "sensorId": str(item.sensor_id) if item.sensor_id else None,
            "detectedAt": item.detected_at.isoformat(),
        },
    )
    return ok(item)


def _create_action_history(
    db: Session,
    event: RiskEvent,
    actor: User,
    action_type: str,
    status_from: str | None = None,
    status_to: str | None = None,
    comment: str | None = None,
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


def _to_action_history_read(history: ActionHistory) -> ActionHistoryRead:
    return ActionHistoryRead(
        id=history.id,
        riskEventId=history.risk_event_id,
        actorId=history.actor_id,
        actionType=history.action_type,
        statusFrom=history.status_from,
        statusTo=history.status_to,
        comment=history.comment,
        actionAt=history.action_at,
        metadata=history.metadata_json,
        photoUrls=history.photo_urls,
        createdAt=history.created_at,
        createdBy=history.created_by,
    )


@router.get(
    "/{risk_event_id}/actions",
    response_model=ApiResponse[list[ActionHistoryRead]],
    summary="위험 이벤트 조치 이력 조회",
    description="위험 이벤트에 등록된 담당자 배정, 조치, 완료 이력을 시간순으로 조회합니다.",
)
def list_action_histories(
    risk_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    if db.get(RiskEvent, risk_event_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    histories = db.scalars(
        select(ActionHistory).where(ActionHistory.risk_event_id == risk_event_id).order_by(ActionHistory.action_at.asc())
    ).all()
    return ok([_to_action_history_read(history) for history in histories])


@router.post(
    "/{risk_event_id}/assign",
    response_model=ApiResponse[RiskEventRead],
    summary="위험 이벤트 담당자 배정",
    description="위험 이벤트 담당자를 배정하고 ActionHistory에 배정 이력을 기록합니다.",
)
def assign_risk_event(
    risk_event_id: UUID,
    payload: RiskEventAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER)),
):
    event = db.get(RiskEvent, risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    assignee = db.get(User, payload.assignee_id)
    if assignee is None or assignee.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found or inactive")
    status_from = event.status
    event.assignee_id = payload.assignee_id
    if event.status == RiskEventStatus.OPEN.value:
        event.status = RiskEventStatus.INVESTIGATING.value
    _create_action_history(
        db,
        event,
        current_user,
        action_type="Assign",
        status_from=status_from,
        status_to=event.status,
        comment=payload.comment,
        metadata={"assigneeId": str(payload.assignee_id)},
    )
    db.commit()
    row = db.execute(_risk_event_query().where(RiskEvent.id == risk_event_id)).one()
    return ok(_row_to_risk_event_read(row))


@router.post(
    "/{risk_event_id}/actions",
    response_model=ApiResponse[ActionHistoryRead],
    status_code=status.HTTP_201_CREATED,
    summary="위험 이벤트 조치 이력 등록",
    description="현장 조치 내용과 사진 URL을 ActionHistory에 등록하고 선택적으로 이벤트 상태를 변경합니다.",
)
def create_action_history(
    risk_event_id: UUID,
    payload: ActionHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    event = db.get(RiskEvent, risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    status_from = event.status
    status_to = payload.status_to.value if payload.status_to else event.status
    if payload.status_to:
        event.status = payload.status_to.value
    history = _create_action_history(
        db,
        event,
        current_user,
        action_type=payload.action_type,
        status_from=status_from,
        status_to=status_to,
        comment=payload.comment,
        photo_urls=payload.photo_urls,
        metadata=payload.metadata,
    )
    db.commit()
    db.refresh(history)
    return ok(_to_action_history_read(history))


@router.post(
    "/{risk_event_id}/complete",
    response_model=ApiResponse[RiskEventRead],
    summary="위험 이벤트 완료 처리",
    description="위험 이벤트를 Resolved 상태로 변경하고 완료 메모/사진을 조치 이력에 남깁니다.",
)
def complete_risk_event(
    risk_event_id: UUID,
    payload: RiskEventCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    event = db.get(RiskEvent, risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    status_from = event.status
    event.status = RiskEventStatus.RESOLVED.value
    event.resolved_at = datetime.now(timezone.utc)
    _create_action_history(
        db,
        event,
        current_user,
        action_type="Complete",
        status_from=status_from,
        status_to=event.status,
        comment=payload.comment,
        photo_urls=payload.photo_urls,
    )
    db.commit()
    row = db.execute(_risk_event_query().where(RiskEvent.id == risk_event_id)).one()
    return ok(_row_to_risk_event_read(row))


@router.get(
    "/{risk_event_id}",
    response_model=ApiResponse[RiskEventRead | GeoJSONFeature],
    summary="위험 이벤트 상세 조회",
    description="위험 이벤트 상세 정보를 조회합니다. `responseFormat=geojson`을 지정하면 GeoJSON Feature로 반환합니다.",
)
def get_risk_event(
    risk_event_id: UUID,
    response_format: Literal["json", "geojson"] = Query(default="json", alias="responseFormat"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    row = db.execute(_risk_event_query().where(RiskEvent.id == risk_event_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    item = _row_to_risk_event_read(row)
    if response_format == "geojson":
        return ok(_to_feature(item))
    return ok(item)


@router.patch(
    "/{risk_event_id}",
    response_model=ApiResponse[RiskEventRead],
    summary="위험 이벤트 수정",
    description="위험 이벤트의 상태, 등급, 위치, 연관 자산 또는 설명을 부분 수정합니다.",
)
def update_risk_event(
    risk_event_id: UUID,
    payload: RiskEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    event = db.get(RiskEvent, risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")

    update_data = payload.model_dump(exclude_unset=True, by_alias=False)
    location = update_data.pop("location", None)
    for field, value in update_data.items():
        if isinstance(value, (RiskSeverity, RiskEventStatus)):
            value = value.value
        setattr(event, field, value)
    if location is not None:
        event.location = _location_from_geojson(location)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Risk event code already exists or related asset is invalid") from exc
    row = db.execute(_risk_event_query().where(RiskEvent.id == risk_event_id)).one()
    return ok(_row_to_risk_event_read(row))


@router.delete(
    "/{risk_event_id}",
    response_model=ApiResponse[dict[str, str]],
    summary="위험 이벤트 삭제",
    description="위험 이벤트를 삭제합니다. 연결된 Notification/ActionHistory는 cascade 삭제됩니다.",
)
def delete_risk_event(
    risk_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN)),
):
    event = db.get(RiskEvent, risk_event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk event not found")
    db.delete(event)
    db.commit()
    return ok({"message": "Risk event deleted"})
