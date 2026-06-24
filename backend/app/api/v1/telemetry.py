from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RoleCode, require_roles
from app.core.response import ApiResponse, ok
from app.core.websocket import dashboard_ws_manager
from app.models.assets import Sensor
from app.models.iam import User
from app.models.telemetry import SensorData
from app.schemas.telemetry import SensorDataCreate, SensorDataRead

router = APIRouter()


def _to_sensor_data_read(row: SensorData) -> SensorDataRead:
    return SensorDataRead(
        id=row.id,
        sensorId=row.sensor_id,
        measuredAt=row.measured_at,
        receivedAt=row.received_at,
        value=float(row.value),
        unit=row.unit,
        quality=row.quality,
        rawPayload=row.raw_payload,
        createdAt=row.created_at,
        createdBy=row.created_by,
    )


@router.post(
    "/sensor-data",
    response_model=ApiResponse[SensorDataRead],
    status_code=status.HTTP_201_CREATED,
    summary="SensorData 수신",
    description="센서 측정 데이터를 저장하고 Dashboard WebSocket으로 SensorDataReceived 이벤트를 전파합니다.",
)
def ingest_sensor_data(
    payload: SensorDataCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    sensor = db.get(Sensor, payload.sensor_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")

    received_at = datetime.now(timezone.utc)
    row = SensorData(
        sensor_id=payload.sensor_id,
        measured_at=payload.measured_at,
        received_at=received_at,
        value=payload.value,
        unit=payload.unit,
        quality=payload.quality,
        raw_payload=payload.raw_payload,
        created_by=current_user.id,
    )
    sensor.last_seen_at = received_at
    db.add(row)
    db.commit()
    db.refresh(row)

    dashboard_ws_manager.publish(
        "SensorDataReceived",
        {
            "sensorId": str(row.sensor_id),
            "sensorCode": sensor.sensor_code,
            "sensorType": sensor.sensor_type,
            "pipelineId": str(sensor.pipeline_id) if sensor.pipeline_id else None,
            "value": float(row.value),
            "unit": row.unit,
            "measuredAt": row.measured_at.isoformat(),
            "receivedAt": row.received_at.isoformat(),
        },
    )
    return ok(_to_sensor_data_read(row))
