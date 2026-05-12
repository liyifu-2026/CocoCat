# P0 Security Fixes: Web Panel Authentication + exec_command Sandbox

## Overview

Fix two critical security issues in CocoCat:

1. **P0-2**: Web management panel has zero authentication — all 40+ API endpoints are fully public
2. **P0-4**: `exec_command` tool runs arbitrary shell commands with no restrictions — agents can execute dangerous commands, access internal network, and leak secrets

## 1. Web Panel Authentication

### Approach: Dual Independent Auth Channels

Two separate auth mechanisms for two different audiences:

| Channel | Audience | Auth Method | Endpoints |
|---------|----------|-------------|-----------|
| **Management API** | Human operators (via React SPA) | JWT (password login) | `/api/agents/*`, `/api/hiring/*`, `/api/schedule/*`, etc. |
| **External API** | External services / programmatic callers | API Key (static) | `/api/scenes/{id}/chat`, `/api/channels/webhook/*`, `/api/channels/wechat/*`, `/api/scenes/{id}/users/{uid}/history` |

```
                    ┌──────────────────────────────┐
                    │      Management Panel         │
                    │  (React SPA + all admin API)  │
                    │                                │
                    │  Auth: JWT (password login)    │
                    │  Header: Authorization: Bearer │
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │      FastAPI Backend          │
                    │                                │
                    │  GET /api/agents/*  → JWT    │
                    │  POST /api/hiring/* → JWT    │
                    │  POST /api/scenes/{id}/chat  │
                    │    → API Key                 │
                    │  POST /api/channels/webhook/*│
                    │    → API Key                 │
                    │  POST /api/auth/login → OPEN │
                    └──────────────────────────────┘
```

### Backend

**New dependencies** (`web/requirements.txt`):
- `python-jose[cryptography]` — JWT generation and verification
- `passlib[bcrypt]` — password hashing
- `python-multipart` — form parsing for login endpoint

**New env vars** (`.env`):
```
WEB_PASSWORD=your-admin-password
JWT_SECRET=your-jwt-secret-key
JWT_EXPIRE_MINUTES=480
API_KEY=your-api-key-for-external-access
```

**New file: `web/auth.py`** (shared utilities):
- `create_access_token(data, expires_delta)` — create JWT
- `verify_jwt_token(token)` — decode and verify JWT, return payload or None
- `verify_api_key(token)` — constant-time compare against `API_KEY` from env
- `get_current_user(authorization=Header(None), x_api_key=Header(None))` — try JWT first, then API Key, raise 401 if neither valid
- `verify_password(plain, hashed)` / `get_password_hash(password)` — bcrypt wrappers

**New file: `web/routes/auth.py`**:
- `POST /api/auth/login` — accept `{password}`, verify against `WEB_PASSWORD` (bcrypt), return JWT token
- `GET /api/auth/verify` — verify token validity, return current user info

**Modified: `web/main.py`**:
- Add auth dependency injection to all routes
- Protected by **JWT** (management endpoints):
  - All `/api/agents/*`
  - All `/api/scenes/*` (CRUD operations, NOT scene chat)
  - All `/api/knowledge/*`
  - All `/api/skills/*`
  - All `/api/mailbox/*`
  - All `/api/chat/*` (chat group management)
  - All `/api/hiring/*`
  - All `/api/status/*`
  - All `/api/schedule/*`
  - All `/api/entries/*`
  - WebSocket `/ws` (token via query param)
- Protected by **API Key** (external endpoints):
  - `POST /api/scenes/{scene_id}/chat`
  - `GET /api/scenes/{scene_id}/users/{user_id}/history`
  - `POST /api/channels/webhook/{target_type}/{target_id}`
  - `GET/POST /api/channels/wechat/{scene_id}` (in addition to existing signature verification)
- **Public** (no auth):
  - `POST /api/auth/login`
  - `GET /api/auth/verify`

**Modified: `web/routes/*.py`**:
- All 8 existing route files: add `Depends(get_current_user)` to every management endpoint

### Frontend

