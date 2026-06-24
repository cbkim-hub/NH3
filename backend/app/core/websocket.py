from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocket, WebSocketDisconnect


class DashboardWebSocketManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self.queue: asyncio.Queue[dict[str, Any]] | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._pump_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.queue = asyncio.Queue()
        self._pump_task = asyncio.create_task(self._pump(), name="dashboard-websocket-pump")

    async def stop(self) -> None:
        if self._pump_task:
            self._pump_task.cancel()
            try:
                await self._pump_task
            except asyncio.CancelledError:
                pass
        self.active_connections.clear()
        self.queue = None
        self.loop = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        await websocket.send_json(
            self._build_event("Connected", {"message": "Dashboard websocket connected"})
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = self._build_event(event_type, payload)
        if not self.loop or not self.queue:
            return
        self.loop.call_soon_threadsafe(self.queue.put_nowait, event)

    def _build_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return jsonable_encoder(
            {
                "id": str(uuid4()),
                "type": event_type,
                "payload": payload,
                "occurredAt": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def _pump(self) -> None:
        if self.queue is None:
            return
        while True:
            event = await self.queue.get()
            await self.broadcast(event)

    async def broadcast(self, event: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        for websocket in list(self.active_connections):
            try:
                await websocket.send_json(event)
            except (RuntimeError, WebSocketDisconnect):
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)


dashboard_ws_manager = DashboardWebSocketManager()
