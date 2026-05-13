# CocoCat 记忆系统：Auto-Dream 设计

日期: 2026-05-14
状态: 已确认

## 背景

当前记忆系统完成度：

- ✅ `session.jsonl` — 每轮对话持久化，重启可恢复上下文
- ✅ `memory/memory.md` — pin/unpin/recall 读写，启动注入 system prompt
- ✅ 路径已对齐 — pin 写和启动加载用同一个文件
- ✅ context 已传递 — `agent.run()` 传 agent_id/agent_dir/role

缺失：**没人自动调 pin**。记忆全靠 Agent 自觉或用户手动。跨会话的信息全靠重读 session.jsonl，浪费 1M 上下文。

## 目标

用户隔天回来，第一条消息就能"记得"之前聊过的关键信息，不需要 LLM 从头重读全部原始对话。

## 设计原则

- 1M 上下文时代：不担心 token 爆，不引入 Consolidator
- 无心跳线程：CocoCat 已废弃 heartbeat，走事件驱动
- 极简：不引入 cursor、不引入 Git、不引入多用户

## 流程

```
用户发第一条消息
  ↓
agent.run() 启动
  ↓
_load_session() → 全量读 session.jsonl → 注入 messages
  ↓
检查：session.jsonl 行数 > 50？
  ├─ 否 → 继续正常对话
  └─ 是 → fire-and-forget: try_auto_dream(agent)
            │
            ├─ 读 session.jsonl 全部内容
            ├─ LLM 提取关键事实："从以下对话提取新发现的关键事实，每条一行"
            ├─ 逐条 pin → memory/memory.md（已存在的跳过）
            └─ 清空 session.jsonl（保留最新 10 行做缓冲）
  ↓
正常 ReAct 循环
```

## 文件布局

```
agents/main/
  ├── session.jsonl        ← 对话历史
  └── memory/
        └── memory.md      ← 长期记忆
```

无 `.dream_cursor`。每次检查只看行数阈值。

## 触发条件

第一次对话就触发——用户回来发第一条消息时：

```
session.jsonl 行数 > 50 → 触发 Dream
```

50 行约等于 20-30 轮对话。不频繁，但能捕获足够的跨会话信息。

## LLM 调用

模型：`deepseek-v4-flash`（便宜，已有配置，复用 `ProviderFactory`）。不和 Main AI 抢 deepseek-chat 额度。

Prompt：

```
你是一个记忆助手。从以下对话历史中提取迄今为止新发现的关键事实。
每条不超过 30 字。只提取对后续对话有用的信息：
用户偏好、项目信息、进行中的任务、重要决策、代码改动要点。
不要提取闲聊内容，不要重复已经记录过的事实（见上下文中的 ## Memory 段）。

对话历史：
{session.jsonl}

输出格式：严格每行一条事实，不要编号，不要前缀，不要空行。
```

## 去重逻辑

pin 之前检查 memory.md 是否已包含相似内容：直接字符串包含即可（`fact in memory_content`），不做语义去重。简单够用。

## 截断逻辑

Dream 执行后：
- 保留 session.jsonl 最新 10 行（当下会话的缓冲）
- 删除更早的全部行

## 失败处理

```
try:
    facts = await llm.chat(dream_prompt)
    for fact in facts.splitlines():
        if fact.strip() and fact.strip() not in memory_content:
            pin(fact.strip())
    # 截断 session.jsonl
    truncate_session(session_path, keep_lines=10)
except Exception:
    logger.warning("auto_dream failed, will retry next session")
```

fire-and-forget（`asyncio.create_task`），失败不改任何文件，下次启动再试。

## 改动清单

| 文件 | 改动 | 行数 |
|------|------|------|
| `agent.py` | `_load_session` 后检测行数阈值 → 触发 Dream | ~10 行 |
| `memory.py` (新) | `try_auto_dream(agent)` — 阈值检查 + LLM 提取 + pin + 截断 | ~60 行 |
| `tests/core/test_auto_dream.py` (新) | 阈值触发、pin 写入、去重、失败兜底 | ~30 行 |

总计约 100 行。

## 不做

- Consolidator / _snip_history — 1M 上下文不需要
- heartbeat 线程 — 已废弃
- .dream_cursor 游标 — 全量处理，无需状态
- GitStore — 过设计
- Per-User Dream — 单用户先够用
- 受限工具循环 — 直接用 pin