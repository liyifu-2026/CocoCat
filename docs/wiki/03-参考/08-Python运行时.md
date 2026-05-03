---
title: Python 运行时
sidebar_position: 8
---

# Python 运行时

```
py-agent/
├── agent_runtime.py     # JSON-RPC 服务端入口
├── agent_runner.py      # AgentRunner 外观类
├── agent_loop.py        # ReAct 循环核心
├── tools.py             # 26 种工具 + ToolRegistry
├── context.py           # System prompt 构建器
├── sandbox.py           # 安全层(路径验证、命令过滤)
├── llm.py               # 多 provider LLM 客户端
├── dream.py             # 记忆整合(Dream)过程
├─� heartbeat.py          # 后台任务轮询
├── mailbox.py           # Agent 间邮箱通信
├── chat_reader.py       # 聊天群组读取器
├── ingest.py            # 知识库双阶段摄取
├── channel.py           # 频道基类
├── channels/            # 具体频道实现
│   ├── wechat.py        # 微信公众号
│   ├── weixin.py        # 企业微信
│   ├── feishu.py        # 飞书
│   └── web_api.py       # Web API 通道
├── scene_router.py      # 场景消息路由
├── git_store.py         # 记忆的 Git 存储
├── auto_compact.py      # 自动压缩历史
├── lsp_client.py        # LSP 客户端(连接池)
├── skill_hub.py         # 技能中心(安装/搜索)
├── scene_package.py     # 场景打包
└── verify_channel.py    # 频道验证
```

## `agent_runtime.py` — JSON-RPC 服务端

**入口点**。运行模式:从 stdin 读取 JSON 行,处理后写入 stdout。

```python
IDENTITY = {"id": None, "name": "unknown", "scene": "default"}
```

**支持的方法**:

| 方法 | 说明 |
|------|------|
| `ping` | 健康检查,返回 `{"pong": true}` |
| `echo` | 回显 params |
| `identify` | 返回 agent 身份 |
| `task` | 执行 ReAct 循环,返回结果 |
| `task_stream` | 流式 task(通过 stdout 逐行推送 delta) |

**启动流程**:
1. 解析 CLI 参数 `--id`, `--name`, `--scene`
2. 启动心跳线程(300s 周期)
3. 进入 stdin 循环
4. 首次收到 `task` 时懒加载 `AgentRunner`

## `agent_runner.py` — AgentRunner 外观

```python
class AgentRunner:
    def __init__(self, agent_id, agent_name, scene, agent_runtime_path)
    def _ensure_loop(self)    # 加载场景上下文、技能、创建 ToolRegistry + AgentLoop
    def run(self, prompt, user_id) -> dict
```

## `agent_loop.py` — ReAct 循环核心

```python
class AgentLoop:
    def __init__(self, agent_id, agent_name, tools, llm,
                 max_iterations=20, workspace, scene_name,
                 scene_context, scene_skills, permission_mode)
    def run(self, prompt, user_id) -> dict
```

**ReAct 循环**:
```
1. 构建 system prompt (context.build_system_prompt)
2. messages = [system, user_prompt]
3. while iteration < max_iterations:
   a. 如果需要: consolidate() 压缩历史, _snip_history() 裁剪 token
   b. LLM.chat(messages, tools)  最多重试 3 次
   c. 如果 finish_reason == "length": 请求继续
   d. 如果有 tool_calls:
      - 用 ThreadPoolExecutor 并行执行所有工具
      - 结果追加到 messages
      - continue
   e. 否则: break (最终回复)
4. append_history() + auto_dream()
5. 返回 {"content": ..., "iterations": N}
```

**历史压缩**:
- `consolidate()`: 用 LLM 将中间消息合并成摘要
- `_snip_history()`: 超出 budget 时,丢弃最早的 non-system 消息
- `_microcompact_tool_results()`: 截断冗长工具输出(>2000 chars)

## `tools.py` — 工具系统

**Tool 基类**:
```python
class Tool:
    name: str
    description: str
    parameters: dict
    required_permission: PermissionMode
    def to_openai_schema(self) -> dict    # 转 OpenAI tools 格式
    def execute(self, **kwargs) -> str    # 执行工具
```

