# P0 Security Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two critical security issues: add JWT + API Key authentication to the web panel, and add command validation sandbox to exec_command.

**Architecture:** Dual independent auth channels — JWT for management panel (human operators via browser), API Key for external endpoints (webhooks, scene chat). Cross-platform command sandbox with platform-specific dangerous pattern detection for Windows and Linux.

**Tech Stack:** Python (FastAPI, python-jose, passlib, bcrypt), TypeScript (React 19, React Router v7), Python (subprocess)

---

## Part A: exec_command Sandbox

### Task A1: Create `py-agent/sandbox.py` — CommandValidator

**Files:**
- Create: `py-agent/sandbox.py`
- Test: `tests/test_sandbox.py`

- [ ] **Step 1: Write failing test for dangerous command detection (Windows)**

```python
# tests/test_sandbox.py
import sys, pytest
sys.path.insert(0, "py-agent")
from sandbox import CommandValidator, IS_WINDOWS

validator = CommandValidator()

def test_block_destructive_windows():
    if not IS_WINDOWS:
        pytest.skip("Windows-only test")
    assert not validator.validate("del /f /s C:\\*", "FULL_ACCESS")[0]
    assert not validator.validate("rmdir /s /q C:\\", "FULL_ACCESS")[0]
    assert not validator.validate("format D: /q", "FULL_ACCESS")[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sandbox.py::test_block_destructive_windows -v 2>&1`
