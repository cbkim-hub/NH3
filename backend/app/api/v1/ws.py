from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.rbac import is_token_revoked
from app.core.security import TokenPayloadError, TokenType, decode_token
from app.core.websocket import dashboard_ws_manager

router = APIRouter()


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if token:
        try:
            payload = decode_token(token, expected_type=TokenType.ACCESS)
            if is_token_revoked(payload.get("jti")):
                raise TokenPayloadError("Token has been revoked")
        except TokenPayloadError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await dashboard_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_ws_manager.disconnect(websocket)
