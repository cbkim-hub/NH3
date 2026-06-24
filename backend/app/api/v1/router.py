from fastapi import APIRouter

from app.api.v1 import actions, ai_analysis, auth, dashboard, notifications, pipelines, risk_events, sensors, telemetry, ws

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(sensors.router, prefix="/sensors", tags=["sensors"])
api_router.include_router(risk_events.router, prefix="/risk-events", tags=["risk-events"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(actions.router, prefix="/actions", tags=["actions"])
api_router.include_router(ai_analysis.router, prefix="/ai-analysis", tags=["ai-analysis"])
api_router.include_router(ws.router, prefix="/ws", tags=["websocket"])