Expected: ModuleNotFoundError (sandbox module doesn't exist yet)

- [ ] **Step 3: Create `py-agent/sandbox.py` with platform detection and dangerous patterns**

```python
import sys, os, re
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

_DANGEROUS_PATTERNS_WIN = [
    r"del\s+[/\\][fFsS]",
    r"rmdir\s+[/\\][sS]\s+[/\\][qQ]",
    r"format\s+\w:",
    r"diskpart",
    r"shutdown\s+[/\\]",
    r"restart-computer",
    r"%0\|%0",
    r"runas\s+[/\\]",
    r"net\s+user\s+",
    r"route\s+",
    r"netsh\s+",
    r"ipconfig\s+[/\\]release",
    r"choco\s+install",
    r"winget\s+install",
    r"reg\s+(delete|add)",
]

_DANGEROUS_PATTERNS_LIN = [
    r"\brm\s+-rf\s+/\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshred\b",
    r"\bshutdown\s+-[hrP]",
    r"\breboot\b",
    r"\bpoweroff\b",
    r":\(\)\{\:\|:\&\};:",
    r"\bsudo\b",
    r"\bsu\s+-",
    r"\bchmod\s+4777",
    r"\biptables\b",
    r"\bifconfig\s+down",
    r"\b(apt|yum|dnf|apk)\s+(install|remove|purge)",
    r"pip\s+install\s+--system",
]

_INTERNAL_IPS = [
    r"127\.0\.0\.\d+",
    r"10\.\d+\.\d+\.\d+",
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",
    r"192\.168\.\d+\.\d+",
    r"169\.254\.169\.254",
]

_DANGEROUS_PATTERNS = _DANGEROUS_PATTERNS_WIN if IS_WINDOWS else _DANGEROUS_PATTERNS_LIN


class CommandValidator:
    def validate(self, command: str, mode: str) -> tuple:
        command_lower = command.lower()
        for pat in _DANGEROUS_PATTERNS:
            if re.search(pat, command_lower):
                return False, f"dangerous pattern detected: {pat}"
        if self._has_ssrf(command_lower):
            return False, "command targets internal network (SSRF)"
        return True, ""

    def _has_ssrf(self, cmd: str) -> bool:
        has_http = bool(re.search(r"\b(curl|wget|invoke-webrequest|iwr)\b", cmd))
        if not has_http:
            return False
        for ip_pat in _INTERNAL_IPS:
            if re.search(ip_pat, cmd):
                return True
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sandbox.py::test_block_destructive_windows -v 2>&1`
Expected: PASS (or SKIP if not on Windows)

- [ ] **Step 5: Write failing test for Linux patterns**

```python
# Append to tests/test_sandbox.py
def test_block_destructive_linux():
    if IS_WINDOWS:
        pytest.skip("Linux-only test")
    assert not validator.validate("rm -rf /", "FULL_ACCESS")[0]
    assert not validator.validate("sudo apt install nginx", "FULL_ACCESS")[0]
    assert not validator.validate("dd if=/dev/zero of=/dev/sda", "FULL_ACCESS")[0]
```

- [ ] **Step 6: Run test**

Run: `pytest tests/test_sandbox.py::test_block_destructive_linux -v 2>&1`
Expected: PASS (or SKIP depending on platform)

- [ ] **Step 7: Write failing test for SSRF protection**

```python
# Append to tests/test_sandbox.py
def test_block_ssrf():
    assert not validator.validate("curl http://169.254.169.254/latest/meta-data/", "FULL_ACCESS")[0]
    assert not validator.validate("wget http://10.0.0.1/config", "FULL_ACCESS")[0]
    assert not validator.validate("curl http://192.168.1.1/admin", "FULL_ACCESS")[0]

def test_allow_safe_commands():
    assert validator.validate("echo hello", "FULL_ACCESS")[0]
    assert validator.validate("ls -la", "FULL_ACCESS")[0]
    assert validator.validate("python --version", "FULL_ACCESS")[0]
    assert validator.validate("git status", "FULL_ACCESS")[0]
    assert validator.validate("pip list", "FULL_ACCESS")[0]
```

- [ ] **Step 8: Run SSRF tests**

Run: `pytest tests/test_sandbox.py::test_block_ssrf tests/test_sandbox.py::test_allow_safe_commands -v 2>&1`
Expected: Both PASS

- [ ] **Step 9: Commit**

```bash
git add py-agent/sandbox.py tests/test_sandbox.py
git commit -m "feat(sandbox): add CommandValidator with cross-platform dangerous pattern and SSRF detection"
```

### Task A2: EnvironmentSanitizer + PathValidator + OutputTruncator

- [ ] **Step 1: Write failing tests for env sanitizer, path validator, and output truncator**

```python
# Append to tests/test_sandbox.py
from sandbox import EnvironmentSanitizer, PathValidator, OutputTruncator

sanitizer = EnvironmentSanitizer()
path_val = PathValidator()
truncator = OutputTruncator()

def test_env_sanitizer_removes_secrets():
    dirty = {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk-xxx", "HOME": "/root", "JWT_SECRET": "mysecret"}
    clean = sanitizer.sanitize(dirty)
    assert "OPENAI_API_KEY" not in clean
    assert "JWT_SECRET" not in clean
    assert "PATH" in clean
    assert "HOME" in clean

def test_path_validator_allows_workspace():
    ws = Path("/tmp/workspace")
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "test.txt").write_text("hello")
    ok, _ = path_val.validate(str(ws / "test.txt"), ws)
    assert ok

def test_path_validator_blocks_outside():
    ws = Path("/tmp/workspace")
    ok, reason = path_val.validate("/etc/passwd", ws)
    assert not ok
    assert "outside workspace" in reason

def test_output_truncator():
    short = "hello"
    assert truncator.truncate(short) == short
    long = "x" * 20000
    truncated = truncator.truncate(long)
    assert len(truncated) <= 10000 + 50  # max_chars + suffix
    assert "truncated" in truncated
```

- [ ] **Step 2: Add EnvironmentSanitizer to `sandbox.py`**

```python
# Append to py-agent/sandbox.py

if IS_WINDOWS:
    _ALLOWED_ENV_KEYS = {"PATH", "SYSTEMROOT", "USERPROFILE", "APPDATA",
                         "LOCALAPPDATA", "TEMP", "TMP", "COMSPEC"}
else:
    _ALLOWED_ENV_KEYS = {"PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "TEMP", "SHELL"}

_SECRET_PATTERNS = re.compile(r"(key|secret|token|password|credential|auth|cert)", re.IGNORECASE)


class EnvironmentSanitizer:
    def sanitize(self, env: dict) -> dict:
        clean = {}
        for k in _ALLOWED_ENV_KEYS:
            if k in env:
                clean[k] = env[k]
        for k, v in env.items():
            if k.startswith("COCOCAT_"):
                clean[k] = v
        return clean
```

- [ ] **Step 3: Add PathValidator to `sandbox.py`**

```python
# Append to py-agent/sandbox.py

class PathValidator:
    def validate(self, path: str, workspace: Path) -> tuple:
        try:
            resolved = Path(path).resolve()
            ws = workspace.resolve()
            if not str(resolved).startswith(str(ws)):
                return False, "path outside workspace"
            return True, ""
        except Exception as e:
            return False, f"path validation error: {e}"
```

- [ ] **Step 4: Add OutputTruncator to `sandbox.py`**

```python
# Append to py-agent/sandbox.py

class OutputTruncator:
    def __init__(self, max_chars: int = 10000):
        self.max_chars = max_chars

    def truncate(self, output: str) -> str:
        if len(output) <= self.max_chars:
            return output
        return output[:self.max_chars] + f"\n... (truncated, {len(output) - self.max_chars} more chars)"
```

- [ ] **Step 5: Run all sandbox tests**

Run: `pytest tests/test_sandbox.py -v 2>&1`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add py-agent/sandbox.py tests/test_sandbox.py
git commit -m "feat(sandbox): add EnvironmentSanitizer, PathValidator, OutputTruncator"
```

### Task A3: Integrate sandbox into tools.py

- [ ] **Step 1: Write failing integration test for ExecCommandTool with sandbox**

```python
# tests/test_sandbox.py
from sandbox import CommandValidator, EnvironmentSanitizer, PathValidator, OutputTruncator

def test_exec_command_sandbox_integration():
    from tools import ExecCommandTool
    tool = ExecCommandTool()
    # Dangerous command should be rejected
    result = tool.execute(command="rm -rf /" if not IS_WINDOWS else "del /f /s C:\\*")
    assert result.startswith("Error:") or "rejected" in result
    # Safe command should work
    result2 = tool.execute(command="echo hello")
    assert "hello" in result2
```

- [ ] **Step 2: Run integration test to verify it fails because tools.py still has old code**

Run: `pytest tests/test_sandbox.py::test_exec_command_sandbox_integration -v 2>&1`
Expected: FAIL — dangerous command is NOT rejected by old code

- [ ] **Step 3: Modify `ExecCommandTool.execute` in `py-agent/tools.py`**

Read the current file first:

```bash
Select-String -Path py-agent/tools.py -Pattern "class ExecCommandTool" -Context 0,40
```

Replace `ExecCommandTool.execute` method with sandbox-wrapped version:

```python
# In py-agent/tools.py, modify ExecCommandTool.execute:

def execute(self, command="", timeout=60, description="", **kwargs) -> str:
    from sandbox import CommandValidator, EnvironmentSanitizer, OutputTruncator

    validator = CommandValidator()
    is_safe, reason = validator.validate(command, self.required_permission)
    if not is_safe:
        return f"Error: Command rejected - {reason}"

    sanitizer = EnvironmentSanitizer()
    clean_env = sanitizer.sanitize(os.environ.copy())

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, env=clean_env, cwd=PROJECT_ROOT,
        )
        output = OutputTruncator().truncate(result.stdout or "")
        if result.stderr:
            output += f"\n[stderr]\n{OutputTruncator().truncate(result.stderr)}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error executing command: {e}"
