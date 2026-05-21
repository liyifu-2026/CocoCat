# Mode 切换机制完善 & 遗留清理 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善 Mode 双向切换机制（Coco 自主 + 用户手动）并清理重构遗留代码

**Architecture:** 新增 `switch_mode` 元工具让 Coco 在运行时建议模式切换，前端拦截 `/mode` 命令直接改选择器；后端链路补全 mode 参数透传；清理 DagEnv 类型、废弃前端页面/组件

**Tech Stack:** Python 3.10+ / FastAPI / React + TypeScript / pytest

---

### Task 1: 删除 DagEnv 类型

**Files:**
- Modify: `cococat/core/types.py:1-104`
- Modify: `cococat/core/agent.py:165`
- Modify: `tests/memory/test_pinned.py:9-14,77-82`

- [ ] **Step 1: 删除 DagEnv 类并将 ToolContext.dag 替换为 sub_agent_executor**

```python
# cococat/core/types.py — 删除 DagEnv 类 (第 8-16 行)，修改 ToolContext

@dataclass
class ToolContext:
    """Typed context passed through the tool execution pipeline."""

    agent_id: str = ""
    agent_dir: str = ""
    bound_scene: str | None = None
    role: str = ""
    session_id: str | None = None

    db: Any = None
    sub_agent_executor: Callable | None = None
    sandbox: SandboxEnv = field(default_factory=SandboxEnv)
    memory: MemoryEnv = field(default_factory=MemoryEnv)
    web: WebEnv = field(default_factory=WebEnv)
    cron_path: str = "runs/cron"
    _llm: Any = None

    @classmethod
    def from_dict(cls, d: dict | None) -> ToolContext:
        """Convert legacy flat dict to typed ToolContext."""
        if d is None:
            return cls()
        if isinstance(d, cls):
            return d

        sandbox = SandboxEnv(run=d.get("sandbox_run"))

        mem_kw = {}
        if "memory_path" in d:
            mem_kw["memory_path"] = d["memory_path"]
        if "agent_dir" in d:
            mem_kw["agent_dir"] = d["agent_dir"]
        if "exp_path" in d:
            mem_kw["exp_path"] = d["exp_path"]
        memory = MemoryEnv(**mem_kw) if mem_kw else MemoryEnv()

        web = WebEnv(tavily_api_key=d.get("tavily_api_key"))

        direct_keys = {"agent_id", "agent_dir", "bound_scene", "role", "session_id",
                       "db", "sub_agent_executor", "cron_path", "_llm"}
        direct = {k: v for k, v in d.items() if k in direct_keys}

        return cls(sandbox=sandbox, memory=memory, web=web, **direct)
```

要删除的内容（精确行号）：
- 第 8-16 行：`class DagEnv:` 整个类定义
- 第 49 行：`dag: DagEnv = field(default_factory=DagEnv)` → `sub_agent_executor: Callable | None = None`
- 第 64-75 行：DAG 相关的 `from_dict` 逻辑块
- 第 94-95 行：`direct_keys` 集合（不需要修改，`dag` 不在集合中所以自然跳过）
- 第 99 行：`dag=dag,` 删除

- [ ] **Step 2: 更新 agent.py 中 ToolContext 构造**

`cococat/core/agent.py` 第 165 行 `context = ToolContext()` 不需要改动——默认值 `DagEnv()` 变为 `None` 即可。但确认 `context.dag` 的使用：

运行 `rg "\.dag" cococat/core/` 检查是否还有通过 `.dag` 属性访问的代码。

```bash
cd /home/leaif/Project/CocoCat && rg "\.dag\b" cococat/core/
```

预期：无匹配或仅有注释。

- [ ] **Step 3: 更新测试中的 ToolContext 构造**

`tests/memory/test_pinned.py` 第 10 行和 78 行的 `ToolContext(...)` 调用不传 `dag` 参数，无需修改。确认测试通过：

```bash
cd /home/leaif/Project/CocoCat && python -m pytest tests/memory/test_pinned.py -v
```

- [ ] **Step 4: 运行全量测试确认无回归**

```bash
cd /home/leaif/Project/CocoCat && python -m pytest tests/ -v 2>&1 | tail -30
```

