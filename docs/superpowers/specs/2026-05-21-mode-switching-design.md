# Mode 切换机制完善 & 遗留清理 设计文档

**日期**：2026-05-21
**类型**：功能完善 + 代码清理
**状态**：设计阶段
**父文档**：`2026-05-20-core-model-analysis.md`（Decision #20）

---

## 背景

`2026-05-20` 的核心重构引入了 Mode 系统（`config/modes/*.yaml`），Decision #20 定义了 mode 切换的三条通道，但目前仅实现了手动选择器一条。此外重构后遗留了若干 DAG 残留代码、未对齐的后端链路、以及前端未清理的页面/组件。

本文档覆盖：
- **A. Mode 切换核心**：`switch_mode` 工具 + `/mode` 命令 + `GET /api/modes` + 前端动态选择器
- **B. 后端 Mode 链路**：sub_agent / cron / SceneKeeper 补 mode 参数 + session 路径迁移
- **C. 代码清理**：删 DagEnv + 清理 prompt.py + 前端路由/组件清理 + Dashboard 占位

---

## A. Mode 切换核心

### A1. `switch_mode` 元工具

**触发方式**：Coco 自主决定，调用工具 `switch_mode(target_mode="kb-admin")`

**实现位置**：
- `cococat/core/tools/meta.py`：新增 `_make_switch_mode_tool()` → 注册到 `_ALL_TOOL_FACTORIES`
- `config/modes/default.yaml` 和 `config/modes/kb-admin.yaml`：`tools` 列表添加 `switch_mode`

**工具定义**：
```python
Tool(
    name="switch_mode",
    description="Suggest switching to another mode for upcoming messages",
    parameters={"target_mode": "string", "reason": "string"},
)
```

**标记传递机制**：
- `resolve_tools_for_mode()` 接受可选参数 `mode_switch_flag: list[str]`（mutable container）
- 创建 `switch_mode` 工具的 execute lambda 捕获此容器：
  ```python
  execute=lambda params, ctx, flag=mode_switch_flag: (flag.append(params["target_mode"]), "Switched")[1]
  ```
- chat route 在调用前创建 `flag = []`，传给 `resolve_tools_for_mode()`
- 在 `run_once()` 返回后检查 `flag`：若非空则 `response["mode_switch"] = flag[0]`

**行为**：
1. Coco 调用 `switch_mode(target_mode="kb-admin")` → 工具执行
2. 工具将 target_mode 写入 mode_switch_flag 容器
3. chat route 检测到 flag 非空，在响应 JSON 中增加 `mode_switch: "kb-admin"` 字段
4. 前端收到后静默更新 `<select>` 的值为 `"kb-admin"`
5. 不重发消息、不打断会话、不清理记忆
6. 用户下一次消息自动使用新模式

**default mode 的 system_prompt 提示**：
```yaml
system_prompt: |
  ...
  ## 模式切换
  - 当用户请求涉及知识库管理（上传文件、创建/编辑 wiki、lint/dedup）时，
    调用 switch_mode 工具切换到 kb-admin 模式
  - 知识库工作完成后，可以切换回 default 模式
```

**kb-admin mode 的 system_prompt 提示**：
```yaml
system_prompt: |
  ...
  ## 模式切换
  - 知识库管理工作完成后，调用 switch_mode 工具切换回 default 模式
```

---

### A2. `/mode` 命令

**实现位置**：`web-ui/src/pages/Chat.tsx`，前端输入框拦截

**行为**：
- 用户输入 `/mode kb-admin` → 前端检测前缀
- 切换 mode 状态，清除输入框
- 不发送到服务器
- 后续消息自动使用新模式

**可用 mode 名称**：与 `GET /api/modes` 返回的一致，大小写不敏感

**实现伪代码**：
```ts
const handleInput = (value: string) => {
  const cmd = value.match(/^\/mode\s+(\S+)/i)
  if (cmd) {
    const target = cmd[1].toLowerCase()
    if (availableModes.includes(target)) {
      setMode(target)
      setInput("")
      return
    }
  }
  setInput(value)
}
```

---

### A3. `GET /api/modes` 接口

**路由**：`cococat/routes/chat.py`，追加到已有 router

**响应格式**：
```json
[
  {"id": "default", "name": "Coco", "description": "通用主人格..."},
  {"id": "kb-admin", "name": "知识库管理", "description": "知识库管理模式..."}
]
```

**实现**：
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

---

### A4. 前端动态选择器

**改动文件**：`web-ui/src/pages/Chat.tsx`

**变化**：
1. mount 时 `fetch("/api/modes")` 获取 mode 列表
2. fallback：API 失败时使用硬编码 `[{id: "default", name: "Coco"}, {id: "kb-admin", name: "KB 管理"}]`
3. `<select>` 改为 `.map(modes => <option>)` 动态渲染
4. 响应 JSON 有 `mode_switch` 字段时，`setMode(data.mode_switch)`

---

### A5. 模式切换行为约定

