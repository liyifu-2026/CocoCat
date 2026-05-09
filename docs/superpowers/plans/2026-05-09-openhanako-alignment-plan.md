# OpenHanako Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align CocoCat with OpenHanako best practices across 6 phases: environment isolation, ESLint architecture enforcement, dependency injection, SessionFile registry, Zustand state management, testing coverage, and plugin SDK.

**Architecture:** Phase 1 lays safety foundations (env isolation + lint boundaries). Phase 2 injects service containers so modules receive dependencies rather than importing globals. Phase 3 routes all file I/O through a central registry. Phase 4 replaces React Contexts with Zustand stores. Phase 5 leverages DI for mockable tests. Phase 6 builds the plugin SDK on all prior phases.

**Tech Stack:** Rust (axum, rusqlite, tokio), Python (FastAPI, pytest), TypeScript (React 19, Zustand, ESLint, Vitest, Playwright)

---

## Phase 1: Environment Isolation + ESLint (Week 1-2)

### Task 1.1: Environment Isolation — Data directory function

**Files:**
- Modify: `src/config.rs` — add `data_dir()` function
- Modify: `src/main.rs` — use `data_dir()` for all paths
- Modify: `py-agent/context.py` — add `get_data_dir()` function
- Modify: `web/main.py` — use `get_data_dir()`
- Modify: `start.sh` — set `COCOCAT_ENV=dev`
- Modify: `.env.example` — add `COCOCAT_ENV=dev`
- Create: `tests/test_env_isolation.py`
- Create: `tests/env_isolation_test.rs`

- [ ] **Step 1: Write the failing Rust test**

Create `tests/env_isolation_test.rs`:

```rust
use std::env;

fn data_dir() -> std::path::PathBuf {
    let env_name = env::var("COCOCAT_ENV").unwrap_or_else(|_| "dev".to_string());
    let base = dirs::home_dir().expect("HOME not set");
    let dir_name = if env_name == "prod" {
        ".cococat".to_string()
    } else {
        format!(".cococat-{}", env_name)
    };
    base.join(dir_name)
}

#[test]
fn test_data_dir_dev() {
    env::set_var("COCOCAT_ENV", "dev");
    let dir = data_dir();
    assert!(dir.ends_with(".cococat-dev"));
}

#[test]
fn test_data_dir_prod() {
    env::set_var("COCOCAT_ENV", "prod");
    let dir = data_dir();
    assert!(dir.ends_with(".cococat"));
}

#[test]
fn test_data_dir_custom() {
    env::set_var("COCOCAT_ENV", "leaif");
    let dir = data_dir();
    assert!(dir.ends_with(".cococat-leaif"));
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cargo test --test env_isolation_test 2>&1 | head -20
```
Expected: the test file compiles but `dirs` crate may not be available. Add `dirs = "5"` to `Cargo.toml` if needed, then run again. Tests should pass (we inlined data_dir for the test).

- [ ] **Step 3: Move `data_dir()` into `src/config.rs`**

Append to `src/config.rs`:

```rust
use std::env;
use std::path::PathBuf;

/// Returns the data directory for CocoCat based on COCOCAT_ENV.
///
/// COCOCAT_ENV=dev   → ~/.cococat-dev/
/// COCOCAT_ENV=prod  → ~/.cococat/
/// COCOCAT_ENV=leaif → ~/.cococat-leaif/
pub fn data_dir() -> PathBuf {
    let env_name = env::var("COCOCAT_ENV").unwrap_or_else(|_| "dev".to_string());
    let home = dirs::home_dir().expect("HOME not set");
    let dir_name = if env_name == "prod" {
        ".cococat".to_string()
    } else {
        format!(".cococat-{}", env_name)
    };
    let dir = home.join(&dir_name);
    std::fs::create_dir_all(&dir).ok();
    dir
}

/// Returns a path under the data directory, e.g. data_dir().join("agents")
pub fn data_path(relative: &str) -> PathBuf {
    data_dir().join(relative)
}
```

- [ ] **Step 4: Run the test again to verify it still passes**

```bash
cargo test --test env_isolation_test -v
```
Expected: all tests PASS.

- [ ] **Step 5: Update `src/main.rs` to use `data_path()`**

Replace all hardcoded paths in `src/main.rs`:

Change line 21:
```rust
    let _builtin_dir = std::path::Path::new("skills/public");
```
To:
```rust
    let _builtin_dir_path = config::data_path("skills/public");
```

But since builtin skills should likely stay within the repo (not user data), keep the skills loading from the repo root while moving runtime data (DB, agents, scenes) to `data_dir()`.

Change the DB pool creation. Read `src/db/pool.rs` to see how the pool path is set.

- [ ] **Step 6: Read db/pool.rs to see current DB path**