```

- [ ] **Step 4: Run integration test again**

Run: `pytest tests/test_sandbox.py::test_exec_command_sandbox_integration -v 2>&1`
Expected: PASS

- [ ] **Step 5: Add path validation to file tools**

```python
# In py-agent/tools.py, add path validation to ReadFileTool.execute, WriteFileTool.execute, EditFileTool.execute

# At the start of each file tool's execute method, add:
from sandbox import PathValidator
validator = PathValidator()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
is_safe, reason = validator.validate(path, PROJECT_ROOT)
if not is_safe:
    return f"Error: {reason}"
```

- [ ] **Step 6: Commit**

```bash
git add py-agent/tools.py tests/test_sandbox.py
git commit -m "feat(sandbox): integrate sandbox validation into ExecCommandTool and file tools"
```

- [ ] **Step 7: Run existing tests to ensure no regressions**

Run: `pytest tests/ -v 2>&1`
Expected: All existing tests still pass

---

## Part B: Web Panel Authentication (JWT + API Key)

### Task B1: Add auth dependencies and env vars

- [ ] **Step 1: Update `web/requirements.txt`**

```python
# Append to web/requirements.txt
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
```

- [ ] **Step 2: Update `.env.example`**

```bash
# Append to .env.example
WEB_PASSWORD=your-admin-password
JWT_SECRET=your-jwt-secret-key
JWT_EXPIRE_MINUTES=480
API_KEY=your-api-key-for-external-access
COCOCAT_WORKSPACE=  # defaults to project root
EXEC_COMMAND_ALLOWED_MODES=WORKSPACE_WRITE,FULL_ACCESS
```

- [ ] **Step 3: Commit**

```bash
git add web/requirements.txt .env.example
git commit -m "chore(auth): add auth dependencies and env vars"
```

### Task B2: Create `web/auth.py` — shared auth utilities

- [ ] **Step 1: Write failing test for auth utilities**

```python
# tests/test_web_auth.py
import sys, os, pytest
sys.path.insert(0, "web")
os.environ["WEB_PASSWORD"] = "test-pass-123"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["API_KEY"] = "test-api-key"

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
    import time
    token = create_access_token({"sub": "admin"}, expires_delta=0)
    payload = verify_jwt_token(token)
    assert payload is None  # expired or invalid

