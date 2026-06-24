from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RoleCode, require_roles
from app.core.response import ApiResponse, ok
from app.models.iam import User
from app.models.monitoring import AIAnalysis
from app.schemas.ai_analysis import AIAnalysisRead, AIAnalysisRunRequest, AIAnalysisRunResponse
from app.services.ai_analysis_service import AIAnalysisService

router = APIRouter()


@router.post(
    "/run",
    response_model=ApiResponse[AIAnalysisRunResponse],
    status_code=status.HTTP_201_CREATED,
    summary="AI 센서 융합 분석 실행",
    description=(
        "최근 SensorData를 분석해 Pressure 급감, Vibration 증가, Leakage 감지 신호를 융합하고 "
        "Risk Score가 임계값 이상이면 AIAnalysis와 RiskEvent를 함께 생성합니다."
    ),
)
def run_ai_analysis(
    payload: AIAnalysisRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR)),
):
    result = AIAnalysisService(db).run_sensor_fusion_analysis(
        current_user=current_user,
        pipeline_id=payload.pipeline_id,
        window_minutes=payload.window_minutes,
        create_risk_event=payload.create_risk_event,
        risk_event_threshold=payload.risk_event_threshold,
    )
    return ok(result)


@router.get(
    "/recent",
    response_model=ApiResponse[list[AIAnalysisRead]],
    summary="최근 AI 분석 목록",
    description="Dashboard AI 위험도 패널에서 사용할 최근 AIAnalysis 결과를 반환합니다.",
)
def recent_ai_analyses(
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    analyses = db.scalars(select(AIAnalysis).order_by(AIAnalysis.created_at.desc()).limit(limit)).all()
    service = AIAnalysisService(db)
    return ok([service.to_read(analysis) for analysis in analyses])


@router.get(
    "/{analysis_id}",
    response_model=ApiResponse[AIAnalysisRead],
    summary="AI 분석 상세 조회",
    description="AIAnalysis 결과와 evidence를 조회합니다.",
)
def get_ai_analysis(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.OPERATOR, RoleCode.FIELD_WORKER)),
):
    analysis = db.get(AIAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI analysis not found")
    return ok(AIAnalysisService(db).to_read(analysis))