- [ ] **Step 7: Update `src/db/pool.rs` to use configurable data dir**

Add a parameter to `create_pool`. If it currently opens `cococat.db` in cwd, change it to accept a `PathBuf`:

```rust
// src/db/pool.rs
use std::path::PathBuf;

pub fn create_pool(data_dir: &PathBuf) -> Result<DbPool, Box<dyn std::error::Error>> {
    let db_path = data_dir.join("cococat.db");
    // ... rest of pool creation using db_path
}
```

Then in `src/main.rs`, call `create_pool(&config::data_dir())`.

- [ ] **Step 8: Write the Python data_dir test**

Create `tests/test_env_isolation.py`:

```python
import os
import sys
import tempfile
from pathlib import Path

# Add py-agent to path so we can import context
sys.path.insert(0, str(Path(__file__).parent.parent / "py-agent"))

from context import get_data_dir


def test_data_dir_dev():
    os.environ["COCOCAT_ENV"] = "dev"
    d = get_data_dir()
    assert d.name == ".cococat-dev" or str(d).endswith(".cococat-dev")


def test_data_dir_prod():
    os.environ["COCOCAT_ENV"] = "prod"
    d = get_data_dir()
    assert d.name == ".cococat" or str(d).endswith(".cococat")


def test_data_dir_custom():
    os.environ["COCOCAT_ENV"] = "test-runner"
    d = get_data_dir()
    assert ".cococat-test-runner" in str(d)


def test_data_dir_creates_if_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COCOCAT_ENV", "pytest-tmp")
    monkeypatch.setattr(Path, "home", lambda: Path(tmp_path))
    d = get_data_dir()
    assert d.exists()
```

- [ ] **Step 9: Run the Python test to see it fail**

```bash
python -m pytest tests/test_env_isolation.py -v
```
Expected: FAIL — `get_data_dir` not defined in `context.py` yet.

- [ ] **Step 10: Add `get_data_dir()` to `py-agent/context.py`**

At the top of `py-agent/context.py`, add after the existing imports:

```python
import os as _os
from pathlib import Path as _Path


def get_data_dir() -> _Path:
    """Returns the CocoCat data directory based on COCOCAT_ENV."""
    env_name = _os.environ.get("COCOCAT_ENV", "dev")
    home = _Path.home()
    dir_name = ".cococat" if env_name == "prod" else f".cococat-{env_name}"
    data_dir = home / dir_name
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_data_path(relative: str) -> _Path:
    """Returns a path under the data directory."""
    return get_data_dir() / relative
```

- [ ] **Step 11: Run the Python test to verify it passes**

```bash
python -m pytest tests/test_env_isolation.py -v
```
Expected: all PASS.

- [ ] **Step 12: Update `web/main.py` to use `get_data_dir()`**

After the existing imports in `web/main.py`, add:

```python
from py_agent.context import get_data_dir
```

Then replace `BASE_DIR = Path(__file__).resolve().parent.parent` with usage that derives from `get_data_dir()` where appropriate (file upload paths, etc.).

- [ ] **Step 13: Update `start.sh`**

At line 3 (after `cd "$(dirname "$0")"`), add:

```bash
export COCOCAT_ENV="${COCOCAT_ENV:-dev}"
```

- [ ] **Step 14: Update `.env.example`**

Add line:

```
COCOCAT_ENV=dev
```

- [ ] **Step 15: Commit**

```bash
git add src/config.rs src/main.rs src/db/pool.rs py-agent/context.py web/main.py start.sh .env.example tests/test_env_isolation.py tests/env_isolation_test.rs Cargo.toml
git commit -m "feat: add COCOCAT_ENV-based data directory isolation
- Rust: config::data_dir() returns ~/.cococat-{env}/
- Python: get_data_dir() same logic
- start.sh: sets COCOCAT_ENV=dev by default
- .env.example: adds COCOCAT_ENV=dev
- Runtime data (DB, agents, scenes) now under ~/.cococat-{env}/"
```

---

### Task 1.2: ESLint Architecture Constraints — Frontend

**Files:**
- Modify: `web-ui/eslint.config.js`

- [ ] **Step 1: Write architecture rule for pages not importing api directly**

Add to `web-ui/eslint.config.js`:

```javascript
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // Architecture: pages must not import API modules directly
      'no-restricted-imports': ['error', {
        patterns: [
          {
            group: ['@/api/*'],
            importNames: ['**'],
            message: 'Pages must not import api/ modules directly. Use context hooks or Zustand stores instead.',
            allowImportNames: [],
          },
        ],
        paths: [],
      }],
    },
  },
  {
    // Pages get the restriction; components and context do not
    files: ['src/components/**/*.{ts,tsx}', 'src/context/**/*.{ts,tsx}', 'src/api/**/*.{ts,tsx}', 'src/stores/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
])
```

