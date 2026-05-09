# Code Refactoring Plan

**Scope:** Fix Rust warnings, clean up test data, add .env support, move customer-service to scenes/, split web routes.

---

### Task 1: Clean up Rust warnings + test data

**Files:**
- Modify: `src/agent_manager.rs`
- Modify: `src/agent_registry.rs`

- [ ] **Step 1: Fix Rust dead_code warnings**

Read `src/agent_manager.rs` and `src/agent_registry.rs`, add `#[allow(dead_code)]` on intentionally unused items:

In `agent_manager.rs`, add before the struct and methods:
```rust
#[allow(dead_code)]
impl AgentProcess {
```

In `agent_registry.rs`, add before unused fields/methods:
```rust
#[allow(dead_code)]
pub struct AgentStatus {
```

- [ ] **Step 2: Clean test data in agents/ and scenes/**

```powershell
Remove-Item -Recurse -Force "C:\Users\12991\Desktop\Cococlaw\agents\hire_requests" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "C:\Users\12991\Desktop\Cococlaw\agents\dispatch_queue" -ErrorAction SilentlyContinue
Remove-Item -Force "C:\Users\12991\Desktop\Cococlaw\agents\_weixin_credentials.json" -ErrorAction SilentlyContinue
Remove-Item -Force "C:\Users\12991\Desktop\Cococlaw\agents\_consolidation_log.jsonl" -ErrorAction SilentlyContinue
Remove-Item -Force "C:\Users\12991\Desktop\Cococlaw\agents\_usage.jsonl" -ErrorAction SilentlyContinue
Remove-Item -Force "C:\Users\12991\Desktop\Cococlaw\agents\_ask_user.json" -ErrorAction SilentlyContinue
```

- [ ] **Step 3: Build and test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add src/ agents/
git commit -m "refactor: fix Rust warnings, clean test data"
```

---

### Task 2: Move customer-service → scenes/ + .env support

**Files:**
- Modify: move `customer-service/` to `scenes/customer-service/`
- Create: `.env` file

- [ ] **Step 1: Move customer-service**

```powershell
Move-Item "C:\Users\12991\Desktop\Cococlaw\customer-service" "C:\Users\12991\Desktop\Cococlaw\scenes\customer-service" -ErrorAction SilentlyContinue
```

- [ ] **Step 2: Create .env template**

`C:\Users\12991\Desktop\Cococlaw\.env`:
```
OPENAI_API_KEY=your-key-here
OPENAI_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

- [ ] **Step 3: Update web/main.py to load .env**

Add at top of web/main.py (after imports):
```python
# Load .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
```

- [ ] **Step 4: Build and test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add .env web/main.py
git mv customer-service scenes/customer-service 2>/dev/null || Move-Item
git add scenes/customer-service
git commit -m "refactor: move customer-service to scenes/.env support"
```

---

### Task 3: Split web/main.py routes

**Files:**
- Create: `web/routes/__init__.py`
- Create: `web/routes/agents.py`
- Create: `web/routes/scenes.py`
- Create: `web/routes/chat.py`
- Modify: `web/main.py`

- [ ] **Step 1: Create routes package**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\web\routes" | Out-Null
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\web\routes\__init__.py" | Out-Null
```

- [ ] **Step 2: Move agent API to routes/agents.py**

```python
"""Agent management routes."""
from fastapi import APIRouter
import json, os, sys
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/api/agents")
def list_agents():
    config_path = BASE_DIR / "agents" / "config.toml"
    agents = []
    if config_path.exists():
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for a in data.get("agents", []):
            agents.append({
                "id": a["id"], "name": a["name"],
                "enabled": a.get("enabled", True), "scene": a.get("scene", "default"),
            })
    return {"agents": agents}
```

- [ ] **Step 3: Move usage API to routes/agents.py**

```python
@router.get("/api/usage")
def get_usage(limit: int = 50):
    usage_path = BASE_DIR / "agents" / "_usage.jsonl"
    entries = []
    if usage_path.exists():
        with open(usage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except: pass
    return {"usage": entries[-limit:]}
```

- [ ] **Step 4: Update web/main.py to include routers**

```python
from web.routes.agents import router as agents_router
app.include_router(agents_router)
```

- [ ] **Step 5: Build and test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add web/routes/ web/main.py
git commit -m "refactor: split web routes into modules"
```
