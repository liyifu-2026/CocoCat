# SceneRuntime 设计：动态调度工作场景

> Date: 2026-05-07
> Status: Draft

## 目标

将 Scene 从静态配置目录改造为具有运行时生命周期的**隔离工作域**，支持 agent 的动态分配和回收，实现资源（KB/skills/channels）的场景级隔离。

## 背景

当前 Scene 系统的问题：
1. **无运行时** — Scene 只是配置文件目录，没有 `SceneRuntime` 对象管理生命周期
2. **静态绑定** — Agent 通过 `--scene` 启动时绑定，无法运行时切换
3. **无隔离执行** — Agent 可以访问全局所有 KB 和 skills，scene 的 mounted_kbs 只是 prompt 提示
4. **多 agent roster** — 列表冗余，缺乏"一个 scene 一个 agent"的清晰模型

## 概念模型

```
Scene = 一个自包含的 AI 服务单元
类比: RTS 游戏的工作站 — 拖入 agent 就开始工作，拖出就停止

┌──────────────────────────────────────┐
│  SceneManager                         │
│  assign_agent / unassign_agent / list │
└──────────┬───────────────────────────┘
           │
┌──────────▼───────────────────────────┐
│  SceneRuntime (智能客服)              │
│                                      │
│  state: IDLE → ACTIVE → IDLE         │
│                                      │
│  agent_id: "客服小A"                  │  ← 动态分配
│  channels: [微信, 飞书, Web]         │  ← active 时启动，idle 时停止
│  KBs: [产品知识库]                    │  ← agent 只能访问 scene KB
│  skills: agent自身 + [话术, 情绪识别]  │  ← 叠加
│  user_memory: per-user-per-scene     │  ← 场景级隔离
└──────────────────────────────────────┘
```

## 架构

### SceneManager

```python
class SceneManager:
    """全局单例，管理所有 Scene 的运行时生命周期。"""

    # 生命周期操作
    def assign_agent(self, scene_id: str, agent_id: str) -> bool
    def unassign_agent(self, scene_id: str) -> bool

    # 查询
    def get_runtime(self, scene_id: str) -> SceneRuntime | None
    def list_active(self) -> list[str]
    def list_idle(self) -> list[str]

    # 管理
    def create_scene(self, scene_id: str) -> SceneRuntime
    def delete_scene(self, scene_id: str)
```

### SceneRuntime

```python
class SceneState(Enum):
    IDLE = "idle"               # 无 agent，channels 停止
    ACTIVATING = "activating"   # 正在启动
    ACTIVE = "active"           # 正常运行
    DEACTIVATING = "deactivating"  # 正在停止


class SceneRuntime:
    scene_id: str
    state: SceneState
    agent_id: str | None
    config: SceneConfig

    def assign_agent(self, agent_id: str) -> bool
    def unassign_agent(self) -> bool
```

### SceneConfig

```python
@dataclass
class SceneConfig:
    scene_id: str
    name: str
    context: str                         # CONTEXT.md
    agent_id: str | None                 # 当前分配的 agent
    mounted_kbs: list[str]               # KB IDs
    env_skills: list[str]                # scene 级 skills
    channels: list[ChannelConfig]        # 通道配置
    display: dict                        # UI 配置

@dataclass
class ChannelConfig:
    channel_type: str
    enabled: bool
    config: dict
```

### AgentHandle

```python
class AgentHandle:
    """对 agent 的运行时引用。"""

    agent_id: str
    scene_id: str | None    # 当前绑定的 scene

    def assign_to_scene(self, scene_id: str, scene_context: dict)
    def release(self)
    def send_message(self, msg: ChatMessage)
```

## 生命周期

### assign_agent 流程

```
用户/API SceneManager.assign_agent("智能客服", "客服小A")

1. SceneManager.get_runtime("智能客服") → SceneRuntime (state=IDLE)
2. 检查 agent "客服小A" 当前 free
3. SceneRuntime.state = ACTIVATING
4. AgentHandle.assign_to_scene("智能客服", scene_context)
   → 注入 KB 列表、skills、CONTEXT.md
   → AgentLoop 更新 scene 上下文
5. 启动 channels:
   for ch_cfg in config.channels:
       if ch_cfg.enabled:
           channel = create_channel(ch_cfg.channel_type)
           channel.on_message = SceneRuntime.on_message
           channel.start(scene_id, ch_cfg.config)
6. SceneRuntime.state = ACTIVE
```