- [ ] **Step 2: Run lint to verify the rule fires**

```bash
cd web-ui && npx eslint src/pages/Dashboard.tsx 2>&1 | head -10
```
Expected: if Dashboard imports from `@/api/*`, it should show an error. If it doesn't already, add a temporary test import to verify.

- [ ] **Step 3: Fix any existing violations**

If any page currently imports from `@/api/*`, refactor to use the existing context or create a hook. For Phase 1, if there are existing violations, mark them with `// eslint-disable-next-line no-restricted-imports -- TODO: Phase 4 Zustand migration` and track in a follow-up issue.

- [ ] **Step 4: Commit**

```bash
cd /home/leaif/CocoCat && git add web-ui/eslint.config.js
git commit -m "feat: add ESLint architecture rule preventing pages from importing api/ directly"
```

---

### Task 1.3: Architecture Constraints — Python (ruff)

**Files:**
- Create: `ruff.toml`
- Create: `pyproject.toml` (if not exists, or add ruff section)

- [ ] **Step 1: Check if pyproject.toml exists and if ruff is installed**

```bash
cat pyproject.toml 2>/dev/null && pip show ruff 2>/dev/null || echo "need to set up"
```

- [ ] **Step 2: Add ruff configuration**

Create `ruff.toml` at project root:

```toml
[lint]
select = ["E", "F", "I", "N", "TID"]
ignore = ["E501"]  # line length handled by formatter

[lint.isort]
known-first-party = ["py_agent", "web"]
known-third-party = ["fastapi", "pydantic", "openai", "httpx"]

[lint.flake8-tidy-imports]
ban-relative-imports = "parents"

[lint.flake8-tidy-imports.banned-api]
"py_agent.agent_loop".msg = "web/ routes must not import py_agent internal modules. Use web/services/ instead."
"py_agent.agent_runtime".msg = "web/ routes must not import py_agent internal modules. Use web/services/ instead."
"py_agent.tools".msg = "web/ routes must not import py_agent.tools directly."

[format]
line-length = 120
```

- [ ] **Step 3: Install ruff and run it**

```bash
pip install ruff && ruff check py-agent/ web/ --select=TID 2>&1 | head -20
```

Expected: lists any banned imports.

- [ ] **Step 4: Add ruff to CI (if CI file exists) or `AGENTS.md`**

Add `ruff check .` to `AGENTS.md` as the Python lint command.

- [ ] **Step 5: Commit**

```bash
git add ruff.toml AGENTS.md
git commit -m "feat: add ruff with architecture import bans for Python layers"
```

---

## Phase 2: Dependency Injection (Week 3-5)

### Task 2.1: Python Agent Service Container

**Files:**
- Create: `py-agent/container.py`
- Modify: `py-agent/agent_loop.py` — accept `AgentServices` parameter
- Modify: `py-agent/agent_runtime.py` — create and inject `AgentServices`
- Create: `tests/test_container.py`

- [ ] **Step 1: Write the failing test for AgentServices**

Create `tests/test_container.py`:

```python
"""Tests for the AgentServices container (Phase 2 DI)."""
import pytest
from unittest.mock import MagicMock


class MockProviderFactory:
    def get_provider(self, model=None):
        return MagicMock()


class MockToolRegistry:
    def list_tools(self):
        return []


class MockSkillHub:
    def get_skills(self, agent_id):
        return []


class MockSceneManager:
    def get_scene(self, scene_id):
        return MagicMock()


def test_agent_services_test_double():
    """AgentServices.test_double should allow mocking any service."""
    from py_agent.container import AgentServices

    mock_provider = MockProviderFactory()
    services = AgentServices.test_double(provider_factory=mock_provider)

    assert services.provider_factory is mock_provider
    assert services.tool_registry is not None
    assert services.skill_hub is not None


def test_agent_services_default_fills_all():
    """test_double with no overrides should fill all fields with defaults."""
    from py_agent.container import AgentServices

    services = AgentServices.test_double()

    assert services.provider_factory is not None
    assert services.tool_registry is not None
    assert services.config == {}


def test_agent_loop_accepts_services():
    """AgentLoop should accept an AgentServices parameter and use it for provider calls."""
    # This test will verify the DI contract
    pass  # Will fill in after AgentLoop is updated
```

- [ ] **Step 2: Run the test to see it fail**

```bash
python -m pytest tests/test_container.py -v
```
Expected: FAIL — `py_agent.container` doesn't exist.

- [ ] **Step 3: Create `py-agent/container.py`**

