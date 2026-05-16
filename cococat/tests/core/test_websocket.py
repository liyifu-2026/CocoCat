"""Test WebSocket endpoint — connect, receive, ping/pong, disconnect."""
import pytest


class TestWebSocket:
    @pytest.mark.asyncio
    async def test_ws_connect_and_receive_connected(self):
        """WebSocket should accept connection and send 'connected' event."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from cococat.routes.ws import router as ws_router, WsManager
        from cococat.context import AppContext

        app = FastAPI()
        app.state.ctx = AppContext(ws_manager=WsManager())
        app.include_router(ws_router)

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"

    @pytest.mark.asyncio
    async def test_ws_ping_pong(self):
        """WebSocket should respond to ping with pong."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from cococat.routes.ws import router as ws_router, WsManager
        from cococat.context import AppContext

        app = FastAPI()
        app.state.ctx = AppContext(ws_manager=WsManager())
        app.include_router(ws_router)

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # consume connected
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    @pytest.mark.asyncio
    async def test_ws_broadcast_to_clients(self):
        """Manager.broadcast should send to all connected clients."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from cococat.routes.ws import router as ws_router, WsManager
        from cococat.context import AppContext

        ws_manager = WsManager()
        app = FastAPI()
        app.state.ctx = AppContext(ws_manager=ws_manager)
        app.include_router(ws_router)

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # connected
            await ws_manager.broadcast("text_delta", {"content": "hello"})
            data = ws.receive_json()
            assert data["type"] == "text_delta"
            assert data["data"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_ws_disconnect_cleanup(self):
        """Manager should clean up after disconnect."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from cococat.routes.ws import router as ws_router, WsManager
        from cococat.context import AppContext

        ws_manager = WsManager()
        app = FastAPI()
        app.state.ctx = AppContext(ws_manager=ws_manager)
        app.include_router(ws_router)

        client = TestClient(app)
        assert len(ws_manager._connections) == 0
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # connected
            assert len(ws_manager._connections) == 1
        assert len(ws_manager._connections) == 0