### unassign_agent 流程

```
用户/API SceneManager.unassign_agent("智能客服")

1. SceneRuntime (state=ACTIVE)
2. SceneRuntime.state = DEACTIVATING
3. 停止 channels:
   for channel in channels:
       channel.stop()
4. AgentHandle.release()
   → 持久化未完成的 session
   → agent 回到 free 池
5. SceneRuntime.state = IDLE
```

### 消息路由流程

```
WeChat 用户消息
    → WeixinChannel（SceneRuntime 启动时绑定的实例）
    → channel.on_message(ChatMessage)
    → SceneRuntime.on_message(msg)
    → AgentHandle.send_message(msg)
        → 写 mailbox（agents/mailbox/{agent_id}/inbox.jsonl）
        → Agent 进程（独立）读取 → 处理 → 写回复
        → SceneRuntime 读取回复
        → Agent 处理
        → 回复通过 outbound 路径
    → SceneRuntime.send_reply(reply, user_id)
    → WeixinChannel.send(reply, context)
```

## 资源隔离

### KB 隔离

当前 `search_kb` 工具搜索全局 `knowledge/*/`。改为按 scene 过滤：

```python
# 搜索时传入 scene_id
search_kb(query, scene_id="智能客服")
    → 只搜索 scene.config.mounted_kbs 列表中的 KB
```

Agent 系统提示词中只列出 scene 挂载的 KB，不告知其他 KB 的存在。

### Skills 隔离

Agent 可用 skills = agent自身 skills + scene.config.env_skills（叠加）。
系统提示词中只注入这组 skills。

### 用户记忆隔离

消息历史写入 `scenes/{scene_id}/users/{user_id}/history.jsonl`。
Agent 的个人记忆（MEMORY.md）保持不变，不受 scene 影响。

## 文件结构

### 新增文件

| 文件 | 说明 |
|------|------|
| `py-agent/scene_manager.py` | SceneManager 单例 + SceneRuntime 类 |
| `py-agent/scene_config.py` | SceneConfig 加载器 (从 scenes/{id}/ 目录) |
| `py-agent/agent_handle.py` | AgentHandle 包装 agent 进程引用 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `py-agent/context.py` | `build_system_prompt()` 支持 scene 级 KB/skills 过滤 |
| `py-agent/agent_runtime.py` | 支持动态 scene 分配（替代 `--scene` 静态绑定） |
| `py-agent/agent_loop.py` | 支持运行时更新 scene 上下文 |
| `web/entry_manager.py` | 集成 SceneRuntime 生命周期 |

### 删除

| 文件 | 说明 |
|------|------|
| `scenes/*/roster.json` | 改为 SceneConfig.agent_id 动态分配 |

## 向后兼容

- 现有场景目录结构不变（CONTEXT.md, mounted_kbs.json, skills/manifest.json, entries.json）
- `scene.json` 保持现有格式
- `roster.json` 会在第一次主动 assign 后废弃

## 与现有系统集成

### Channel 系统

刚才完成的 Channel 重构（ChatChannel / ChannelFactory）直接适配：

```python
def _start_entry(channel_type, scene_id, config, ...):
    ch = create_channel(channel_type)
    ch.on_message = lambda msg: scene_runtime.on_message(msg)
    ch.start(scene_id, config)
```

SceneRuntime 持有 channel 引用的列表，在 deactivate 时遍历 `stop()`。

### Agent 进程

当前 agent 通过 `--scene` 启动时绑定。改为：

1. Agent 启动 → free 状态（无 scene），等待分配
2. `assign_to_scene()` → 通过 mailbox 发送 scene 配置消息 → agent 接收后注入上下文
3. `release()` → 通过 mailbox 发送释放消息 → agent 清除上下文 → free 状态

Agent 进程不需要重启即可切换 scene。Agent 与 SceneRuntime 保持 mailbox 文件通信，消息路径不变。