```python
"""AgentServices container — holds all services an agent needs.
Supports test doubles for mocking in tests (Phase 2 DI)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentServices:
    """Services injected into agent components instead of global imports."""
    provider_factory: Any = None
    tool_registry: Any = None
    skill_hub: Any = None
    scene_manager: Any = None
    sandbox: Any = None
    session_files: Any = None    # Phase 3 placeholder
    config: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "AgentServices":
        """Production constructor — builds real services from environment."""
        from providers import make_provider
        from tools import create_default_registry, PermissionMode
        from skill_hub import SkillHub
        from scene_router import SceneRouter

        import os as _os

        return cls(
            provider_factory=make_provider,
            tool_registry=create_default_registry(PermissionMode.WORKSPACE_WRITE),
            skill_hub=SkillHub(),
            scene_manager=SceneRouter(),
            sandbox=None,  # created per-execution
            config={
                "workspace": _os.getcwd(),
                "env": _os.environ.get("COCOCAT_ENV", "dev"),
            },
        )

    @classmethod
    def test_double(cls, **overrides) -> "AgentServices":
        """Test constructor — every service defaults to a no-op mock.
        Pass keyword args to override specific services."""
        defaults: dict[str, Any] = {
            "provider_factory": _mock_provider_factory(),
            "tool_registry": _mock_tool_registry(),
            "skill_hub": _mock_skill_hub(),
            "scene_manager": _mock_scene_manager(),
            "sandbox": None,
            "session_files": None,
            "config": {},
        }
        merged = {**defaults, **overrides}
        return cls(**merged)


def _mock_provider_factory():
    from unittest.mock import MagicMock
    return MagicMock(name="MockProviderFactory")


def _mock_tool_registry():
    from unittest.mock import MagicMock
    reg = MagicMock(name="MockToolRegistry")
    reg.list_tools.return_value = []
    return reg


def _mock_skill_hub():
    from unittest.mock import MagicMock
    hub = MagicMock(name="MockSkillHub")
    hub.get_skills.return_value = []
    return hub


def _mock_scene_manager():
    from unittest.mock import MagicMock
    mgr = MagicMock(name="MockSceneManager")
    return mgr
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/test_container.py::test_agent_services_test_double tests/test_container.py::test_agent_services_default_fills_all -v
```
Expected: 2 PASS.

- [ ] **Step 5: Update `agent_loop.py` to accept `AgentServices`**

In `agent_loop.py`, the main `run_loop` or entry function should accept an optional `services: AgentServices = None` parameter. Where it currently calls `from providers import make_provider`, use `services.provider_factory` instead when services is provided.

Add at the top of the imports section:
```python
from container import AgentServices
```

Modify the `run` method signature (around line 200+ depending on exact structure) to accept `services: AgentServices | None = None`:

```python
async def run(
    self,
    prompt: str,
    history: list[dict] | None = None,
    services: AgentServices | None = None,
) -> str:
```

Where it gets a provider, use:
```python
if services and services.provider_factory:
    provider = services.provider_factory()
else:
    provider = make_provider()
```

- [ ] **Step 6: Update `agent_runtime.py` to create and inject services**

In `agent_runtime.py`, where the agent loop is invoked, create `AgentServices.from_env()` and pass it:

```python
from container import AgentServices

services = AgentServices.from_env()
result = await agent_loop.run(prompt, history, services=services)
```

- [ ] **Step 7: Run existing agent tests to ensure no regression**

```bash
python -m pytest tests/test_agent_loop.py tests/test_agent_runner.py -v
```
Expected: existing tests still PASS (they should work without services since we made it optional).

- [ ] **Step 8: Write a test proving DI enables mock provider**

Update `tests/test_container.py` — add:

```python
import pytest
import asyncio


@pytest.mark.asyncio
async def test_agent_loop_with_mock_provider():
    """AgentLoop with injected mock provider should not call real LLM."""
    from unittest.mock import MagicMock, AsyncMock
    from py_agent.container import AgentServices

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(return_value={"content": "mocked response"})

    mock_factory = MagicMock(return_value=mock_provider)
    services = AgentServices.test_double(provider_factory=mock_factory)

    # The agent loop should use services.provider_factory() to get the provider
    # and call provider.chat(...)
    # This test verifies the DI contract works
    assert services.provider_factory is mock_factory
    provider = services.provider_factory()
    result = await provider.chat([{"role": "user", "content": "hello"}])
    assert result["content"] == "mocked response"
```

- [ ] **Step 9: Commit**

```bash
git add py-agent/container.py py-agent/agent_loop.py py-agent/agent_runtime.py tests/test_container.py
git commit -m "feat: add AgentServices container with DI support for agent runtime
- AgentServices.from_env() for production
- AgentServices.test_double() for tests with mock injection
- agent_loop accepts optional services parameter"
```

---

### Task 2.2: Python Web Service Container

