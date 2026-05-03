import os
os.environ["WEB_PASSWORD"] = "test-pass-123"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["API_KEY"] = "test-api-key"

import sys, pytest
sys.path.insert(0, "web")
from auth import create_access_token, verify_jwt_token, verify_api_key, verify_password, get_password_hash

def test_password_hashing():
    pw = "hello123"
    hashed = get_password_hash(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)

def test_jwt_create_and_verify():
    token = create_access_token({"sub": "admin"})
    assert token and isinstance(token, str)
    payload = verify_jwt_token(token)
    assert payload["sub"] == "admin"

def test_jwt_expired():
    token = create_access_token({"sub": "admin"}, expires_delta=-1)
    payload = verify_jwt_token(token)
    assert payload is None

def test_verify_api_key():
    assert verify_api_key("test-api-key")
    assert not verify_api_key("wrong-key")


from fastapi.testclient import TestClient
from web.main import app

client = TestClient(app)

def test_login_success():
    resp = client.post("/api/auth/login", json={"password": "test-pass-123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_failure():
    resp = client.post("/api/auth/login", json={"password": "wrong"})
    assert resp.status_code == 401
    assert "detail" in resp.json()