def test_verify_api_key():
    assert verify_api_key("test-api-key")
    assert not verify_api_key("wrong-key")
```

- [ ] **Step 2: Create `web/auth.py`**

```python
"""Shared auth utilities: JWT + API Key dual authentication."""
import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))
API_KEY = os.environ.get("API_KEY", "")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: int = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_delta if expires_delta is not None else JWT_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_api_key(token: str) -> bool:
    if not API_KEY or not token:
        return False
    return token == API_KEY
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_web_auth.py -v 2>&1`
Expected: 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add web/auth.py tests/test_web_auth.py
git commit -m "feat(auth): add shared auth utilities (JWT + API Key)"
```

### Task B3: Create `web/routes/auth.py` — login/verify endpoints

- [ ] **Step 1: Write failing test for login endpoint**

```python
# tests/test_web_auth.py
import os
os.environ["WEB_PASSWORD"] = "test-pass-123"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["API_KEY"] = "test-api-key"

import sys, pytest
sys.path.insert(0, "web")
from fastapi.testclient import TestClient
from main import app
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
    assert "error" in resp.json()
```

- [ ] **Step 2: Create `web/routes/auth.py`**

```python
"""Authentication routes: login and token verification."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys, os
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
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_web_auth.py -v 2>&1`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add web/routes/auth.py tests/test_web_auth.py
git commit -m "feat(auth): add login and verify endpoints"
```

### Task B4: Add auth dependency injection to `web/main.py`

- [ ] **Step 1: Read `web/main.py` to plan changes**

Run: type web\main.py | Select-Object -First 60

- [ ] **Step 2: Modify `web/main.py` — add auth dependency and protect routes**

Add at top of `web/main.py` (after existing imports):

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from web.auth import verify_jwt_token, verify_api_key
import sys
sys.path.insert(0, str(BASE_DIR / "web"))

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = None
):
    # Try JWT first
    if credentials:
        payload = verify_jwt_token(credentials.credentials)
        if payload:
            return payload
    # Then try API Key
    if x_api_key and verify_api_key(x_api_key):
        return {"sub": "api", "auth_type": "api_key"}
    raise HTTPException(status_code=401, detail="Authentication required")


async def require_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = verify_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload
```

- [ ] **Step 3: Register auth router and protect management routes with dependency**

```python
# In web/main.py, after the existing route includes:
from web.routes.auth import router as auth_router
app.include_router(auth_router)

# Add protected versions of all existing includes using Depends
# For each include_router, wrap endpoints or add global dependency:
from fastapi import APIRouter

# Agents, hiring, knowledge, scenes, skills, entries, mailbox, chat, status, schedule
# need Depends(require_jwt) for their management endpoints

# External endpoints (scene chat, webhooks) need get_current_user (accepts both JWT and API Key)
```

Add the `Depends` to route endpoint functions as needed. For simplicity, add a middleware or use `app.dependency_overrides` approach:

```python
# At the bottom of web/main.py, add protected routers with dependency

# Protected routers (JWT required)
protected_routers = [
    (agents_router, "/api"),
    (knowledge_router, "/api"),
    (scene_router, "/api"),
    (entries_router, "/api"),
    (mailbox_router, "/api"),
    (chat_router, "/api"),
    (status_router, "/api"),
    (schedule_router, "/api"),
]

# For each protected router, we add the dependency via app.dependency_overrides or
# by creating a new APIRouter with dependencies

# Simpler approach: use a middleware that checks auth on all routes except public ones
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = [
        "/api/auth/login",
        "/api/auth/verify",
        "/api/scenes/",  # scene chat is handled separately
    ]
    path = request.url.path

    # Public paths
    if path.startswith("/api/auth/"):
        return await call_next(request)

    # Check auth
    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    # Determine if this is an external endpoint
    is_external = any([
        path.startswith("/api/scenes/") and path.endswith("/chat"),
        path.startswith("/api/channels/"),
    ])

    if is_external:
        # Accept either JWT or API Key
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if verify_jwt_token(token):
                return await call_next(request)
        if api_key_header and verify_api_key(api_key_header):
            return await call_next(request)
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    else:
        # Management endpoints: JWT only
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        token = auth_header[7:]
        if not verify_jwt_token(token):
            return JSONResponse({"error": "Invalid or expired token"}, status_code=401)
        return await call_next(request)
```