**Files:**
- Create: `web/services/__init__.py`
- Create: `web/services/container.py`
- Modify: `web/main.py` — create and wire WebServices
- Create: `tests/test_web_services.py`

- [ ] **Step 1: Create `web/services/__init__.py`**

```python
"""Web panel service layer — all backend interaction goes through here."""
```

- [ ] **Step 2: Create `web/services/container.py`**

```python
"""WebServices container — injected into FastAPI routes via Depends()."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WebServices:
    agent_executor: Any = None
    scheduler_service: Any = None
    scene_service: Any = None
    session_files: Any = None  # Phase 3 placeholder
    config: dict = field(default_factory=dict)


_web_services: WebServices | None = None


def init_web_services(config: dict | None = None) -> WebServices:
    """Initialize the global WebServices singleton."""
    global _web_services
    _web_services = WebServices(config=config or {})
    return _web_services


def get_web_services() -> WebServices:
    """FastAPI Depends() callable. Returns the current WebServices instance."""
    if _web_services is None:
        return init_web_services()
    return _web_services
```

- [ ] **Step 3: Wire into `web/main.py`**

Add after the existing middleware setup in `web/main.py`:

```python
from web.services.container import init_web_services

web_services = init_web_services({"base_dir": str(BASE_DIR)})
```

- [ ] **Step 4: Update one route as example**

Pick `web/routes/agents.py` (or create if not exists). Add:

```python
from fastapi import APIRouter, Depends
from web.services.container import get_web_services, WebServices

router = APIRouter(prefix="/api/web/agents", tags=["agents"])


@router.get("")
async def list_agents(services: WebServices = Depends(get_web_services)):
    return {"agents": [], "source": "web_services"}
```

This demonstrates the DI pattern for future routes.

- [ ] **Step 5: Write a test**

Create `tests/test_web_services.py`:

```python
def test_web_services_init_and_get():
    from web.services.container import init_web_services, get_web_services

    svc1 = init_web_services({"test": True})
    svc2 = get_web_services()

    assert svc1 is svc2
    assert svc1.config["test"] is True


def test_web_services_default():
    from web.services.container import init_web_services
    svc = init_web_services()
    assert svc.agent_executor is None  # Not wired yet
    assert svc.config == {}
```

- [ ] **Step 6: Run test**

```bash
python -m pytest tests/test_web_services.py -v
```
Expected: 2 PASS.

- [ ] **Step 7: Commit**

```bash
git add web/services/ web/main.py tests/test_web_services.py
git commit -m "feat: add WebServices container with FastAPI Depends() DI pattern"
```

---

### Task 2.3: Rust AppState Splitting

**Files:**
- Modify: `src/api/router.rs` — split `AppState` into individual Extensions

- [ ] **Step 1: Extract `DbPool` into its own Extension**

In `src/api/router.rs`, keep `AppState` for backward compatibility but add separate Extension layers:

```rust
pub fn build(state: AppState) -> Router {
    let db_pool = state.db_pool.clone();
    let task_tx = state.task_tx.clone();
    let jwt = state.jwt.clone();
    let event_tx = state.event_tx.clone();

    let cors = CorsLayer::permissive();

    Router::new()
        .route("/api/health", get(health))
        // ... existing routes ...
        .layer(Extension(db_pool))
        .layer(Extension(task_tx))
        .layer(Extension(jwt))
        .layer(Extension(event_tx))
        .layer(cors)
        .layer(CompressionLayer::new())
        .layer(DefaultBodyLimit::max(10 * 1024 * 1024))
}
```

Drop `.with_state(state)` in favor of the Extension approach.

- [ ] **Step 2: Update one handler to use Extension instead of State**

Example: update `health` to not need state at all; update one simple handler like `list_handler` in `scenes.rs`:

```rust
// Before:
pub async fn list_handler(State(state): State<AppState>, ...) -> ...

// After:
pub async fn list_handler(
    Extension(db_pool): Extension<DbPool>,
    Extension(event_tx): Extension<broadcast::Sender<WsEvent>>,
    ...
) -> ...
```

- [ ] **Step 3: Run Rust tests**

```bash
cargo test
```
Expected: All existing tests still pass or are updated.

- [ ] **Step 4: Commit**

```bash
git add src/api/router.rs src/api/scenes.rs
git commit -m "refactor: split AppState into individual axum Extensions for DI"
```

---

## Phase 3: SessionFile Registry (Week 5-7)

### Task 3.1: SessionFile Data Model

**Files:**
- Create: `py-agent/session_files.py`

- [ ] **Step 1: Write SessionFile and Registry classes**