- [ ] **Step 5: Commit**

```bash
git add cococat/core/types.py
git commit -m "refactor: remove DagEnv type, replace ToolContext.dag with sub_agent_executor"
```

---

### Task 2: 清理 prompt.py 中 DAG 工具名过滤

**Files:**
- Modify: `cococat/core/agent_builder/prompt.py:28-32`

- [ ] **Step 1: 删除不存在的 DAG 工具名**

```python
# cococat/core/agent_builder/prompt.py — 第 28-32 行

# Before:
exec_tools = [t for t in all_tools if t["name"] not in (
    "define_dag", "append_stage", "update_dag", "dispatch_task", "check_tasks", "stop_task",
    "pin", "unpin", "recall",
    "cron", "wait", "current_status",
)]

# After:
exec_tools = [t for t in all_tools if t["name"] not in (
    "pin", "unpin", "recall",
    "cron", "wait", "current_status",
)]
```

- [ ] **Step 2: 确认工具列表无误**

```bash
cd /home/leaif/Project/CocoCat && python -c "
from cococat.core.tools import create_core_tools
names = [t['name'] for t in create_core_tools()]
dag_names = ['define_dag', 'append_stage', 'update_dag', 'dispatch_task', 'check_tasks', 'stop_task']
missing = [n for n in dag_names if n not in names]
print('Missing DAG tools (expected all missing):', missing if missing else 'OK — all gone')
print('Total tools:', len(names))
"
```

- [ ] **Step 3: Commit**

```bash
git add cococat/core/agent_builder/prompt.py
git commit -m "refactor: remove stale DAG tool name filters from prompt builder"
```

---

### Task 3: 前端路由清理（删 SceneRun / ChatHistory 路由 + AgentsTab 文件）

**Files:**
- Modify: `web-ui/src/App.tsx:1-34`
- Delete: `web-ui/src/pages/SceneRun.tsx`
- Delete: `web-ui/src/pages/ChatHistory.tsx`
- Delete: `web-ui/src/components/settings/AgentsTab.tsx`

- [ ] **Step 1: 从 App.tsx 删除废弃路由和 import**

只删除 `SceneRun`（空壳）、`ChatHistory`、以及这两个路由。保留 `SceneDetail`（SceneRail 链接依赖）。

```tsx
// web-ui/src/App.tsx — 修改后

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { Layout } from "@/components/Layout"
import ErrorBoundary from "@/components/ErrorBoundary"
import Chat from "@/pages/Chat"
import SceneDetail from "@/pages/SceneDetail"
import Dashboard from "@/pages/Dashboard"
import Scenes from "@/pages/Scenes"
import Knowledge from "@/pages/Knowledge"
import KnowledgeDetail from "@/pages/KnowledgeDetail"
import SceneNew from "@/pages/SceneNew"

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ErrorBoundary><Chat /></ErrorBoundary>} />
          <Route path="/dashboard" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
          <Route path="/scenes" element={<ErrorBoundary><Scenes /></ErrorBoundary>} />
          <Route path="/scenes/:id" element={<ErrorBoundary><SceneDetail /></ErrorBoundary>} />
          <Route path="/scenes/new" element={<ErrorBoundary><SceneNew /></ErrorBoundary>} />
          <Route path="/knowledge" element={<ErrorBoundary><Knowledge /></ErrorBoundary>} />
          <Route path="/knowledge/:kb" element={<ErrorBoundary><KnowledgeDetail /></ErrorBoundary>} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 2: 删除废弃页面文件**

```bash
rm /home/leaif/Project/CocoCat/web-ui/src/pages/SceneRun.tsx
rm /home/leaif/Project/CocoCat/web-ui/src/pages/ChatHistory.tsx
rm /home/leaif/Project/CocoCat/web-ui/src/components/settings/AgentsTab.tsx
```

- [ ] **Step 3: 确认前端编译通过**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/App.tsx web-ui/src/pages/SceneRun.tsx web-ui/src/pages/ChatHistory.tsx web-ui/src/components/settings/AgentsTab.tsx
git commit -m "refactor(frontend): remove SceneRun, ChatHistory routes and AgentsTab"
```

