from uuid import UUID

from pydantic import BaseModel


class PipelineRead(BaseModel):
    id: UUID
    code: str
    name: str
    pipeline_type: str
    risk_grade: str | None = None


class SensorRead(BaseModel):
    id: UUID
    sensor_code: str
    name: str
    sensor_type: str
    unit: str
    status: str
    last_seen_at: str | None = None
