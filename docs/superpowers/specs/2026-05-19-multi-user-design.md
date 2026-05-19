# Multi-User Architecture Design

**Date:** 2026-05-19
**Status:** Draft

## Overview

CocoCat currently has a single global user (hardcoded "admin"). This design adds multi-user
support for small teams, where each user has private data but shares team-wide resources.

**Type:** Home / small-team deployment. All users are administrators with equal permissions.
No open registration — users are created by any existing admin via the settings page.

## User Model

### Database

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,          -- username, e.g. "alice"
    password_hash TEXT NOT NULL,   -- bcrypt hash
    display_name TEXT DEFAULT '',  -- optional display name
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seed the default admin user
INSERT OR IGNORE INTO users (id, password_hash, display_name)
VALUES ('admin', '<hash>', 'Admin');
```

### Auth Flow

1. `POST /api/auth/login` accepts `{username, password}`
2. Verify against `users` table
3. Return JWT with `{"sub": "<username>"}`
4. All subsequent requests include `Authorization: Bearer <token>`
5. Middleware extracts `username` from JWT → injects into `AppContext`

Fallback: if `JWT_SECRET == "change-me"` and no users exist, auth is skipped (current behavior preserved for first-run / dev mode).

### Password Security

Replace the current SHA-256 hashing in `auth.py:44-49` with bcrypt:

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), stored_hash.encode())
```

Add `bcrypt>=4.0` to `pyproject.toml` dependencies.

Password requirements (small-team, internal deployment — deliberately minimal):
- Minimum 4 characters
- Not whitespace-only
- No uppercase/digit/symbol enforcement
- Frontend shows a soft hint, no hard block

## Resource Isolation

| Resource | Scope | Storage |
|---|---|---|
| Chat history | **per-user** | `messages` table filtered by `user_id` |
| Agent memory/session | **per-user** | `agents/{username}/memory/` |
| LLM API Key | **per-user** | `config/users/{username}/auth.json` |
| Model selection | **per-user** | `config/users/{username}/models.json` |
| Channel config (WeChat, etc.) | **per-user** | `config/users/{username}/channels.json` |
| Scenes | **shared** | `scenes` table, no user filter |
| Cron jobs | **shared** | `cron` records, `created_by` field |
| Provider registry (built-in) | **shared** | code-defined, global |

## Directory Layout

```
config/
  users/
    {username}/
      auth.json          # personal API keys
      models.json        # personal model prefs
      channels.json      # personal channel tokens

agents/
  {username}/
    memory/              # personal memory + session
    sessions/            # personal chat sessions
```

The existing global files (`config/auth.json`, `config/models.json`, etc.) are retired.
On first startup after migration, existing data migrates to `config/users/admin/`.

## Architecture Changes

### 1. ConfigStore → User-Scoped

`ConfigStore` gains an optional `user_id` parameter. When set, all paths resolve to
`config/users/{user_id}/...`. When `None`, global paths are used (for scene configs, etc.).

```python
class ConfigStore:
    def __init__(self, user_id: str | None = None):
        self._user_id = user_id
        self._base = Path("config") if user_id is None else Path(f"config/users/{user_id}")

    @property
    def auth_path(self) -> Path:
        return self._base / "auth.json"

    @property
    def models_path(self) -> Path:
        return self._base / "models.json"

    @property
    def channels_path(self) -> Path:
        return self._base / "channels.json"

    # cron_dir, skills_dir, residents_dir remain global (not user-scoped)
    @property
    def cron_dir(self) -> Path:
        return Path("runs/cron")
```

### 2. AppContext → User Injection

```python
@dataclass
class AppContext:
    user_id: str | None = None      # NEW: extracted from JWT
    db: Database = field(default=None)
    ...
```

Middleware extracts `username` from JWT → sets `ctx.user_id`.

### 3. ProviderFactory → Per-Request

No longer created once at startup. Instead, created per-request with user-scoped credentials:

```python
# In sandbox executor (or wherever LLM is resolved)
def _resolve_llm_for_user(agent_id: str, user_id: str):
    creds = CredentialManager(config_store=ConfigStore(user_id=user_id))
    factory = ProviderFactory(credential_manager=creds)
    return factory.create_sync(model)
```

The global `ctx.creds` and `ctx.provider_factory` remain for shared operations (cron worker, etc.),
but per-user LLM calls use user-scoped instances.

### 4. Chat Route → User-Scoped

```python
@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    msg_store.save(
        ...
        user_id=ctx.user_id,  # was hardcoded "local"
        ...
    )
    # LLM resolution uses user-scoped credentials
```

### 5. User Management API

```
GET    /api/users               list all users
POST   /api/users               create user {username, password}
DELETE /api/users/{username}    delete user
PUT    /api/users/{username}/password   reset password
```

All endpoints require valid JWT (any authenticated user can manage users).

### 6. Existing API Endpoints

| Endpoint | Change |
|---|---|
| `POST /api/auth/login` | Accept `username` field, verify against users table |
| `GET /api/chat/history` | Filter by `ctx.user_id` |
| `GET /api/knowledge/*` | No change (KB is shared) |
| `GET /api/scenes/*` | No change (scenes are shared) |
| `GET /api/cron/*` | No change (cron is shared, add `created_by`) |
| `PUT /api/providers/key` | Save to user-scoped ConfigStore |
| `GET /api/providers` | Read from user-scoped ConfigStore |
| `PUT /api/providers/{name}/config` | User-scoped |
| `GET /api/channels/*` | User-scoped |

## Agent Isolation

Each user gets their own agent directory:

```
agents/{username}/memory/memory.md  (user's memory)
agents/{username}/sessions/         (user's chat sessions)
```

`load_agent_config()` reads from the user's directory. `run_agent()` works unchanged — it
receives a per-user `AgentConfig` with the user's own `agent_dir`.

No changes to `Agent`, `AgentConfig`, `run_agent()`, or any tool implementations.

## Migration Path

1. New DB migration adds `users` table, seeds `admin` user
2. Existing `config/auth.json` → `config/users/admin/auth.json` (copy)
3. Existing `agents/` session files → start fresh per user (or migrate if needed)
4. Old global paths are deleted (or left as inert)

## Edge Cases

- **User deleted**: agent directory and config remain on disk for recovery. DB anchor deleted.
- **Same channel type, different users**: OK — each user has their own channel credentials file.
  Channel credentials are stored per-user, not globally.
- **Concurrent requests**: Agent calls are stateless and parallel-safe. DB is SQLite (serialized
  writes) — acceptable for small-team use.

## What Does NOT Change

- Agent execution (`run_agent`, `_make_and_run_agent`)
- Tool system (`ToolCatalog`, all tools)
- Knowledge base system
- Scene system
- Cron worker (adds `created_by` field only)
- WebUI structure (adds user management tab/section)