---

### Task 4: Dashboard 占位内容

**Files:**
- Modify: `web-ui/src/pages/Dashboard.tsx:1-7`

- [ ] **Step 1: 填充 Dashboard 基本内容**

```tsx
import { useState, useEffect } from "react"
import { Activity, Cpu, Layers, Zap } from "lucide-react"

interface ModeInfo {
  id: string
  name: string
  description: string
}

export default function DashboardPage() {
  const [modes, setModes] = useState<ModeInfo[]>([])
  const [sessions, setSessions] = useState<{ id: string; title: string }[]>([])

  useEffect(() => {
    fetch("/api/modes").then(r => r.json()).then(setModes).catch(() => {})
    try {
      const raw = localStorage.getItem("cococat-sessions")
      if (raw) {
        const data = JSON.parse(raw)
        setSessions(data?.sessions?.slice(0, 5) || [])
      }
    } catch {}
  }, [])

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-display">Dashboard</h1>
        <p className="text-xs text-muted-foreground mt-1">系统状态一览</p>
      </div>
      <div className="flex-1 overflow-auto p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard icon={<Cpu className="size-5" />} label="运行模式" value={`${modes.length} 个`} detail={modes.map(m => m.name).join(" / ") || "加载中..."} />
          <StatusCard icon={<Layers className="size-5" />} label="活跃会话" value={`${sessions.length} 个`} detail="最近会话" />
          <StatusCard icon={<Zap className="size-5" />} label="系统状态" value="运行中" detail="ExecutorProvider 正常" />
        </div>

        <div className="rounded-xl border border-border bg-card/40 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="size-4 text-muted-foreground" />
            <h2 className="text-sm font-medium">可用模式</h2>
          </div>
          <div className="space-y-2">
            {modes.length === 0 && <p className="text-xs text-muted-foreground">加载模式列表...</p>}
            {modes.map(m => (
              <div key={m.id} className="flex items-center gap-3 rounded-lg bg-accent/20 px-4 py-2.5">
                <span className="text-sm font-medium">{m.name}</span>
                <span className="text-xs text-muted-foreground">{m.description}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusCard({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card/40 p-4 space-y-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="text-xl font-bold">{value}</div>
      {detail && <div className="text-xs text-muted-foreground">{detail}</div>}
    </div>
  )
}
```

- [ ] **Step 2: 确认前端编译通过**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/Dashboard.tsx
git commit -m "feat(frontend): add Dashboard placeholder with mode list and system status"
```

---

### Task 5: Session 路径迁移

**Files:**
- Modify: `cococat/core/sandbox/__init__.py:25-31`
- Modify: `cococat/routes/chat.py:22-48,87-133`
- Modify: `cococat/core/agent.py:179`

- [ ] **Step 1: `_run_sandbox_chat()` 透传 scene_id 和 user_id**

当前 `_run_sandbox_chat` 签名缺少 `scene_id`/`user_id`，导致 `_resolve_agents_dir` 回退到 `sessions/default` 而非 `scenes/{scene}/sessions/{user}/`。

```python
# cococat/routes/chat.py — 第 22-48 行

async def _run_sandbox_chat(
    ctx: AppContext,
    agent_id: str,
    prompt: str,
    session_id: str | None,
    tools: list,
    mode: str = "default",
    scene_id: str = "default",
    user_id: str = "local",
) -> str:
    sandbox_provider = ctx.sandbox_provider
    if not sandbox_provider:
        return f"[System] ExecutorProvider not available for agent '{agent_id}'"

    async def on_event(event_type: str, data: dict):
        await ctx.ws_manager.broadcast(event_type, {
            **(data or {}),
            "agent_id": agent_id,
            "session_id": session_id,
        })

    return await sandbox_provider.run_once(
        prompt=prompt,
        agent_id=agent_id,
        tools=tools,
        on_event=on_event,
        session_id=session_id,
        mode=mode,
        scene_id=scene_id,
        user_id=user_id,
    )
```

同时更新调用点（第 75 行）：
```python
# Before:
reply = await _run_sandbox_chat(ctx, "main", body.content, body.session_id, tools, mode=body.mode)

