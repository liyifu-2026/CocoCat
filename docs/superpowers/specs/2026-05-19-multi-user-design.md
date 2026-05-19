# Multi-User Architecture Design

**Date:** 2026-05-19
**Status:** Approved

## Overview

CocoCat currently has a single global user (hardcoded "admin"). This design adds multi-user
support for small teams, where each user has private data but shares team-wide resources.

**Type:** Home / small-team deployment. All users are administrators with equal permissions.
No open registration — users are created by any existing admin via the settings page.

The first user is created via a frontend initialization wizard on first visit.

## User Model

### Database

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,          -- username, e.g. "alice"
    password_hash TEXT NOT NULL,   -- bcrypt hash
    display_name TEXT DEFAULT '',  -- optional display name
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Initialization

On first startup (no users in DB), the frontend detects this and shows an initialization
wizard: set admin username + password. Backend endpoint creates the user and returns a JWT.
Subsequent visits go to the normal login page.

### Auth Flow

1. `POST /api/auth/login` accepts `{username, password}`
2. Verify bcrypt hash against `users` table
3. Return JWT with `{"sub": "<username>"}`
4. All subsequent requests include `Authorization: Bearer <token>`
5. Middleware extracts `username` from JWT → sets `ctx.user_id`

Fallback: if `JWT_SECRET == "change-me"` and no users exist, auth is skipped (dev mode).

### Password Security

Replace SHA-256 in `auth.py` with bcrypt:

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), stored_hash.encode())
```

Add `bcrypt>=4.0` to `pyproject.toml` dependencies.

Password requirements (small-team, internal — deliberately minimal):
- Minimum 4 characters
- Not whitespace-only
- No uppercase/digit/symbol enforcement
- Frontend shows a soft hint only

## Resource Isolation

### Per-User (private)

| Resource | Storage |
|---|---|
| Chat history | `messages` table, filtered by `user_id` |
| Agent memory/session | `agents/{username}/memory/`, `agents/{username}/sessions/` |
| LLM API Key | `config/users/{username}/auth.json` — personal key overrides shared fallback |
| Model selection | `config/users/{username}/models.json` |
| Personal channels (Coco chat) | `config/users/{username}/channels.json` |

### Shared (team-wide)

| Resource | Storage |
|---|---|
| Scenes | `scenes` table, no user filter. Everyone can create/edit/delete. |
| Scene channels | Shared `channels.json` — one bot per scene, team-wide |
| Cron jobs | Shared records, `created_by` field for attribution. Executes with shared key. |
| Knowledge bases | Shared, no change |
| Resident agents (coco, kb-agent) | Global instances, use shared admin key by default. Users can override their own key. |
| Provider registry (built-in) | Code-defined, global |

### API Key: Layered Fallback

```
User tries to call LLM:
  1. Check config/users/{username}/auth.json  (personal key)
  2. If missing → fallback to config/users/admin/auth.json (shared key)
```

This means admin sets the default provider keys. Individual users can override
with their own keys in the settings page. Personal overrides shared.

## Channel Architecture: Two Layers

```
Scene channels (shared)              Personal channels (independent)
─────────────────────────            ──────────────────────────────
scene:cs:feishu    → 全队一个飞书     alice:main:weixin  → Alice 的私人微信
scene:sales:weixin → 全队一个微信     bob:main:weixin    → Bob 的私人微信
                                      bob:main:web_api   → Bob 的网页聊天
```

### ChannelManager Key Format

Extended to include username:

```
{username}:{target_type}:{target_id}:{channel_type}
```

Examples:
- Scene channel (no user): `*:scene:customer-service:feishu`
- Personal channel: `alice:main:null:weixin`

Personal channel credentials are stored in `config/users/{username}/channels.json`.
Scene channel credentials remain in the global config.

### Auto-Reconnect

On startup, the ChannelManager iterates all users' channel configs and reconnects
every enabled channel across all users. No "active" concept — the service runs persistently,
all channels stay connected.

## Directory Layout

```
config/
  users/
    {username}/
      auth.json          # personal API keys (overrides shared fallback)
      models.json        # personal model preferences
      channels.json      # personal channel tokens

