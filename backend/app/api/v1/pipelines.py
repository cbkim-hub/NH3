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
from app.models.assets import Pipeline
from app.models.iam import User
from app.schemas.pipelines import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    PipelineCreate,
    PipelineListResponse,
    PipelineRead,
    PipelineUpdate,
)

router = APIRouter()


def _geometry_from_geojson(geometry: dict) -> object:
    if geometry.get("type") != "LineString":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pipeline geometry must be a GeoJSON LineString")
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)


def _row_to_pipeline_read(row) -> PipelineRead:
    pipeline: Pipeline = row.Pipeline
    geometry = json.loads(row.geometry) if row.geometry else {"type": "LineString", "coordinates": []}
    return PipelineRead(
        id=pipeline.id,
        organizationId=pipeline.organization_id,
        code=pipeline.code,
        name=pipeline.name,
        pipelineType=pipeline.pipeline_type,
        material=pipeline.material,
        diameterMm=float(pipeline.diameter_mm) if pipeline.diameter_mm is not None else None,
        depthM=float(pipeline.depth_m) if pipeline.depth_m is not None else None,
        lengthM=float(pipeline.length_m) if pipeline.length_m is not None else None,
        riskGrade=pipeline.risk_grade,
        installedAt=pipeline.installed_at,
        properties=pipeline.properties,
        createdAt=pipeline.created_at,
        updatedAt=pipeline.updated_at,
        createdBy=pipeline.created_by,
        geometry=geometry,
    )


def _to_feature(pipeline: PipelineRead) -> GeoJSONFeature:
    return GeoJSONFeature(
        id=str(pipeline.id),
        geometry=pipeline.geometry,
        properties=pipeline.model_dump(by_alias=True, exclude={"geometry"}),
    )


def _pipeline_query():
    return select(Pipeline, func.ST_AsGeoJSON(Pipeline.geom).label("geometry"))


@router.get(
    "",
    response_model=ApiResponse[PipelineListResponse | GeoJSONFeatureCollection],
    summary="배관 목록 조회",
    description="배관 목록을 페이지네이션으로 조회합니다. `responseFormat=geojson`을 지정하면 GeoJSON FeatureCollection으로 반환합니다.",
)
def list_pipelines(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    response_format: Literal["json", "geojson"] = Query(default="json", alias="responseFormat"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    total = db.scalar(select(func.count()).select_from(Pipeline)) or 0
    rows = db.execute(
        _pipeline_query().order_by(Pipeline.created_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    items = [_row_to_pipeline_read(row) for row in rows]
    if response_format == "geojson":
        return ok(GeoJSONFeatureCollection(features=[_to_feature(item) for item in items], total=total, page=page, size=size))
    return ok(PipelineListResponse(items=items, total=total, page=page, size=size))


@router.post(
    "",
    response_model=ApiResponse[PipelineRead],
    status_code=status.HTTP_201_CREATED,
    summary="배관 등록",
    description="GeoJSON LineString geometry를 포함해 신규 배관을 등록합니다.",
)
def create_pipeline(
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER)),
):
    pipeline = Pipeline(
        organization_id=payload.organization_id,
        code=payload.code,
        name=payload.name,
        pipeline_type=payload.pipeline_type,
        material=payload.material,
        diameter_mm=payload.diameter_mm,
        depth_m=payload.depth_m,
        length_m=payload.length_m,
        risk_grade=payload.risk_grade,
        installed_at=payload.installed_at,
        properties=payload.properties,
        geom=_geometry_from_geojson(payload.geometry),
        created_by=current_user.id,
    )
    db.add(pipeline)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pipeline code already exists") from exc
    row = db.execute(_pipeline_query().where(Pipeline.id == pipeline.id)).one()
    return ok(_row_to_pipeline_read(row))


@router.get(
    "/{pipeline_id}",
    response_model=ApiResponse[PipelineRead | GeoJSONFeature],
    summary="배관 상세 조회",
    description="배관 상세 정보를 조회합니다. `responseFormat=geojson`을 지정하면 GeoJSON Feature로 반환합니다.",
)
def get_pipeline(
    pipeline_id: UUID,
    response_format: Literal["json", "geojson"] = Query(default="json", alias="responseFormat"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    row = db.execute(_pipeline_query().where(Pipeline.id == pipeline_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    item = _row_to_pipeline_read(row)
    if response_format == "geojson":
        return ok(_to_feature(item))
    return ok(item)


@router.patch(
    "/{pipeline_id}",
    response_model=ApiResponse[PipelineRead],
    summary="배관 수정",
    description="배관 속성 또는 GeoJSON LineString geometry를 부분 수정합니다.",
)
def update_pipeline(
    pipeline_id: UUID,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER)),
):
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    update_data = payload.model_dump(exclude_unset=True, by_alias=False)
    geometry = update_data.pop("geometry", None)
    for field, value in update_data.items():
        setattr(pipeline, field, value)
    if geometry is not None:
        pipeline.geom = _geometry_from_geojson(geometry)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pipeline code already exists") from exc
    row = db.execute(_pipeline_query().where(Pipeline.id == pipeline_id)).one()
    return ok(_row_to_pipeline_read(row))


@router.delete(
    "/{pipeline_id}",
    response_model=ApiResponse[dict[str, str]],
    summary="배관 삭제",
    description="배관을 삭제합니다. 연결된 PipelineImage는 cascade 삭제되며 Sensor는 DB FK 정책에 따라 pipeline_id가 NULL 처리됩니다.",
)
def delete_pipeline(
    pipeline_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN)),
):
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    db.delete(pipeline)
    db.commit()
    return ok({"message": "Pipeline deleted"})