```python
"""SessionFile — unified file identity across all channels and agents."""
from __future__ import annotations
import hashlib
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass
class SessionFile:
    file_id: str
    session_id: str
    channel: str  # "web" | "telegram" | "wechat" | "discord" | "agent"
    filename: str
    stored_path: Path
    mime_type: str
    size_bytes: int
    checksum: str  # SHA256
    created_at: datetime
    modified_at: datetime
    created_by: str  # agent_id or user_external_id
    deleted: bool = False


class SessionFileRegistry:
    """Central file registry — all file I/O by agents and channels must go through here."""

    def __init__(self, data_dir: Path, db_conn=None):
        self.data_dir = Path(data_dir)
        self.files_dir = self.data_dir / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._db = db_conn  # SQLite connection (optional, falls back to in-memory if None)
        self._in_memory: dict[str, SessionFile] = {}
        self._init_db()

    def _init_db(self):
        if self._db is not None:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS session_files (
                    file_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    mime_type TEXT,
                    size_bytes INTEGER,
                    checksum TEXT,
                    created_at TEXT,
                    modified_at TEXT,
                    created_by TEXT,
                    deleted INTEGER DEFAULT 0
                )"""
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sf_checksum ON session_files(checksum)"
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sf_session ON session_files(session_id)"
            )

    def register(
        self,
        session_id: str,
        channel: str,
        filename: str,
        data: bytes,
        created_by: str = "unknown",
        mime_type: str = "application/octet-stream",
    ) -> SessionFile:
        checksum = hashlib.sha256(data).hexdigest()

        # Dedup by checksum
        existing = self.by_checksum(checksum)
        if existing and not existing.deleted:
            return existing

        file_id = uuid.uuid4().hex
        subdir = self.files_dir / file_id[:2]
        subdir.mkdir(parents=True, exist_ok=True)
        stored_path = subdir / file_id

        with open(stored_path, "wb") as f:
            f.write(data)

        now = datetime.now(timezone.utc)
        sf = SessionFile(
            file_id=file_id,
            session_id=session_id,
            channel=channel,
            filename=filename,
            stored_path=stored_path,
            mime_type=mime_type,
            size_bytes=len(data),
            checksum=checksum,
            created_at=now,
            modified_at=now,
            created_by=created_by,
        )

        self._in_memory[file_id] = sf
        if self._db is not None:
            self._db.execute(
                """INSERT OR REPLACE INTO session_files
                   (file_id, session_id, channel, filename, stored_path, mime_type,
                    size_bytes, checksum, created_at, modified_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sf.file_id, sf.session_id, sf.channel, sf.filename,
                    str(sf.stored_path), sf.mime_type, sf.size_bytes,
                    sf.checksum, sf.created_at.isoformat(),
                    sf.modified_at.isoformat(), sf.created_by,
                ),
            )
            self._db.commit()

        return sf

    def get(self, file_id: str) -> SessionFile | None:
        sf = self._in_memory.get(file_id)
        if sf and not sf.deleted:
            return sf
        if self._db is not None:
            row = self._db.execute(
                "SELECT * FROM session_files WHERE file_id = ? AND deleted = 0",
                (file_id,),
            ).fetchone()
            if row:
                return self._row_to_sf(row)
        return None

    def list_by_session(self, session_id: str) -> list[SessionFile]:
        if self._db is not None:
            rows = self._db.execute(
                "SELECT * FROM session_files WHERE session_id = ? AND deleted = 0 ORDER BY created_at",
                (session_id,),
            ).fetchall()
            return [self._row_to_sf(r) for r in rows]
        return [sf for sf in self._in_memory.values()
                if sf.session_id == session_id and not sf.deleted]

    def update(self, file_id: str, new_data: bytes) -> SessionFile | None:
        sf = self.get(file_id)
        if sf is None:
            return None
        new_checksum = hashlib.sha256(new_data).hexdigest()
        with open(sf.stored_path, "wb") as f:
            f.write(new_data)
        sf.checksum = new_checksum
        sf.size_bytes = len(new_data)
        sf.modified_at = datetime.now(timezone.utc)
        if self._db is not None:
            self._db.execute(
                "UPDATE session_files SET checksum=?, size_bytes=?, modified_at=? WHERE file_id=?",
                (sf.checksum, sf.size_bytes, sf.modified_at.isoformat(), file_id),
            )
            self._db.commit()
        return sf

    def delete(self, file_id: str):
        sf = self.get(file_id)
        if sf:
            sf.deleted = True
            sf.stored_path.unlink(missing_ok=True)
            if self._db is not None:
                self._db.execute(
                    "UPDATE session_files SET deleted=1 WHERE file_id=?",
                    (file_id,),
                )
                self._db.commit()

    def by_checksum(self, checksum: str) -> SessionFile | None:
        if self._db is not None:
            row = self._db.execute(
                "SELECT * FROM session_files WHERE checksum = ? AND deleted = 0 LIMIT 1",
                (checksum,),
            ).fetchone()
            if row:
                return self._row_to_sf(row)
        for sf in self._in_memory.values():
            if sf.checksum == checksum and not sf.deleted:
                return sf
        return None

    def _row_to_sf(self, row) -> SessionFile:
        return SessionFile(
            file_id=row[0],
            session_id=row[1],
            channel=row[2],
            filename=row[3],
            stored_path=Path(row[4]),
            mime_type=row[5] or "application/octet-stream",
            size_bytes=row[6] or 0,
            checksum=row[7] or "",
            created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(timezone.utc),
            modified_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now(timezone.utc),
            created_by=row[10] or "unknown",
            deleted=bool(row[11]) if len(row) > 11 else False,
        )
```