| 行为 | 说明 |
|------|------|
| 会话 | 不变（session_id 不变） |
| 记忆 | 不变（同一 agent 目录） |
| 历史 | 不变（消息追加到同一 session） |
| 工具 | 下一请求时按新模式解析 |
| 用户感知 | 仅 mode 选择器值变化 |

---

## B. 后端 Mode 链路

### B1. SubAgentExecutor.dispatch() 补 mode 参数

**文件**：`cococat/core/sub_agent.py`

**改动**：
```python
async def dispatch(self, task: str, from_agent: str = "main",
                   session_id: str | None = None,
                   mode: str = "default") -> str | None:
```
透传到：
```python
result = await self._sandbox.run_once(
    prompt=task,
    agent_id=f"sub-{task_id}",
    session_id=session_id,
    mode=mode,
)
```

---

### B2. CronWorker mode 修复

**文件**：`cococat/core/cron_worker.py`

**问题**：`_dispatch()` 读取 `entry.get("agent_id")`（不存在），应读 `entry.get("mode")`

**改动**：
```python
# _process_entry() 内：
mode = entry.get("mode", "default")

# _dispatch() 签名改为：
async def _dispatch(task: str, mode: str, sub_executor) -> None:
    result = await sub_executor.dispatch(task, from_agent="cron", mode=mode)
```

---

### B3. SceneKeeper 补 mode 参数

**文件**：`cococat/core/scene_keeper.py`

**改动**：
```python
async def handle_message(self, content: str, mode: str = "default") -> str:
    return await self._sandbox.run_once(
        prompt=content,
        agent_id="coco",
        scene_id=self.scene_id,
        permissions=self._permissions,
        mode=mode,
    )
```

---

### B4. Session 路径迁移

**文件**：`cococat/core/sandbox/__init__.py`、`cococat/routes/chat.py`

**目标路径**：`scenes/{scene_id}/sessions/{user_id}/`

**改动**：
1. `_resolve_agents_dir()` 去掉 `agents/` fallback，统一返回 `scenes/{scene}/sessions/{user}/` 或 `sessions/default`
2. `chat.py` 的 session 删除路由和 history 路由更新为读取新路径
3. `prompt.py` 的 `load_memory_from_agent_dir()` 更新路径引用

**不迁移旧数据**：`agents/main/sessions/` 下的旧 session 文件直接废弃，新 session 从 `scenes/` 路径写入。

---

## C. 代码清理

### C1. 删除 DagEnv 类型

**文件**：`cococat/core/types.py`

**改动**：
- 删除 `DagEnv` 类（第 8-16 行）
- `ToolContext` 删除 `dag: DagEnv` 字段，改为 `sub_agent_executor: Callable | None = None`
- `from_dict()` 简化：
  - 移除 `dag_store` → `DagEnv.store` 映射逻辑（第 64-75 行）
  - 改为：若有 `sub_agent_executor` 键则直接赋值给 `ToolContext.sub_agent_executor`
- 搜索所有构造 `ToolContext(dag=DagEnv(...))` 的调用点并更新：
  - 主要在 `_make_tool_context()` 或 `context.py` 等文件中查找 `ToolContext` 构造

---

### C2. 清理 prompt.py 残留

**文件**：`cococat/core/agent_builder/prompt.py`

**改动**：
- `build_sub_agent_section()` 删除 `"define_dag"`, `"append_stage"`, `"update_dag"`, `"dispatch_task"`, `"check_tasks"`, `"stop_task"` 过滤（这些工具已不存在于代码中）

---

### C3. 前端路由/组件清理

**文件**：`web-ui/src/App.tsx`、`web-ui/src/components/settings/AgentsTab.tsx`

**改动**：
1. `App.tsx` 删除以下路由及对应 import：
   - `/scene/:id/run` → `SceneRun`
   - `/chat/history` → `ChatHistory`
   - `/scene/:id` → `SceneDetail`
2. 删除 `web-ui/src/components/settings/AgentsTab.tsx` 文件
3. `Settings` 组件中删除 AgentsTab 的引用

---

### C4. Dashboard 占位内容

**文件**：`web-ui/src/pages/Dashboard.tsx`

**当前状态**：基本为空（~7 行）

**目标**：填充基本占位：
- Coco 状态卡片（运行中 / mode 列表）
- 最近会话列表
- 当前 Scene 信息
- 系统健康状态摘要

不要求完整实现,只需有意义的占位内容替代空白即可。

---

## 实现顺序

```
C1 (删 DagEnv) → C2 (清理 prompt.py)
  → C3 (前端清理) → C4 (Dashboard)
  → B4 (session 路径迁移)
  → A3 (GET /api/modes) → A4 (前端动态选择器)
  → A1 (switch_mode 工具) → A2 (/mode 命令)
  → B1 (sub_agent mode) → B2 (cron mode) → B3 (SceneKeeper mode)
```

原则：先清理再新建，后端先于前端，核心先于周边。