**ToolRegistry**:
```python
class ToolRegistry:
    def register(self, tool)
    def execute(self, name, args, mode) -> str
    def get_definitions(self) -> list[dict]
```

**权限模式**: `READONLY < WORKSPACE_WRITE < FULL_ACCESS`

详见 [05-工具列表](./05-工具列表.md)。

## `context.py` — System Prompt 构建器

构建 agent 的 system prompt,包含:
- 身份、角色、个性
- 场景上下文
- 知识库概览
- 技能描述(agent 级 + 场景级)
- 长期记忆(MEMORY.md)
- 当前用户 profile
- 工具描述(自动从 ToolRegistry 生成)

## `sandbox.py` — 安全层

| 组件 | 说明 |
|------|------|
| `PathValidator` | 检查文件路径是否在 workspace 内 |
| `CommandValidator` | 过滤危险 shell 命令模式 |
| `EnvironmentSanitizer` | 移除 secret 环境变量 |
| `OutputTruncator` | 截断过长的命令输出 |
| `FileLock` | 跨平台文件锁(lock file) |
| `atomic_write` | 原子写入(tmp + rename) |
| `wrap_with_namespace` | Linux namespace 沙箱包装 |

## `llm.py` — LLM 客户端

```python
class LLMClient:
    def __init__(self, providers=None)
    def chat(self, messages, tools, max_tokens, temperature,
             max_retries=3) -> dict
    def chat_stream(self, messages, tools, max_tokens, temperature) -> generator
```

- 支持多 provider 链(失败自动切换)
- 自动重试(指数退避)
- 支持 tools 调用
- 支持流式输出

**Provider**: `OpenAICompatibleProvider` — 兼容 OpenAI API 格式的所有 provider。

## `dream.py` — 记忆整合

**Dream 过程**: 分析 agent 的 history.jsonl,提取关键信息,并入 MEMORY.md。

```
Trigger: 每 30min 或积累 ≥3 条未处理记录
  1. 读取未处理历史条目(从 .dream_cursor 位置开始)
  2. LLM 分析 → 提取决策、事实、偏好、模式
  3. AgentLoop 手术式编辑 MEMORY.md(仅允许 read_file + edit_file)
  4. 更新 cursor
  5. Git commit 记录变更
```

也支持 per-user Dream(每个用户独立的 PROFILE.md):
```
用户对话 → run_user_dream() → 更新 users/{hash}/PROFILE.md
```

## `heartbeat.py` — 后台任务轮询

```python
def start_heartbeat(agent_id, agent_name, interval=300, scene)
```

每个 agent 独立线程,每 300s 执行:
1. **邮箱检查**: `read_inbox()` → 处理 unread → `mark_read()`
2. **聊天群组**: `get_unread_messages()` → 按优先级排序 → 处理 → `mark_as_read()`
3. **定时任务**: `get_pending_tasks()` → 执行 → `update_task_status()`
4. **自动压缩**: `run_auto_compact()`

## `mailbox.py` — Agent 间邮箱

- 收件箱: `agents/mailbox/{agent_id}/inbox.jsonl`
- 线程安全: `FileLock` 保护写入
- Heartbeat 消费: 心跳线程读取并处理 unread 消息

## `chat_reader.py` — 聊天群组读取器

- 从 `chat/groups.json` 获取群组列表
- 按 agent id 过滤所属群组
- 计算消息优先级: @提及 +100, @all +80, admin +50, leader +30
- 仅处理 score ≥ 10 的消息
- `mark_as_read()` 更新 read_by 数组

## `ingest.py` — 知识库摄取

双阶段 LLM 管道:
1. **分析阶段**: LLM 分析源文件 → 输出结构化 JSON(title, type, entities, concepts, key_points, tags, related)
2. **生成阶段**: LLM 根据分析结果生成 Markdown Wiki 页面
3. 自动更新 KB 索引 (`index.md`) 和日志 (`log.md`)

## `channel.py` / `channels/` — 频道抽象

```python
class Channel:
    channel_type = ""
    def start(self, scene_id, config)
    def send(self, reply, user_id)
```

实现:
- `channels/wechat.py` — 微信公众号(XML 消息解析、签名验证)
- `channels/weixin.py` — 企业微信
- `channels/feishu.py` — 飞书
- `channels/web_api.py` — Web API 通道
