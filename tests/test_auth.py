"""Tests for cococat.auth — JWT tokens, password hashing, and middleware."""
import os
import time
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cococat import auth
from cococat.auth import (
    create_access_token,
    verify_token,
    verify_password,
    auth_middleware,
)


# ── Token tests ──────────────────────────────────────────────────

class TestToken:
    def test_create_returns_valid_jwt_string(self):
        token = create_access_token({"sub": "test"})
        assert isinstance(token, str)
        decoded = verify_token(token)
        assert decoded is not None
        assert decoded["sub"] == "test"

    def test_verify_succeeds_for_valid_token(self):
        token = create_access_token({"sub": "test"})
        decoded = verify_token(token)
        assert decoded is not None
        assert "exp" in decoded
        assert decoded["sub"] == "test"

    def test_verify_fails_for_expired_token(self):
        expired_payload = {"sub": "test", "exp": int(time.time()) - 1}
        expired_token = pyjwt.encode(
            expired_payload, auth.JWT_SECRET, algorithm=auth.JWT_ALGORITHM,
        )
        assert verify_token(expired_token) is None

    def test_verify_fails_for_tampered_token(self):
        token = create_access_token({"sub": "test"})
        tampered = token[:-1] + ("B" if token[-1] != "B" else "C")
        assert verify_token(tampered) is None


# ── Password tests ────────────────────────────────────────────────

class TestPassword:
    def test_verify_correct_password(self, monkeypatch):
        monkeypatch.setenv("WEB_PASSWORD", "secret123")
        import importlib
        importlib.reload(auth)
        try:
            assert auth.verify_password("secret123") is True
        finally:
            importlib.reload(auth)

    def test_verify_rejects_wrong_password(self):
        assert verify_password("wrong-password") is False


# ── Middleware helpers ────────────────────────────────────────────

@pytest.fixture
def app_with_auth():
    app = FastAPI()
    app.middleware("http")(auth_middleware)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/protected")
    async def protected():
        return {"data": "secret"}

    @app.get("/ws")
    async def ws():
        return {"ws": "open"}

    return app


# ── Middleware tests ──────────────────────────────────────────────

class TestMiddleware:
    @pytest.fixture
    def client(self, app_with_auth):
        """TestClient with auth enabled (non-default JWT_SECRET and API_KEY)."""
        with patch.object(auth, "JWT_SECRET", "test-secret"), \
             patch.object(auth, "API_KEY", "test-api-key"):
            yield TestClient(app_with_auth)

    def test_whitelisted_health_passes(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_whitelisted_ws_passes(self, client):
        resp = client.get("/ws")
        assert resp.status_code == 200

    def test_protected_returns_401_without_token(self, client):
        resp = client.get("/api/protected")
        assert resp.status_code == 401

    def test_protected_passes_with_valid_bearer_token(self, app_with_auth, client):
        token = create_access_token({"sub": "test"})
        resp = client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_protected_passes_with_valid_api_key(self, client):
        resp = client.get(
            "/api/protected",
            headers={"X-API-Key": "test-api-key"},
        )
        assert resp.status_code == 200

    def test_protected_rejects_invalid_bearer_token(self, client):
        resp = client.get(
            "/api/protected",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401