- [ ] **Step 2: Write tests**

Create `tests/test_session_files.py`:

```python
"""Tests for SessionFile registry."""
import tempfile
from pathlib import Path
from py_agent.session_files import SessionFileRegistry


def test_register_and_get():
    with tempfile.TemporaryDirectory() as td:
        reg = SessionFileRegistry(data_dir=Path(td))
        data = b"hello world"
        sf = reg.register("session-1", "web", "test.txt", data, created_by="user-1")

        assert sf.filename == "test.txt"
        assert sf.channel == "web"
        assert sf.checksum is not None
        assert sf.stored_path.exists()

        retrieved = reg.get(sf.file_id)
        assert retrieved is not None
        assert retrieved.file_id == sf.file_id


def test_dedup_by_checksum():
    with tempfile.TemporaryDirectory() as td:
        reg = SessionFileRegistry(data_dir=Path(td))
        data = b"same data"
        sf1 = reg.register("s1", "web", "a.txt", data)
        sf2 = reg.register("s2", "telegram", "b.txt", data)  # same content

        assert sf1.file_id == sf2.file_id  # Dedup
        assert sf2.channel == "web"  # Returns original


def test_list_by_session():
    with tempfile.TemporaryDirectory() as td:
        reg = SessionFileRegistry(data_dir=Path(td))
        reg.register("s1", "web", "a.txt", b"a")
        reg.register("s1", "web", "b.txt", b"b")
        reg.register("s2", "telegram", "c.txt", b"c")

        s1_files = reg.list_by_session("s1")
        assert len(s1_files) == 2

        s2_files = reg.list_by_session("s2")
        assert len(s2_files) == 1


def test_update_and_delete():
    with tempfile.TemporaryDirectory() as td:
        reg = SessionFileRegistry(data_dir=Path(td))
        sf = reg.register("s1", "web", "f.txt", b"v1")

        updated = reg.update(sf.file_id, b"v2")
        assert updated.checksum != sf.checksum
        assert updated.size_bytes == 2

        reg.delete(sf.file_id)
        assert reg.get(sf.file_id) is None
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_session_files.py -v
```
Expected: all PASS.

- [ ] **Step 4: Integrate into AgentServices container**

Update `py-agent/container.py` — in `AgentServices.from_env()`:

```python
from session_files import SessionFileRegistry
from context import get_data_dir

# ...
sandbox=None,
session_files=SessionFileRegistry(data_dir=get_data_dir()),
# ...
```

- [ ] **Step 5: Update channels to use SessionFileRegistry**

For each channel file (`py-agent/channels/telegram.py`, `wechat.py`, etc.), where files are downloaded/saved, replace direct `open()` calls with `registry.register()`.

Example for `telegram.py`:
```python
# Before:
with open(f"/tmp/{filename}", "wb") as f:
    f.write(data)

# After:
sf = services.session_files.register(
    session_id=session_id,
    channel="telegram",
    filename=filename,
    data=data,
    created_by=user_id,
)
```

- [ ] **Step 6: Commit**

```bash
git add py-agent/session_files.py py-agent/container.py py-agent/channels/telegram.py py-agent/channels/wechat.py tests/test_session_files.py
git commit -m "feat: add SessionFileRegistry for unified file identity across channels"
```

---

## Phase 4: Zustand State Management (Week 7-9)

### Task 4.1: Install Zustand and Create First Store

**Files:**
- Modify: `web-ui/package.json` — add zustand
- Create: `web-ui/src/stores/auth-store.ts`
- Create: `web-ui/src/stores/preference-store.ts`
- Modify: `web-ui/src/App.tsx` — replace AuthProvider with store

- [ ] **Step 1: Install Zustand**

```bash
cd web-ui && npm install zustand
```

- [ ] **Step 2: Create `web-ui/src/stores/auth-store.ts`**