# After:
reply = await _run_sandbox_chat(ctx, "main", body.content, body.session_id, tools, mode=body.mode, scene_id=body.scene_id, user_id=user_id)
```

- [ ] **Step 2: 确认 `_resolve_agents_dir()` 的路径逻辑**

```python
# cococat/core/sandbox/__init__.py — 第 25-31 行

def _resolve_agents_dir(scene_id: str | None = None, user_id: str | None = None) -> str:
    if scene_id and user_id:
        return f"scenes/{scene_id}/sessions/{user_id}"
    elif scene_id:
        return f"scenes/{scene_id}/sessions"
    return "sessions/default"
```

（当前代码已正确，但需确认 `_make_and_run_agent()` 中的 `_resolve_agents_dir` 调用传了 `scene_id` 和 `user_id`）

- [ ] **Step 3: 更新 chat.py 中 session 删除路由的路径**

```python
# cococat/routes/chat.py — 替换 delete_chat_session 函数 (第 87-111 行)

@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, ctx: AppContext = Depends(get_ctx)):
    import os, shutil
    deleted = {"session_files": 0, "sub_agent_dirs": 0}

    # New paths under scenes/
    scenes_dir = "scenes"
    if os.path.isdir(scenes_dir):
        for scene_name in os.listdir(scenes_dir):
            sessions_dir = os.path.join(scenes_dir, scene_name, "sessions")
            if not os.path.isdir(sessions_dir):
                continue
            for user_dir in os.listdir(sessions_dir):
                session_path = os.path.join(sessions_dir, user_dir, f"{session_id}.jsonl")
                if os.path.exists(session_path):
                    os.remove(session_path)
                    deleted["session_files"] += 1

    # Clean stale sub-agent dirs
    agents_dir = str(ctx.config_store.agents_dir)
    if os.path.isdir(agents_dir):
        for name in os.listdir(agents_dir):
            if name.startswith("sub-"):
                path = os.path.join(agents_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    deleted["sub_agent_dirs"] += 1

    return {"status": "deleted", **deleted}
```

- [ ] **Step 4: 更新 chat.py 中 history 路由的路径**

```python
# cococat/routes/chat.py — 替换 chat_history 路由 (第 114-134 行)

@router.get("/chat/history")
async def chat_history(ctx: AppContext = Depends(get_ctx), scene_id: str = "default", limit: int = 50, session_id: str = ""):
    """Get chat history. If session_id provided, reads from session file."""
    if session_id:
        import os, json as _json
        user = ctx.user_id or "local"
        path = os.path.join("scenes", scene_id, "sessions", user, f"{session_id}.jsonl")
        if not os.path.exists(path):
            return {"messages": []}
        msgs = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msg = _json.loads(line)
                        msgs.append({"role": msg.get("role", ""), "content": msg.get("content", "")})
                    except _json.JSONDecodeError:
                        pass
        return {"messages": msgs}
    return {"messages": ctx.db.messages.get_chat_history(scene_id, limit, user_id=ctx.user_id)}
```

- [ ] **Step 5: 确认 agent.py 中 session 路径解析无变化**

```python
# cococat/core/agent.py — 第 179 行附近，`_resolve_session_path` 调用

# 当前 (第 179 行):
session_path = _resolve_session_path(config.agent_dir, sid)

# 确认 _resolve_session_path 定义（agent.py 顶部）使用了正确的路径模式。
# 如果 agent_dir 现在是 "scenes/default/sessions/local/main"，
# 那么 session_path 为 "scenes/default/sessions/local/main/<session_id>.jsonl" 即可。
```

`_resolve_session_path` 函数（agent.py 文件顶部某处）定义为：
```python
def _resolve_session_path(agent_dir: str, session_id: str) -> str:
    return os.path.join(agent_dir, f"{session_id}.jsonl") if session_id else os.path.join(agent_dir, "session.jsonl")
```

这是在 `agent_dir` 下追加 session 文件名，只要 `agent_dir` 指向正确路径即可。无需修改函数本身。

```bash
# 确认函数位置
cd /home/leaif/Project/CocoCat && rg "_resolve_session_path" cococat/core/agent.py
```

- [ ] **Step 6: 运行测试确认无回归**

```bash
cd /home/leaif/Project/CocoCat && python -m pytest tests/ -v 2>&1 | tail -30
```

- [ ] **Step 7: Commit**

```bash
git add cococat/core/sandbox/__init__.py cococat/routes/chat.py
git commit -m "refactor: migrate session paths from agents/ to scenes/{scene}/sessions/{user}/"
```

---

### Task 6: `GET /api/modes` 接口

**Files:**
- Modify: `cococat/routes/chat.py`

- [ ] **Step 1: 新增 route**

在 `cococat/routes/chat.py` 的 `@router.delete("/chat/session/{session_id}")` 之后添加：

```python
@router.get("/modes")
async def list_modes_route():
    from cococat.core.modes import list_modes
    modes = list_modes()
    return [
        {"id": m.id, "name": m.name, "description": m.description}
        for m in modes
    ]
```

- [ ] **Step 2: 手动验证接口**

```bash
# 启动后端后
curl http://localhost:8000/api/modes | python -m json.tool
```

预期返回：
```json
[
    {"id": "default", "name": "Coco", "description": "通用主人格..."},
    {"id": "kb-admin", "name": "知识库管理", "description": "知识库管理模式..."}
]
```

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/chat.py
git commit -m "feat: add GET /api/modes endpoint for dynamic mode listing"
```

---

### Task 7: 前端动态 Mode 选择器

**Files:**
- Modify: `web-ui/src/pages/Chat.tsx`

- [ ] **Step 1: 添加 modes 状态和获取逻辑**

在 `ChatPage` 组件内（第 28 行 `const [mode, setMode] = useState("default")` 之后）添加：

```tsx
const [modes, setModes] = useState<{ id: string; name: string }[]>([
  { id: "default", name: "Coco" },
  { id: "kb-admin", name: "KB 管理" },
])

useEffect(() => {
  fetch("/api/modes")
    .then(r => r.json())
    .then(data => {
      if (data?.length) setModes(data)
    })
    .catch(() => {})
}, [])
```

- [ ] **Step 2: 将硬编码 `<select>` 改为动态渲染**

第 334-341 行，替换：

```tsx
<select
  value={mode}
  onChange={e => setMode(e.target.value)}
  className="shrink-0 rounded-xl border border-border bg-background/60 px-3 py-3 text-xs font-medium text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 cursor-pointer"
>
  {modes.map(m => (
    <option key={m.id} value={m.id}>{m.name}</option>
  ))}
</select>
```

- [ ] **Step 3: 处理响应中的 mode_switch 字段**

在 `sendMessage` 函数中（第 74-91 行），`const data = await resp.json()` 之后添加：

```tsx
const data = await resp.json()
const reply = data.reply || "(no response)"

// Mode switch handling
if (data.mode_switch && modes.some(m => m.id === data.mode_switch)) {
  setMode(data.mode_switch)
}
```

- [ ] **Step 4: 确认前端编译通过**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 5: Commit**

```bash
git add web-ui/src/pages/Chat.tsx
git commit -m "feat(frontend): dynamic mode selector with /api/modes and mode_switch handling"
```

---

### Task 8: `switch_mode` 元工具

**Files:**
- Modify: `cococat/core/tools/meta.py`（新增 `_make_switch_mode_tool`）
- Modify: `cococat/core/tools/__init__.py`（注册到 `_ALL_TOOL_FACTORIES`）
- Modify: `cococat/routes/chat.py`（检测 flag 并返回 `mode_switch`）
- Modify: `config/modes/default.yaml`（tools 列表添加 `switch_mode`）
- Modify: `config/modes/kb-admin.yaml`（tools 列表添加 `switch_mode`）

- [ ] **Step 1: 在 meta.py 新增 switch_mode 工具工厂**

在 `cococat/core/tools/meta.py` 末尾（`make_meta_tools` 函数之后）添加：

```python
def make_switch_mode_tool(mode_switch_flag: list | None = None) -> Tool:
    """Create a switch_mode tool that writes the target mode to a mutable flag list.

    The flag list is provided by the chat route and checked after Agent.run()
    returns to include mode_switch in the response JSON.
    """
    from cococat.core.tools.types import _make

    def _switch_mode(params: dict, ctx) -> str:
        target = params.get("target_mode", "")
        if not target:
            return "Error: 'target_mode' is required"
        if mode_switch_flag is not None:
            mode_switch_flag.append(target)
        return f"Mode switch suggested: {target}"

    return _make(
        name="switch_mode",
        description="Suggest switching to another mode for upcoming messages. Use when the user's request needs tools available in a different mode.",
        params={"target_mode": "string", "reason": "string"},
        execute_fn=_switch_mode,
    )
```

需要导入 `Tool`：
```python
from cococat.core.tools.types import Tool, _make
```

检查 meta.py 顶部 import，添加 `Tool`。

- [ ] **Step 2: 在 `__init__.py` 注册到 `_ALL_TOOL_FACTORIES`**

在 `cococat/core/tools/__init__.py` 中：

```python
# 在 import 部分添加
from cococat.core.tools.meta import make_meta_tools, make_switch_mode_tool

# 在 _ALL_TOOL_FACTORIES 中添加 (第 50 行之前，如 "current_status" 之后)
"switch_mode": lambda flag=None: make_switch_mode_tool(flag),
```

- [ ] **Step 3: 更新 `resolve_tools_for_mode()` 支持 switch_mode**

在 `cococat/core/tools/__init__.py` 中，`resolve_tools_for_mode()` 函数签名加 `mode_switch_flag` 参数，并在工具解析中添加 `switch_mode` 分支：

```python
def resolve_tools_for_mode(mode_id: str, sub_agent_executor=None, tavily_api_key=None, mode_switch_flag=None):
    from cococat.core.modes import load_mode

    mode = load_mode(mode_id)
    tools = []
    for tool_name in mode.tools:
        if tool_name == "sub_agent":
            if sub_agent_executor:
                tools.append(Tool(
                    name="sub_agent",
                    description="Spawn a sub-agent to execute a task",
                    parameters={"task": "string", "agent_id": "string"},
                    execute=lambda params, ctx, executor=sub_agent_executor: executor(params.get("task", ""), params.get("agent_id", "sub")),
                ))
        elif tool_name == "switch_mode":
            tools.append(make_switch_mode_tool(mode_switch_flag))
        elif tool_name in _ALL_TOOL_FACTORIES:
            try:
                factory = _ALL_TOOL_FACTORIES[tool_name]
                if tool_name in ("web_search", "web_fetch"):
                    tool = factory(tavily_api_key)
                else:
                    tool = factory()
                if isinstance(tool, list):
                    tools.extend(tool)
                else:
                    tools.append(tool)
            except Exception:
                continue
    return tools
```

- [ ] **Step 4: 更新 chat.py 创建 flag 容器并检测**

在 `cococat/routes/chat.py` 中修改 chat 路由：

```python
@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    user_id = ctx.user_id or body.user_id or "local"
    msg_uuid = new_uuid()
    msg_store = ctx.db.messages
    msg_store.save(
        msg_uuid=msg_uuid, agent_id="main", user_id=user_id,
        role="user", content=body.content, scene_id=body.scene_id,
        channel_type="web",
    )

    from cococat.core.tools import resolve_tools_for_mode, resolve_tavily_key
    sub_executor = ctx.sub_executor
    tavily_key = resolve_tavily_key(ctx.config_store)

    mode_switch_flag: list[str] = []
    tools = resolve_tools_for_mode(
        body.mode,
        sub_agent_executor=sub_executor.dispatch if sub_executor else None,
        tavily_api_key=tavily_key,
        mode_switch_flag=mode_switch_flag,
    )

    try:
        reply = await _run_sandbox_chat(ctx, "main", body.content, body.session_id, tools, mode=body.mode)
    except Exception as e:
        reply = f"Error: {e}"

    reply_uuid = new_uuid()
    msg_store.save(
        msg_uuid=reply_uuid, agent_id="main", user_id=user_id,
        role="assistant", content=reply, scene_id=body.scene_id,
    )

    response = {"reply": reply, "msg_uuid": reply_uuid}
    if mode_switch_flag:
        response["mode_switch"] = mode_switch_flag[0]
    return response
```

（注意：`return` 语句需要从 `return {"reply": reply, "msg_uuid": reply_uuid}` 改为上述带条件 `mode_switch` 的形式）

- [ ] **Step 5: 在两个 Mode YAML 的 tools 列表添加 `switch_mode`**

`config/modes/default.yaml`：
```yaml
tools:
  - switch_mode
  - sub_agent
  - read_file
  ...
```

`config/modes/kb-admin.yaml`：
```yaml
tools:
  - switch_mode
  - sub_agent
  - read_file
  ...
```

- [ ] **Step 6: 更新 default mode 的 system_prompt**

在 `config/modes/default.yaml` 的 system_prompt 末尾追加：

```yaml
system_prompt: |
  你是 Coco，CocoCat 平台的核心智能体。...
  ...
  ## 模式切换
  - 当用户请求涉及知识库管理（上传文件、创建/编辑 wiki、lint/dedup）时，
    调用 switch_mode 工具，target_mode 设为 "kb-admin"
  - 知识库工作完成后，调用 switch_mode 切换回 "default"
```

- [ ] **Step 7: 更新 kb-admin mode 的 system_prompt**

在 `config/modes/kb-admin.yaml` 的 system_prompt 末尾追加：

```yaml
system_prompt: |
  你是 Coco，当前在知识库管理模式下工作。...
  ...
  ## 模式切换
  - 知识库管理工作完成后，调用 switch_mode 工具，target_mode 设为 "default"
```

- [ ] **Step 8: 运行测试确认**

```bash
cd /home/leaif/Project/CocoCat && python -m pytest tests/core/test_modes.py -v
```

- [ ] **Step 9: Commit**

```bash
git add cococat/core/tools/meta.py cococat/core/tools/__init__.py cococat/routes/chat.py config/modes/default.yaml config/modes/kb-admin.yaml
git commit -m "feat: add switch_mode meta tool for Coco-initiated mode switching"
```

---

### Task 9: `/mode` 命令（前端拦截）

**Files:**
- Modify: `web-ui/src/pages/Chat.tsx`

- [ ] **Step 1: 在输入处理中拦截 `/mode` 命令**

在 Chat.tsx 中，修改 `handleKeyDown` 和 send 逻辑。在 `send` 函数（第 103-108 行）之前添加 mode 命令检测：

```tsx
// Replace the input onChange handler — modify the textarea's onChange:
const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
  const value = e.target.value
  const cmdMatch = value.match(/^\/mode\s+(\S+)/i)
  if (cmdMatch) {
    const target = cmdMatch[1].toLowerCase()
    if (modes.some(m => m.id === target)) {
      setMode(target)
      setInput("")
      return
    }
  }
  setInput(value)
}
```

然后将 textarea 的 `onChange={e => setInput(e.target.value)}` 改为 `onChange={handleInputChange}`。

- [ ] **Step 2: 确认前端编译通过**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/Chat.tsx
git commit -m "feat(frontend): add /mode slash command for in-chat mode switching"
```

---

### Task 10: SubAgentExecutor.dispatch() 补 mode 参数

**Files:**
- Modify: `cococat/core/sub_agent.py:30-61`

- [ ] **Step 1: dispatch() 加 mode 参数并透传**

```python
# cococat/core/sub_agent.py — 修改 dispatch 方法

async def dispatch(self, task: str, from_agent: str = "main",
                   session_id: str | None = None,
                   mode: str = "default") -> str | None:
    if self._sandbox:
        return await self._dispatch_via_sandbox(task, from_agent, session_id, mode)

    logger.warning("No executor configured for dispatch from %s", from_agent)
    return None

async def _dispatch_via_sandbox(self, task: str, from_agent: str,
                                session_id: str | None = None,
                                mode: str = "default") -> str | None:
    task_id = uuid.uuid4().hex[:12]

    try:
        result = await self._sandbox.run_once(
            prompt=task,
            agent_id=f"sub-{task_id}",
            session_id=session_id,
            mode=mode,
        )
        await self._bus.publish("sub_agent_complete", {
            "task_id": task_id,
            "from_agent": from_agent,
            "agent_id": f"sub-{task_id}",
            "result": result,
        })
        return result
    except Exception as e:
        logger.exception("Sub-agent sandbox task %s failed", task_id)
        await self._bus.publish("sub_agent_complete", {
            "task_id": task_id,
            "from_agent": from_agent,
            "agent_id": f"sub-{task_id}",
            "error": str(e),
        })
        return f"Error: {e}"
```

- [ ] **Step 2: Commit**

```bash
git add cococat/core/sub_agent.py
git commit -m "feat: add mode parameter to SubAgentExecutor.dispatch()"
```

---

### Task 11: CronWorker mode 修复

**Files:**
- Modify: `cococat/core/cron_worker.py:107-113,198-244`

- [ ] **Step 1: 修改 `_dispatch()` 签名和实现**

```python
# cococat/core/cron_worker.py — 第 107-114 行

async def _dispatch(task: str, mode: str, sub_executor) -> None:
    if not sub_executor:
        raise RuntimeError("No sub_executor available for dispatch")

    result = await sub_executor.dispatch(task, from_agent="cron", mode=mode)
    if not result:
        raise RuntimeError("Sub-agent dispatch returned no result for task")
    return
```

- [ ] **Step 2: 修改 `_process_entry()` 读取 mode 而非 agent_id**

```python
# cococat/core/cron_worker.py — 第 225-237 行

        task = entry.get("task", "")
        task_id = entry.get("id", "unknown")
        mode = entry.get("mode", "default")
        is_system = entry.get("type") == "system" or task.startswith("__")

        logger.info("CronWorker dispatching %s -> mode=%s: %s", task_id, mode, task)

        try:
            if is_system and task.startswith("__"):
                entry["status"] = await _dispatch_system_task(task)
            else:
                await _dispatch(task, mode, self._sub_executor)
                entry["status"] = "completed"
```

替换第 225-237 行（删除 `target_agent_id` 变量，替换为 `mode`）。

- [ ] **Step 3: Commit**

```bash
git add cococat/core/cron_worker.py
git commit -m "fix: use mode instead of agent_id in CronWorker dispatch"
```

---

### Task 12: SceneKeeper 补 mode 参数

**Files:**
- Modify: `cococat/core/scene_keeper.py:39-59`

- [ ] **Step 1: handle_message() 加 mode 参数**

```python
# cococat/core/scene_keeper.py — 修改 handle_message 方法

async def handle_message(self, content: str, mode: str = "default") -> str:
    """Process a message through the sandbox agent. Returns reply text.

    Retries up to max_retries times on failure, then returns fallback_reply.
    """
    for attempt in range(self._max_retries + 1):
        try:
            return await self._sandbox.run_once(
                prompt=content,
                agent_id="coco",
                scene_id=self.scene_id,
                permissions=self._permissions,
                mode=mode,
            )
        except Exception as e:
            logger.warning(
                "SceneKeeper[%s]: attempt %d/%d failed: %s",
                self.scene_id, attempt + 1, self._max_retries + 1, e,
            )
            if attempt >= self._max_retries:
                return self._fallback_reply
    return self._fallback_reply
```

- [ ] **Step 2: Commit**

```bash
git add cococat/core/scene_keeper.py
git commit -m "feat: add mode parameter to SceneKeeper.handle_message()"
```

---

### Task 13: 最终验证

- [ ] **Step 1: 运行全量后端测试**

```bash
cd /home/leaif/Project/CocoCat && python -m pytest tests/ -v 2>&1
```

- [ ] **Step 2: 前端 TypeScript 编译检查**

```bash
cd /home/leaif/Project/CocoCat/web-ui && npx tsc --noEmit 2>&1
```

- [ ] **Step 3: 确认所有 mode YAML 文件可加载**

```bash
cd /home/leaif/Project/CocoCat && python -c "
from cococat.core.modes import list_modes
for m in list_modes():
    print(f'{m.id}: {m.name} — {len(m.tools)} tools, {len(m.skills)} skills')
"
```

- [ ] **Step 4: 最终 git status 确认无遗漏文件**

```bash
cd /home/leaif/Project/CocoCat && git status
```