- [ ] **Step 4: Update WebSocket endpoint to accept token query param**

```python
# In web/main.py, modify websocket_endpoint:
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = None):
    if not token or not verify_jwt_token(token):
        await ws.close(code=4001)
        return
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
```

- [ ] **Step 5: Commit**

```bash
git add web/main.py web/auth.py web/routes/auth.py
git commit -m "feat(auth): add auth middleware to protect management and external endpoints"
```

### Task B5: Create React frontend auth

- [ ] **Step 1: Create `web-ui/src/context/AuthContext.tsx`**

```typescript
import React, { createContext, useContext, useState, useCallback, useEffect } from "react";

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  login: (password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("cococat_token")
  );

  const isAuthenticated = !!token;

  const login = useCallback(async (password: string) => {
    const resp = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!resp.ok) throw new Error("Invalid password");
    const data = await resp.json();
    localStorage.setItem("cococat_token", data.access_token);
    setToken(data.access_token);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("cococat_token");
    setToken(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Create `web-ui/src/pages/Login.tsx`**

```typescript
import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await login(password);
      navigate("/");
    } catch {
      setError("密码错误");
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-80">
        <h1 className="text-xl font-bold mb-6 text-center">CocoCat 管理面板</h1>
        {error && <div className="text-red-500 text-sm mb-4">{error}</div>}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="请输入密码"
          className="w-full border rounded px-3 py-2 mb-4"
          autoFocus
        />
        <button
          type="submit"
          className="w-full bg-blue-600 text-white rounded py-2 hover:bg-blue-700"
        >
          登录
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Create `web-ui/src/components/ProtectedRoute.tsx`**

```typescript
import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}
```

- [ ] **Step 4: Add API auth header interceptor in `web-ui/src/api/client.ts`**

Read current `client.ts` first:

```bash
type web-ui\src\api\client.ts
```

Then wrap fetch to inject auth header:

```typescript
// At the top of web-ui/src/api/client.ts
const API_BASE = "";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("cococat_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (resp.status === 401) {
    localStorage.removeItem("cococat_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  return resp.json();
}
```

- [ ] **Step 5: Update `web-ui/src/App.tsx`**

```typescript
// Add to imports:
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";

// In the JSX, wrap routes:
<AuthProvider>
  <Routes>
    <Route path="/login" element={<Login />} />
    <Route element={<ProtectedRoute />}>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/agents" element={<Agents />} />
        {/* ... all existing routes ... */}
      </Route>
    </Route>
  </Routes>
</AuthProvider>
```

- [ ] **Step 6: Add logout button to `web-ui/src/components/Sidebar.tsx`**

```typescript
// Add at bottom of sidebar navigation:
import { useAuth } from "../context/AuthContext";
import { LogOut } from "lucide-react";

function Sidebar() {
  const { logout } = useAuth();
  // ...
  return (
    <div>
      {/* ... existing nav items ... */}
      <button onClick={logout} className="flex items-center gap-2 p-2 text-red-600 hover:bg-red-50 rounded">
        <LogOut size={16} />
        <span>退出登录</span>
      </button>
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
git add web-ui/src/context/AuthContext.tsx web-ui/src/pages/Login.tsx web-ui/src/components/ProtectedRoute.tsx web-ui/src/api/client.ts web-ui/src/App.tsx web-ui/src/components/Sidebar.tsx
git commit -m "feat(auth): add React frontend login page, auth context, and protected routes"
```

### Task B6: Verify frontend builds

- [ ] **Step 1: Run TypeScript check**

```bash
cd web-ui && npx tsc --noEmit 2>&1
```

Expected: No type errors

- [ ] **Step 2: Run lint**

```bash
cd web-ui && npm run lint 2>&1
```

Expected: No lint errors

- [ ] **Step 3: If there are errors, fix them and commit**

```bash
git add -A
git commit -m "fix: resolve TypeScript/lint errors from auth integration"
```

---

## Part C: Integration Verification

### Task C1: Run all tests

- [ ] **Step 1: Run all Python tests**

```bash
pytest tests/ -v 2>&1
```

Expected: All tests PASS

- [ ] **Step 2: Verify web panel loads with auth**

```bash
cd web && python -m uvicorn main:app --reload 2>&1 &
```

Expected: Server starts. Opening `http://localhost:8000` redirects to login. Login with correct password works. API endpoints return 401 without token.
