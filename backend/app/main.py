from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.websocket import dashboard_ws_manager

app = FastAPI(title="NH3 Pipeline Monitoring API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
async def start_dashboard_websockets():
    await dashboard_ws_manager.start()


@app.on_event("shutdown")
async def stop_dashboard_websockets():
    await dashboard_ws_manager.stop()


app.include_router(api_router, prefix="/api/v1")
