"""Authentication routes: login and token verification."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from auth import verify_password, get_password_hash, create_access_token, verify_jwt_token

router = APIRouter()

WEB_PASSWORD_HASH = get_password_hash(os.environ.get("WEB_PASSWORD", ""))


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/api/auth/login")
async def login(req: LoginRequest):
    if not verify_password(req.password, WEB_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_access_token({"sub": "admin"})
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/api/auth/verify")
async def verify(token: str = None):
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True, "sub": payload.get("sub")}


def validate_config():
    import os
    if not os.environ.get("WEB_PASSWORD"):
        raise RuntimeError("WEB_PASSWORD environment variable is not set")
