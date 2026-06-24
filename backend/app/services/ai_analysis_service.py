from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assets import Sensor
from app.models.iam import User
from app.models.monitoring import AIAnalysis, RiskEvent
from app.models.telemetry import SensorData
from app.core.websocket import dashboard_ws_manager
from app.schemas.ai_analysis import AIAnalysisRead, AIAnalysisRunResponse, AISignalEvidence, AISeverity

MODEL_NAME = "pipeline-risk-rule-engine"
MODEL_VERSION = "mvp-1.0"
ANALYSIS_TYPE = "SensorFusionRiskDetection"


class AIAnalysisService:
    def __init__(self, db: Session):
        self.db = db

    def run_sensor_fusion_analysis(
        self,
        current_user: User,
        pipeline_id=None,
        window_minutes: int = 15,
        create_risk_event: bool = True,
        risk_event_threshold: float = 75,
    ) -> AIAnalysisRunResponse:
        started_at = datetime.now(timezone.utc)
        since = started_at - timedelta(minutes=window_minutes)
        rows = self._load_sensor_rows(since, pipeline_id)
        grouped = self._group_by_sensor_type(rows)
        evidence = self._build_evidence(grouped, window_minutes)
        risk_score = self._calculate_risk_score(evidence)
        severity = self._severity_for_score(risk_score)
        trigger_sensor = self._select_trigger_sensor(grouped)

        analysis = AIAnalysis(
            pipeline_id=pipeline_id or (trigger_sensor.pipeline_id if trigger_sensor else None),
            sensor_id=trigger_sensor.id if trigger_sensor else None,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            analysis_type=ANALYSIS_TYPE,
            risk_score=risk_score,
            severity=severity.value,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            evidence={
                "signals": {name: signal.model_dump(by_alias=True) for name, signal in evidence.items()},
                "windowMinutes": window_minutes,
                "rule": "Pressure 급감 + Vibration 증가 + Leakage 감지 시 Critical RiskEvent 생성",
            },
            created_by=current_user.id,
        )
        self.db.add(analysis)
        self.db.flush()

        risk_event = None
        if create_risk_event and risk_score >= risk_event_threshold:
            risk_event = self._create_risk_event(analysis, trigger_sensor, risk_score, severity, current_user)

        self.db.commit()
        self.db.refresh(analysis)
        if risk_event is not None:
            self.db.refresh(risk_event)

        dashboard_ws_manager.publish(
            "AIAnalysisCompleted",
            {
                "analysisId": str(analysis.id),
                "pipelineId": str(analysis.pipeline_id) if analysis.pipeline_id else None,
                "sensorId": str(analysis.sensor_id) if analysis.sensor_id else None,
                "riskScore": float(analysis.risk_score),
                "severity": analysis.severity,
                "riskEventId": str(risk_event.id) if risk_event else None,
                "riskEventCreated": risk_event is not None,
                "endedAt": analysis.ended_at.isoformat() if analysis.ended_at else None,
            },
        )
        if risk_event is not None:
            dashboard_ws_manager.publish(
                "RiskEventCreated",
                {
                    "riskEventId": str(risk_event.id),
                    "eventCode": risk_event.event_code,
                    "title": risk_event.title,
                    "severity": risk_event.severity,
                    "riskScore": float(risk_event.risk_score),
                    "status": risk_event.status,
                    "pipelineId": str(risk_event.pipeline_id) if risk_event.pipeline_id else None,
                    "sensorId": str(risk_event.sensor_id) if risk_event.sensor_id else None,
                    "detectedAt": risk_event.detected_at.isoformat(),
                },
            )

        return AIAnalysisRunResponse(
            analysis=self.to_read(analysis),
            riskEventId=risk_event.id if risk_event else None,
            riskEventCreated=risk_event is not None,
            decision=self._decision_message(risk_score, severity, bool(risk_event)),
        )

    def _load_sensor_rows(self, since: datetime, pipeline_id) -> list[tuple[Sensor, SensorData]]:
        stmt = select(Sensor, SensorData).join(SensorData, SensorData.sensor_id == Sensor.id).where(SensorData.measured_at >= since)
        if pipeline_id is not None:
            stmt = stmt.where(Sensor.pipeline_id == pipeline_id)
        return list(self.db.execute(stmt.order_by(Sensor.sensor_type.asc(), SensorData.measured_at.asc())).all())

    def _group_by_sensor_type(self, rows: list[tuple[Sensor, SensorData]]) -> dict[str, list[tuple[Sensor, SensorData]]]:
        grouped: dict[str, list[tuple[Sensor, SensorData]]] = defaultdict(list)
        for sensor, data in rows:
            grouped[sensor.sensor_type].append((sensor, data))
        return grouped

    def _build_evidence(self, grouped: dict[str, list[tuple[Sensor, SensorData]]], window_minutes: int) -> dict[str, AISignalEvidence]:
        return {
            "pressureDrop": self._pressure_drop_signal(grouped.get("Pressure", [])),
            "vibrationIncrease": self._vibration_increase_signal(grouped.get("Vibration", [])),
            "leakageDetected": self._leakage_signal(grouped.get("Leakage", [])),
            "dataCoverage": AISignalEvidence(
                detected=bool(grouped),
                scoreContribution=10 if grouped else 0,
                reason=f"최근 {window_minutes}분 센서 데이터 {'수신' if grouped else '미수신'}",
            ),
        }

    def _pressure_drop_signal(self, points: list[tuple[Sensor, SensorData]]) -> AISignalEvidence:
        if not points:
            return AISignalEvidence(detected=False, scoreContribution=0, reason="Pressure 센서 데이터 없음")
        latest = float(points[-1][1].value)
        previous_values = [float(data.value) for _, data in points[:-1]]
        baseline = mean(previous_values) if previous_values else self._metadata_float(points[-1][0], "baselinePressure", latest)
        change_percent = ((latest - baseline) / baseline * 100) if baseline else 0
        threshold = -abs(self._metadata_float(points[-1][0], "pressureDropPercentThreshold", 20))
        detected = change_percent <= threshold
        return AISignalEvidence(
            detected=detected,
            scoreContribution=32 if detected else 0,
            latestValue=latest,
            baselineValue=round(baseline, 4),
            changePercent=round(change_percent, 2),
            reason="Pressure 급감 감지" if detected else "Pressure 급감 기준 미충족",
        )

    def _vibration_increase_signal(self, points: list[tuple[Sensor, SensorData]]) -> AISignalEvidence:
        if not points:
            return AISignalEvidence(detected=False, scoreContribution=0, reason="Vibration 센서 데이터 없음")
        latest = float(points[-1][1].value)
        previous_values = [float(data.value) for _, data in points[:-1]]
        baseline = mean(previous_values) if previous_values else self._metadata_float(points[-1][0], "baselineVibration", 0)
        threshold = self._metadata_float(points[-1][0], "vibrationThreshold", 7)
        change_percent = ((latest - baseline) / baseline * 100) if baseline else None
        detected = latest >= threshold or (change_percent is not None and change_percent >= 50)
        return AISignalEvidence(
            detected=detected,
            scoreContribution=25 if detected else 0,
            latestValue=latest,
            baselineValue=round(baseline, 4),
            changePercent=round(change_percent, 2) if change_percent is not None else None,
            reason="Vibration 증가 감지" if detected else "Vibration 증가 기준 미충족",
        )

    def _leakage_signal(self, points: list[tuple[Sensor, SensorData]]) -> AISignalEvidence:
        if not points:
            return AISignalEvidence(detected=False, scoreContribution=0, reason="Leakage 센서 데이터 없음")
        latest_sensor, latest_data = points[-1]
        latest = float(latest_data.value)
        threshold = self._metadata_float(latest_sensor, "leakageThreshold", 0)
        raw_payload = latest_data.raw_payload or {}
        detected = latest > threshold or bool(raw_payload.get("detected"))
        return AISignalEvidence(
            detected=detected,
            scoreContribution=25 if detected else 0,
            latestValue=latest,
            baselineValue=threshold,
            changePercent=None,
            reason="Leakage 감지" if detected else "Leakage 감지 기준 미충족",
        )

    def _metadata_float(self, sensor: Sensor, key: str, default: float) -> float:
        try:
            return float((sensor.metadata_json or {}).get(key, default))
        except (TypeError, ValueError):
            return default

    def _calculate_risk_score(self, evidence: dict[str, AISignalEvidence]) -> float:
        score = sum(signal.score_contribution for signal in evidence.values())
        return round(min(score, 100), 2)

    def _severity_for_score(self, risk_score: float) -> AISeverity:
        if risk_score >= 90:
            return AISeverity.CRITICAL
        if risk_score >= 75:
            return AISeverity.HIGH
        if risk_score >= 50:
            return AISeverity.MEDIUM
        if risk_score >= 25:
            return AISeverity.LOW
        return AISeverity.NORMAL

    def _select_trigger_sensor(self, grouped: dict[str, list[tuple[Sensor, SensorData]]]) -> Sensor | None:
        for sensor_type in ("Leakage", "Pressure", "Vibration"):
            points = grouped.get(sensor_type) or []
            if points:
                return points[-1][0]
        for points in grouped.values():
            if points:
                return points[-1][0]
        return None

    def _create_risk_event(
        self,
        analysis: AIAnalysis,
        trigger_sensor: Sensor | None,
        risk_score: float,
        severity: AISeverity,
        current_user: User,
    ) -> RiskEvent:
        now = datetime.now(timezone.utc)
        event = RiskEvent(
            event_code=f"AI-{now.strftime('%Y%m%d%H%M%S')}-{str(uuid4())[:8]}",
            title=f"AI {severity.value} Risk Detected",
            description="Sensor fusion analysis detected pressure drop, vibration increase, and/or leakage signals.",
            pipeline_id=analysis.pipeline_id,
            sensor_id=trigger_sensor.id if trigger_sensor else None,
            ai_analysis_id=analysis.id,
            severity=severity.value,
            risk_score=risk_score,
            status="Open",
            location=trigger_sensor.geom if trigger_sensor else None,
            detected_at=now,
            evidence=analysis.evidence,
            created_by=current_user.id,
        )
        self.db.add(event)
        return event

    def _decision_message(self, risk_score: float, severity: AISeverity, created: bool) -> str:
        if created:
            return f"Risk Score {risk_score:.0f}, {severity.value} Event 생성"
        return f"Risk Score {risk_score:.0f}, RiskEvent 생성 기준 미충족"

    def to_read(self, analysis: AIAnalysis) -> AIAnalysisRead:
        return AIAnalysisRead(
            id=analysis.id,
            pipelineId=analysis.pipeline_id,
            sensorId=analysis.sensor_id,
            modelName=analysis.model_name,
            modelVersion=analysis.model_version,
            analysisType=analysis.analysis_type,
            riskScore=float(analysis.risk_score),
            severity=analysis.severity,
            startedAt=analysis.started_at,
            endedAt=analysis.ended_at,
            evidence=analysis.evidence,
            createdAt=analysis.created_at,
            createdBy=analysis.created_by,
        )