**Modified: `web-ui/src/api/client.ts`**:
- Add `Authorization: Bearer <token>` header to all requests
- Handle 401 responses → redirect to login

**New file: `web-ui/src/context/AuthContext.tsx`**:
- Store token in `localStorage`
- `isAuthenticated` state
- `login(password)` → calls `/api/auth/login`, stores token
- `logout()` → clears token, redirects to login

**New file: `web-ui/src/pages/Login.tsx`**:
- Simple password input form
- Error message display
- Redirect to dashboard on success

**Modified: `web-ui/src/App.tsx`**:
- Wrap routes with `<ProtectedRoute>` component
- Add `/login` route (unprotected)

**New file: `web-ui/src/components/ProtectedRoute.tsx`**:
- Check auth state, redirect to `/login` if not authenticated

**Modified: `web-ui/src/components/Sidebar.tsx`**:
- Add logout button

### WebSocket Auth

WebSocket connects via `/ws?token=<jwt>`. The server validates the token on connect.

## 2. exec_command Sandbox (Cross-Platform)

### Approach: Application-Layer Defense-in-Depth

Four independent layers, platform-aware. Inspired by claw-code's permission enforcer + bash validation pipeline, adapted for cross-platform use.

### New File: `py-agent/sandbox.py`

Structure:

```
sandbox.py
├── platform detection (sys.platform)
├── Layer 1: CommandValidator
│   ├── DANGEROUS_PATTERNS (Windows + Linux sets)
│   ├── INTERNAL_IPS (SSRF protection)
│   ├── READONLY_COMMANDS whitelist
│   ├── classify_command(cmd) → READONLY | WRITE | DANGEROUS
│   └── validate(cmd, mode) → (is_safe, reason)
├── Layer 2: EnvironmentSanitizer
│   ├── ALLOWED_ENV_KEYS (per-platform)
│   └── sanitize(env) → clean_env
├── Layer 3: PathValidator
│   └── validate(path, workspace) → (is_safe, reason)
├── Layer 4: OutputTruncator
│   └── truncate(output, max_chars=10000) → truncated
└── Layer 5: PermissionEnforcer
    └── check_tool(tool_name, agent_mode) → bool
```

Platform selection at module load time:

```python
import sys

IS_WINDOWS = sys.platform == "win32"

DANGEROUS_PATTERNS = _WINDOWS_DANGEROUS if IS_WINDOWS else _LINUX_DANGEROUS
ALLOWED_ENV_KEYS = _WINDOWS_ENV_KEYS if IS_WINDOWS else _LINUX_ENV_KEYS
```

Core validation logic is shared; only pattern lists and platform-specific paths differ.

#### Layer 1: CommandValidator

**Dangerous command detection** (cross-platform):

| Category | Windows Patterns | Linux Patterns |
|----------|-----------------|----------------|
| Destructive FS | `del /f /s`, `rmdir /s /q`, `format`, `diskpart` | `rm -rf /`, `mkfs`, `dd`, `shred` |
| System shutdown | `shutdown`, `restart-computer` | `shutdown -h`, `reboot`, `poweroff` |
| Fork bomb | `%0|%0` | `:(){:\|:&};:`, `fork()` |
| Privilege escalation | `runas`, `net user` | `sudo`, `su`, `chmod 4777` |
| Network manipulation | `route`, `netsh`, `ipconfig /release` | `iptables`, `ifconfig down` |
| Package management | `choco install`, `winget` | `apt`, `yum`, `pip install --system` |
| Registry (Windows) | `reg delete`, `reg add` | — |

