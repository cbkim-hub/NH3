from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RoleCode, require_roles
from app.core.response import ApiResponse, ok
from app.models.assets import Sensor
from app.models.iam import User
from app.schemas.sensors import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    SensorCreate,
    SensorListResponse,
    SensorRead,
    SensorStatus,
    SensorType,
    SensorUpdate,
)

router = APIRouter()


def _geometry_from_geojson(geometry: dict) -> object:
    if geometry.get("type") != "Point":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sensor geometry must be a GeoJSON Point")
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)


def _row_to_sensor_read(row) -> SensorRead:
    sensor: Sensor = row.Sensor
    geometry = json.loads(row.geometry) if row.geometry else {"type": "Point", "coordinates": []}
    return SensorRead(
        id=sensor.id,
        pipelineId=sensor.pipeline_id,
        sensorCode=sensor.sensor_code,
        name=sensor.name,
        sensorType=sensor.sensor_type,
        unit=sensor.unit,
        status=sensor.status,
        minValue=float(sensor.min_value) if sensor.min_value is not None else None,
        maxValue=float(sensor.max_value) if sensor.max_value is not None else None,
        lastSeenAt=sensor.last_seen_at,
        metadata=sensor.metadata_json,
        createdAt=sensor.created_at,
        updatedAt=sensor.updated_at,
        createdBy=sensor.created_by,
        geometry=geometry,
    )


def _to_feature(sensor: SensorRead) -> GeoJSONFeature:
    return GeoJSONFeature(
        id=str(sensor.id),
        geometry=sensor.geometry,
        properties=sensor.model_dump(by_alias=True, exclude={"geometry"}),
    )


def _sensor_query():
    return select(Sensor, func.ST_AsGeoJSON(Sensor.geom).label("geometry"))


@router.get(
    "",
    response_model=ApiResponse[SensorListResponse | GeoJSONFeatureCollection],
    summary="센서 목록 조회",
    description="센서 목록을 페이지네이션으로 조회합니다. 타입/상태/배관 ID 필터와 GeoJSON FeatureCollection 반환을 지원합니다.",
)
def list_sensors(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sensor_type: SensorType | None = Query(default=None, alias="sensorType"),
    sensor_status: SensorStatus | None = Query(default=None, alias="status"),
    pipeline_id: UUID | None = Query(default=None, alias="pipelineId"),
    response_format: Literal["json", "geojson"] = Query(default="json", alias="responseFormat"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    filters = []
    if sensor_type is not None:
        filters.append(Sensor.sensor_type == sensor_type.value)
    if sensor_status is not None:
        filters.append(Sensor.status == sensor_status.value)
    if pipeline_id is not None:
        filters.append(Sensor.pipeline_id == pipeline_id)

    total = db.scalar(select(func.count()).select_from(Sensor).where(*filters)) or 0
    rows = db.execute(
        _sensor_query().where(*filters).order_by(Sensor.created_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    items = [_row_to_sensor_read(row) for row in rows]
    if response_format == "geojson":
        return ok(GeoJSONFeatureCollection(features=[_to_feature(item) for item in items], total=total, page=page, size=size))
    return ok(SensorListResponse(items=items, total=total, page=page, size=size))


@router.post(
    "",
    response_model=ApiResponse[SensorRead],
    status_code=status.HTTP_201_CREATED,
    summary="센서 등록",
    description="GeoJSON Point geometry와 센서 타입/상태 정보를 포함해 신규 센서를 등록합니다.",
)
def create_sensor(
    payload: SensorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER)),
):
    sensor = Sensor(
        pipeline_id=payload.pipeline_id,
        sensor_code=payload.sensor_code,
        name=payload.name,
        sensor_type=payload.sensor_type.value,
        unit=payload.unit,
        status=payload.status.value,
        min_value=payload.min_value,
        max_value=payload.max_value,
        metadata_json=payload.metadata_json,
        geom=_geometry_from_geojson(payload.geometry),
        created_by=current_user.id,
    )
    db.add(sensor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sensor code already exists or pipeline is invalid") from exc
    row = db.execute(_sensor_query().where(Sensor.id == sensor.id)).one()
    return ok(_row_to_sensor_read(row))


@router.get(
    "/{sensor_id}",
    response_model=ApiResponse[SensorRead | GeoJSONFeature],
    summary="센서 상세 조회",
    description="센서 상세 정보를 조회합니다. `responseFormat=geojson`을 지정하면 GeoJSON Feature로 반환합니다.",
)
def get_sensor(
    sensor_id: UUID,
    response_format: Literal["json", "geojson"] = Query(default="json", alias="responseFormat"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    row = db.execute(_sensor_query().where(Sensor.id == sensor_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    item = _row_to_sensor_read(row)
    if response_format == "geojson":
        return ok(_to_feature(item))
    return ok(item)


@router.patch(
    "/{sensor_id}",
    response_model=ApiResponse[SensorRead],
    summary="센서 수정",
    description="센서 속성, 상태 또는 GeoJSON Point geometry를 부분 수정합니다.",
)
def update_sensor(
    sensor_id: UUID,
    payload: SensorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER)),
):
    sensor = db.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")

    update_data = payload.model_dump(exclude_unset=True, by_alias=False)
    geometry = update_data.pop("geometry", None)
    for field, value in update_data.items():
        if isinstance(value, (SensorType, SensorStatus)):
            value = value.value
        setattr(sensor, field, value)
    if geometry is not None:
        sensor.geom = _geometry_from_geojson(geometry)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sensor code already exists or pipeline is invalid") from exc
    row = db.execute(_sensor_query().where(Sensor.id == sensor_id)).one()
    return ok(_row_to_sensor_read(row))


@router.delete(
    "/{sensor_id}",
    response_model=ApiResponse[dict[str, str]],
    summary="센서 삭제",
    description="센서를 삭제합니다. 연결된 SensorData는 DB FK 정책에 따라 cascade 삭제됩니다.",
)
def delete_sensor(
    sensor_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN)),
):
    sensor = db.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    db.delete(sensor)
    db.commit()
    return ok({"message": "Sensor deleted"})
