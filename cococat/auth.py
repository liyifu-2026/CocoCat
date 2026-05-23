"""Authentication — JWT + API key middleware with multi-user bcrypt support."""
from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

import bcrypt
import jwt as pyjwt

logger = logging.getLogger("cococat.auth")

# ── Config ─────────────────────────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))
API_KEY = os.environ.get("API_KEY", "")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "admin")

# Routes that skip auth
PUBLIC_PATHS = {"/api/health", "/ws", "/api/auth/login", "/api/auth/init", "/api/auth/status"}
PUBLIC_PREFIXES = ["/api/channels"]


# ── Token helpers ──────────────────────────────────────────

def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = int(time.time()) + JWT_EXPIRE_MINUTES * 60
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.PyJWTError:
        return None


# ── Password hash ──────────────────────────────────────────

def _password_hash() -> str:
    return hashlib.sha256(WEB_PASSWORD.encode()).hexdigest()


def verify_password(password: str) -> bool:
    """Legacy SHA-256 fallback — deprecated, use verify_user_password instead."""
    return hashlib.sha256(password.encode()).hexdigest() == _password_hash()


def verify_user_password(username: str, password: str, db) -> bool:
    """Verify username/password against the users table using bcrypt."""
    row = db.fetch_one(
        "SELECT password_hash FROM users WHERE id = ?", (username,)
    )
    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row["password_hash"].encode())


# ── Middleware ─────────────────────────────────────────────

async def auth_middleware(request, call_next):
    """FastAPI middleware: authenticate all requests except public paths.

    If no API_KEY or JWT_SECRET is configured, auth is skipped entirely.
    """
    path = request.url.path.rstrip("/")

    if path in PUBLIC_PATHS or path.startswith("/ws"):
        return await call_next(request)

    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return await call_next(request)

    # Auth disabled — no credentials configured
    if not API_KEY and JWT_SECRET == "change-me":
        return await call_next(request)

    # Try Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = verify_token(token)
        if payload:
            # Inject user_id into AppContext
            ctx = getattr(request.app.state, "ctx", None)
            if ctx:
                ctx.user_id = payload.get("sub")
            return await call_next(request)

    # Try API key
    api_key = request.headers.get("X-API-Key", "")
    if api_key and API_KEY and api_key == API_KEY:
        return await call_next(request)

    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