**SSRF Protection**:
- Scan command strings for `curl`, `wget`, `Invoke-WebRequest` targeting private IP ranges
- Blocked ranges: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254` (cloud metadata)

**Command Classification**:
- `READONLY`: `ls`, `dir`, `pwd`, `echo`, `cat`, `type`, `find`, `grep`, `python --version`, `git status`, etc.
- `WRITE`: `mkdir`, `cp`, `copy`, `move`, `echo >`, etc.
- `DANGEROUS`: all destructive patterns above

Classification determines whether the command is allowed based on the agent's permission mode.

#### Layer 2: EnvironmentSanitizer

Strip sensitive environment variables before executing commands. Keep only:

| Windows | Linux |
|---------|-------|
| `PATH`, `SYSTEMROOT` | `PATH`, `HOME` |
| `USERPROFILE`, `APPDATA`, `LOCALAPPDATA` | `USER`, `LOGNAME` |
| `TEMP`, `TMP` | `TMPDIR`, `TEMP` |
| `COCOCAT_*` (project-specific) | `COCOCAT_*` |
| `COMSPEC` | `SHELL` |

**Explicitly removed**: `OPENAI_API_KEY`, `OPENAI_BASE_KEY`, `AWS_*`, `AZURE_*`, `DATABASE_URL`, `JWT_SECRET`, `WEB_PASSWORD`, `API_KEY` — any key/secret/token/password/credential env vars.

#### Layer 3: PathValidator

Ensures file paths stay within project workspace:

```python
def validate(path: str, workspace: Path) -> tuple[bool, str]:
    resolved = Path(path).resolve()
    if not str(resolved).startswith(str(workspace.resolve())):
        return False, "path outside workspace"
    return True, ""
```

#### Layer 4: OutputTruncator

```python
def truncate(output: str, max_chars: int = 10000) -> str:
    if len(output) <= max_chars:
        return output
    return output[:max_chars] + f"\n... (truncated, {len(output) - max_chars} more chars)"
```

#### Layer 5: PermissionEnforcer (for future use)

Cross-reference agent's permission level with tool requirements:
- `READONLY` agents: can only use read-only commands
- `WORKSPACE_WRITE` agents: can read/write within workspace
- `FULL_ACCESS` agents: unrestricted (but still validated for dangerous patterns)

### Modified: `py-agent/tools.py`

**ExecCommandTool** — wrap execution with sandbox:

```python
def execute(self, command="", timeout=60, description="", **kwargs):
    validator = CommandValidator()
    is_safe, reason = validator.validate(command, self.required_permission)
    if not is_safe:
        return f"Error: Command rejected - {reason}"

    sanitizer = EnvironmentSanitizer()
    clean_env = sanitizer.sanitize(os.environ.copy())

    result = subprocess.run(
        command, shell=True, capture_output=True, text=True,
        timeout=timeout, env=clean_env,
        cwd=PROJECT_ROOT,
    )

    output = OutputTruncator.truncate(result.stdout)
    if result.stderr:
        output += f"\n[stderr]\n{OutputTruncator.truncate(result.stderr)}"
    if result.returncode != 0:
        output += f"\n[exit code: {result.returncode}]"
    return output.strip() or "(no output)"
```

**ReadFileTool / WriteFileTool / EditFileTool / GlobSearchTool / GrepSearchTool** — add path validation:

```python
is_safe, reason = PathValidator.validate(path, workspace)
if not is_safe:
    return f"Error: {reason}"
```

### Configuration

**New env vars** (`.env`, optional):
```
COCOCAT_WORKSPACE=/path/to/project
EXEC_COMMAND_ALLOWED_MODES=WORKSPACE_WRITE,FULL_ACCESS
```

## Implementation Order

1. `py-agent/sandbox.py` — core validation module
2. `py-agent/tools.py` — integrate sandbox into ExecCommandTool + file tools
3. `web/auth.py` + `web/routes/auth.py` — backend dual auth infrastructure
4. `web/main.py` + `web/routes/*.py` — protect endpoints with auth dependency
5. `web-ui/` — frontend login page + auth context + protected routes
6. Update `.env.example` with new config vars
7. Update `web/requirements.txt` with new dependencies

## Testing

- `tests/test_sandbox.py` — CommandValidator (dangerous patterns, SSRF, classification)
- `tests/test_sandbox_paths.py` — PathValidator (Windows + Linux paths)
- `tests/test_sandbox_env.py` — EnvironmentSanitizer (key stripping)
- Manual: login flow, token expiry, WebSocket auth, API key auth on external endpoints