agents/
  admin/                 # migrated from existing agents/
    memory/
    sessions/
  alice/
    memory/
    sessions/
  bob/
    memory/
    sessions/
```

Existing global files are retired and migrated to `config/users/admin/`.
Existing `agents/` sessions migrate to `agents/admin/`.

## User Management

### Directory Lifecycle

- **User created**: `config/users/{username}/` and `agents/{username}/` directories
  are created immediately (not lazily on first login).
- **User deleted**: The user's DB record, config directory, agent directory, and
  all channel instances are deleted immediately. No retention.

### API Endpoints

```
GET    /api/users                        list all users
POST   /api/users                        create user {username, password}
DELETE /api/users/{username}             delete user (cascades: config + agents + channels)
PUT    /api/users/{username}/password    reset password
```

All endpoints require valid JWT. Any authenticated user can manage users.

## Architecture Changes

### 1. ConfigStore → User-Scoped

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

    # cron_dir, skills_dir, residents_dir remain global
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

### 3. ProviderFactory → Layered

Global `ctx.creds` and `ctx.provider_factory` remain for shared operations
(resident agents, cron worker). Per-user LLM calls use user-scoped credentials
with fallback to admin:

```python
def _resolve_llm_for_user(model: str, user_id: str):
    user_cfg = ConfigStore(user_id=user_id)
    creds = CredentialManager(config_store=user_cfg)
    # Fallback: personal key first, then admin key
    if not creds.get(model):
        admin_creds = CredentialManager(config_store=ConfigStore(user_id="admin"))
        # merge — personal overrides admin
    factory = ProviderFactory(credential_manager=creds)
    return factory.create_sync(model)
```

### 4. Chat Route → User-Scoped

```python
@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    msg_store.save(
        user_id=ctx.user_id,  # was hardcoded "local"
        ...
    )
```

### 5. Route Changes Summary

| Endpoint | Change |
|---|---|
| `POST /api/auth/login` | Accept `username`, verify against users table |
| `POST /api/auth/init` | NEW: first-run wizard, create admin user |
| `GET /api/chat/history` | Filter by `ctx.user_id` |
| `GET /api/knowledge/*` | No change |
| `GET /api/scenes/*` | No change |
| `PUT /api/providers/key` | Save to user-scoped ConfigStore |
| `GET /api/providers` | Read from user-scoped ConfigStore |
| `PUT /api/providers/{name}/config` | User-scoped |
| `GET /api/channels/*` | User-scoped for personal, global for scene channels |
| `GET /api/cron/*` | No change, add `created_by` |

## Agent Isolation

Each user gets their own agent directory with independent memory and sessions:

```
agents/{username}/memory/memory.md
agents/{username}/sessions/
```

`load_agent_config()` reads from the user's agent directory.
`run_agent()` works unchanged — it receives a per-user `AgentConfig`.

**No changes** to: `Agent`, `AgentConfig`, `run_agent()`, any tool implementation.

## Migration Path

1. DB migration adds `users` table (no seed row — handled by init wizard)
2. Existing `config/auth.json` → `config/users/admin/auth.json`
3. Existing `agents/` session files → `agents/admin/`
4. On first visit after migration, init wizard prompts for admin credentials
5. Old global config files are deleted after migration

## Edge Cases

- **First run (no users)**: Frontend shows init wizard instead of login page.
  Backend `POST /api/auth/init` creates first admin user.
- **User deleted**: Immediate — DB record, config dir, agent dir, and channel instances
  all removed synchronously.
- **Same channel type, different users**: Each user has an independent channel instance,
  identified by `{username}:{target_type}:{target_id}:{channel_type}` in ChannelManager.
  Separate tokens, separate connections, no interference.
- **Concurrent requests**: Agent calls are stateless and parallel-safe.
  SQLite serialized writes — acceptable for small-team scale.
- **Auth disabled (dev mode)**: If no users exist and `JWT_SECRET == "change-me"`,
  auth middleware is skipped entirely (current behavior preserved).

## What Does NOT Change

- Agent execution (`run_agent`, `_make_and_run_agent`)
- Tool system (`ToolCatalog`, all tools)
- Knowledge base system
- Scene system (shared, all users equal access)
- Cron worker (adds `created_by` field only)
- WebUI structure (adds user management section, init wizard page)
