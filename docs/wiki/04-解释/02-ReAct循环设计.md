---
title: ReAct 循环设计
sidebar_position: 2
---

# ReAct 循环设计

ReAct（Reasoning + Acting）是 Agent 的核心决策循环，实现位于 `py-agent/agent_loop.py`。

## 基本流程

```
system prompt → LLM 调用 → 工具执行 → 结果 → 继续调用 → ... → 最终回复
                              ↑______________________________|
```

```python
class AgentLoop:
    def run(self, prompt, user_id) -> dict:
        messages = [system_prompt, user_prompt]
        iteration = 0

        while iteration < max_iterations:          # 最多 20 轮
            if needs_consolidate:
                consolidate()                       # LLM 压缩历史
                _snip_history()                     # Token 裁剪

            response = LLM.chat(messages, tools)    # 最大 3 次重试

            if finish_reason == "length":
                request_continue()                  # Token 耗尽续写
                continue

            if response has tool_calls:
                execute_tools_in_parallel()          # ThreadPoolExecutor
                append_results_to_messages()
                iteration += 1
                continue

            break  # 纯文本回复 → 结束

        append_history()
        auto_dream()
        return {"content": final_reply, "iterations": N}
```

## 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | 20 | 最大工具调用轮次，防止无限循环 |
| `max_retries` | 3 | LLM 调用失败重试次数 |
| `consolidate_every` | 动态 | 消息积累到 token 阈值时触发压缩 |
| `token_budget` | 动态 | 上下文窗口的 70%，预留工具响应空间 |

## 并行工具执行

当 LLM 在一次响应中返回多个 tool_calls 时，使用 `ThreadPoolExecutor` 并行执行：

```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(tool_registry.execute, call): call
        for call in tool_calls
    }
    for future in as_completed(futures):
        result = future.result()
        messages.append({"role": "tool", ...})
```

这显著提升了耗时工具的并行度（如同时 `web_search` + `grep_search`）。

## Token 预算管理

ReAct 循环需要防止上下文窗口溢出。三层防护：

### 1. Consolidator（LLM 压缩）

当消息历史超过 token budget 时，调用 LLM 将中间消息（工具调用和结果）合并为自然语言摘要。使用边界感知 split 算法，确保不会切断 tool call→result 对。

### 2. Snip History（硬裁剪）

如果 Consolidator 后仍超预算，从最旧消息开始丢弃（保留最后 4 条消息 + system prompt）。

### 3. Micro-compact（工具结果截断）

单个工具输出超过 2000 字符时截断，并标注 `[truncated X chars]`。

## LLM 调用可靠性

```python
for attempt in range(max_retries):
    try:
        response = self.llm.chat(messages, tools, ...)
        return response
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # 指数退避
            continue
        raise
```

- 网络错误指数退避重试
- 空响应重试（最多 3 次）
- `finish_reason == "length"` 时自动续写

## 循环终止条件

| 条件 | 行为 |
|------|------|
| LLM 返回纯文本（无 tool_calls） | 正常结束，返回最终回复 |
| 达到 `max_iterations` | 强制终止，返回最后一条消息 |
| `finish_reason == "stop"` 但有 tool_calls | 捕获到完整响应，继续执行 |
| `finish_reason == "length"` | 请求续写（追加 "continue"） |
| LLM 返回错误 | 重试，耗尽后返回错误信息 |

## 自动 Dream

每次 ReAct 循环结束后调用 `auto_dream()`：

- 读取未处理的历史记录
- 如果满足触发条件（时间>30min 或积累≥3 条），执行 Dream
- Dream 用受限的工具集（仅 `read_file` + `edit_file`）手术式更新 `MEMORY.md`

详见 [记忆系统设计原理](./03-记忆系统设计原理.md)。
