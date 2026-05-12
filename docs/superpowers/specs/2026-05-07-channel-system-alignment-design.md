# Channel 系统重构设计：CowAgent 对齐

> Date: 2026-05-07
> Status: Draft

## 目标

将 CocoCat 的 Channel 系统与 CowAgent 的渠道架构对齐，从当前 ~30% 对齐度提升至 ~85%。

## 背景

当前 CocoCat Channel 系统存在以下问题：

1. **缺少 ChatChannel 中间层**：CowAgent 的 `ChatChannel` 提供了消息队列、session 管理、上下文构建、回复流水线等核心能力，CocoCat 完全缺失
2. **回复类型单一**：`send(reply: str, user_id: str)` 只支持纯文本，不支持图片/文件/视频等类型
3. **连接状态贫乏**：`bool _connected` 无法表达 `connecting/reconnecting/disconnected` 等中间状态
4. **缺少通道工厂**：channel 实例化分散在 `entry_manager.py` 的 `_start_*` 函数中
5. **没有 Plugin 事件集成**：CowAgent 在 channel 层有 4 个事件钩子，CocoCat 没有
6. **没有 session 队列**：多用户并发时可能出现消息交叉
7. **现有实现不一致**：Feishu 已有 token refresh 但 Discord 没有 connected_state

## 架构

### 分层结构

```
┌─────────────────────────────────────┐
│  Channel (基类)                      │
│  - connected_state (4-state)        │
│  - startup() / start() / stop()     │
│  - send(reply: Reply, context: Context) │
│  - startup_event (Event 报告)        │
│  - on_disconnected 回调              │
└────────────────┬────────────────────┘
                 │ extends
┌────────────────▼────────────────────┐
│  ChatChannel (中间层)                │
│  - produce(context) → session 队列   │
│  - consume() → 后台消费线程          │
│  - _compose_context()               │
│  - _handle() → 回复流水线            │
│  │  ├─ _generate_reply()            │
│  │  ├─ _decorate_reply()            │
│  │  └─ _send_reply()                │
│  - Plugin 事件: 4 hooks             │
│  - cancel_session()                 │
└────────────────┬────────────────────┘
                 │ extends
┌────────────────▼────────────────────┐
│  具体 Channel 实现                   │
│  Weixin / Feishu / Telegram / Discord│
│  - startup(): 各自连接逻辑           │
│  - send(): 各自发送逻辑              │
│  - _parse_message(): 平台消息解析    │
└─────────────────────────────────────┘
```

### 回复流水线

```
收到平台原始消息
    → _parse_message() → ChatMessage
    → _compose_context() → Context | None
        → Plugin: ON_RECEIVE_MESSAGE
    → produce(context) → session 队列
    → consume() → _handle(context)
        → _generate_reply(context)
            → Plugin: ON_HANDLE_CONTEXT
            → Bridge().fetch_agent_reply()
                → [LocalBridge | MailboxBridge]
        → _decorate_reply(context, reply)
            → Plugin: ON_DECORATE_REPLY
            → 前缀/后缀/@提及/语音转换
        → _send_reply(context, reply)
            → Plugin: ON_SEND_REPLY
            → 媒体提取 (图片/视频 URL → 单独发送)
            → self.send(reply, context)
```

### Bridge 与 Mailbox 的关系

Bridge 是 channel 获取 AI 回复的唯一接口。Mailbox 是 Bridge 的一种进程通信实现：

```
Bridge.fetch_agent_reply(query, context) → Reply
├── LocalBridge:    直接调用 AgentLoop.run() (同进程)
└── MailboxBridge:  写 mailbox → 轮询回复 (跨进程)
```

Channel 和 ChatChannel 不感知 mailbox 的存在。

## 文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `py-agent/channel_context.py` | ContextType/ReplyType 枚举、Context/Reply 类 |
| `py-agent/chat_channel.py` | ChatChannel 中间层（~200 行） |
| `py-agent/channels/channel_factory.py` | 通道工厂 + 注册机制 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `py-agent/channel.py` | 重写：4-state、send(Reply,Context)、startup_event、on_disconnected |
| `py-agent/channels/channel_base.py` | 增强：对齐新的 connected_state |
| `py-agent/channels/weixin.py` | 重写：继承 ChatChannel |
| `py-agent/channels/feishu.py` | 重写：继承 ChatChannel |
| `py-agent/channels/telegram.py` | 重写：继承 ChatChannel |
| `py-agent/channels/discord.py` | 重写：继承 ChatChannel |
| `web/entry_manager.py` | 简化：改用 ChannelFactory |

### 依赖于未来实现

| 项目 | 说明 |
|------|------|
| Bridge 系统 | 新建 `Bridge` 类，支持 LocalBridge / MailboxBridge |
| PluginManager 事件 | 已有基础，新增 2 个 channel 事件类型 |

## 实现步骤

### Step 1: Channel 基类增强 + Context/Reply 系统
- 新建 `channel_context.py`
- 重写 `channel.py`

### Step 2: ChannelFactory
- 新建 `channels/channel_factory.py`

### Step 3: ChatChannel 中间层
- 新建 `chat_channel.py`
- 包含 produce/consume、_compose_context、回复流水线

### Step 4: 重写现有 Channel 实现
- WeixinChannel (参考 CowAgent 的完整 weixin_channel.py)
- FeishuChannel (保留 token refresh)
- TelegramChannel (最简单)
- DiscordChannel (asyncio + discord.py)

### Step 5: 简化 entry_manager
- 用 ChannelFactory 替代 `_start_*` 函数
- 保留 `_route_to_agent` + mailbox 写入

### Step 6: Bridge 集成
- Bridge 作为 channel 唯一回复接口
- 可独立于 channel 重构进行

## 与 CowAgent 对齐矩阵

| 维度 | 当前 | 对齐后 |
|------|------|--------|
| 接口层 | `Channel` 单层 | `Channel` + `ChatChannel` 双层 |
| 回复类型 | 纯文本 `send(str, str)` | `send(Reply, Context)` 多类型 |
| 连接状态 | `bool _connected` | 4-state: disconnected/connecting/connected/reconnecting |
| Session 管理 | 无 | `produce/consume` 按 session 排队 |
| 上下文构建 | 无 | `_compose_context` (前缀/群组/黑白名单) |
| Plugin 事件 | 无 | 4 生命周期事件 |
| 通道工厂 | 无 | `ChannelFactory` |
| 回复流水线 | on_message 直接回调 | `_handle → _generate → _decorate → _send` |
| 启动报告 | 无 | `startup_event` Event 机制 |
| Bridge 集成 | 无 | `Bridge().fetch_agent_reply()` |

## 安全性 / 边界情况

1. **session 队列死锁**：`BoundedSemaphore` 确保并发度上限，`consume` 循环防止队列积压
2. **channel 重复启动**：`start()` 应在 `stop()` 后重置状态，防止重复线程
3. **token 过期**：Feishu token refresh 保留，`send()` 内增加 401 重试
4. **Bridge 超时**：同步 Bridge 应设置超时，超时后返回友好错误回复
5. **Plugin 事件异常**：每个事件调用应 try/except，防止单个 plugin 拖垮整个 channel
