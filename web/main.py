"""Stub — web FastAPI app for test_web_auth.py."""
import os
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse

app = FastAPI()

WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "admin")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me")
API_KEY = os.environ.get("API_KEY", "")

security = HTTPBearer(auto_error=False)

from auth import create_access_token, verify_jwt_token, verify_api_key, verify_password


def get_password_hash_from_env():
    import hashlib
    return hashlib.sha256(WEB_PASSWORD.encode()).hexdigest()


async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_jwt_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


async def require_api_key(request: Request):
    api_key = request.headers.get("X-API-Key", "")
    if not verify_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.post("/api/auth/login")
async def login(request: Request):
    body = await request.json()
    password = body.get("password", "")
    if not verify_password(password, get_password_hash_from_env()):
        raise HTTPException(status_code=401, detail="Incorrect password")
    token = create_access_token({"sub": "admin"})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/agents")
async def list_agents(payload=Depends(require_auth)):
    return {"agents": []}


@app.post("/api/scenes/{scene_id}/chat")
async def scene_chat(scene_id: str):
    raise HTTPException(status_code=401, detail="Not authenticated")


@app.post("/api/channels/webhook/scene/{scene_id}")
async def webhook(scene_id: str, request: Request, _=Depends(require_api_key)):
    return JSONResponse(status_code=200, content={"status": "ok"})