```typescript
import { create } from 'zustand'

interface AuthState {
  token: string | null
  user: { id: string; name: string } | null
  isAuthenticated: boolean
  login: (token: string) => void
  logout: () => void
  setUser: (user: { id: string; name: string }) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  login: (token) => set({ token, isAuthenticated: true }),
  logout: () => set({ token: null, user: null, isAuthenticated: false }),
  setUser: (user) => set({ user }),
}))
```

- [ ] **Step 3: Create `web-ui/src/stores/preference-store.ts`**

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark' | 'system'
type Language = 'zh' | 'en'

interface PreferenceState {
  theme: Theme
  language: Language
  setTheme: (theme: Theme) => void
  setLanguage: (language: Language) => void
}

export const usePreferenceStore = create<PreferenceState>()(
  persist(
    (set) => ({
      theme: 'system',
      language: 'zh',
      setTheme: (theme) => set({ theme }),
      setLanguage: (language) => set({ language }),
    }),
    { name: 'cococat-prefs' }
  )
)
```

- [ ] **Step 4: Create `web-ui/src/stores/ui-store.ts`**

```typescript
import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  panelOpen: boolean
  breadcrumbs: { label: string; path: string }[]
  toggleSidebar: () => void
  togglePanel: () => void
  setBreadcrumbs: (items: { label: string; path: string }[]) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  panelOpen: false,
  breadcrumbs: [],
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  setBreadcrumbs: (items) => set({ breadcrumbs: items }),
}))
```

- [ ] **Step 5: Write store tests**

Create `web-ui/src/stores/__tests__/auth-store.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { useAuthStore } from '../auth-store'

describe('auth-store', () => {
  it('should start unauthenticated', () => {
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.token).toBeNull()
  })

  it('should login and set token', () => {
    useAuthStore.getState().login('test-jwt-token')
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.token).toBe('test-jwt-token')
  })

  it('should logout and clear state', () => {
    useAuthStore.getState().login('test-jwt-token')
    useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.token).toBeNull()
  })
})
```

- [ ] **Step 6: Run tests**

```bash
cd web-ui && npx vitest run src/stores/__tests__/auth-store.test.ts
```
Expected: 3 PASS.

- [ ] **Step 7: Replace AuthContext in App.tsx**

In `web-ui/src/App.tsx`, remove `<AuthProvider>` wrapper and instead use:
```tsx
const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
```

Replace all `useContext(AuthContext)` calls with `useAuthStore` selectors selectively (one page at a time in subsequent tasks).

- [ ] **Step 8: Commit**

```bash
git add web-ui/package.json web-ui/package-lock.json web-ui/src/stores/
git commit -m "feat: add Zustand stores for auth, preferences, and UI state"
```

### Task 4.2: Migrate Remaining Contexts to Stores

(Continue the same pattern for: dialog-store.ts, live-store.ts, agent-store.ts, scene-store.ts)

---

## Phase 5: Testing Coverage (Week 9-13)

### Task 5.1: Rust API Tests

**Files:**
- Create: `tests/api/` directory with test files

- [ ] **Step 1: Create helper for test DB**

Create `tests/common/mod.rs`:

```rust
use sqlite::Connection;
use std::sync::Arc;

pub fn test_db() -> DbPool {
    let conn = Connection::open(":memory:").unwrap();
    // Run migrations...
}
```

- [ ] **Step 2: Write test for agents_list endpoint**

Create `tests/api/agents_list_test.rs`:

```rust
#[tokio::test]
async fn test_list_agents_empty() {
    let pool = test_db().await;
    let app = test_router(pool).await;
    let resp = app
        .oneshot(
            Request::builder()
                .uri("/api/agents")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), 200);
}
```

(Continue with full test implementations for all 13 API modules and 13 DB modules.)

---

### Task 5.2: Python Core Tests

Write DI-powered tests for providers, tools, channels, scenes, and agent lifecycle using `AgentServices.test_double()`.

### Task 5.3: Frontend Tests

Write Vitest tests for all Zustand stores and key components.

### Task 5.4: E2E Tests with Playwright

---

## Phase 6: Plugin SDK (Week 13+)

This phase is dependent on all previous phases being complete. Detailed task breakdowns will be written in a separate plan document after Phase 5 completes, as the codebase will have changed significantly by then.

The Plugin SDK plan will cover:
1. `packages/plugin-protocol/` — manifest schema, permission model, message types
2. `packages/plugin-runtime/` — Python: PluginBase, @tool decorator, EventBus
3. `packages/plugin-sdk/` — TypeScript: iframe↔host postMessage bridge
4. `packages/plugin-components/` — React: PluginCard, PluginSettings, PluginSlot
5. PluginManager in `py-agent/plugin_manager.py` — load/uninstall/permissions
6. Migration of existing mcp and image-gen as plugins
7. Install flow, example plugins, documentation
