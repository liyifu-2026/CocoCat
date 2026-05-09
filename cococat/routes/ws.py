"""WebSocket route — real-time events via EventBus."""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class WsManager:
    """Manages WebSocket connections and EventBus → WS broadcast."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Send event to all connected WebSocket clients."""
        message = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint — receives real-time events from EventBus."""
    # Access app state via the websocket's app reference
    manager = ws.app.state.ws_manager
    await manager.connect(ws)
    await ws.send_text(json.dumps({"type": "connected", "data": {"session_id": "ws"}}))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
