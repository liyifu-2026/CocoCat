# E2E Integration Test Design

## Goal

启动完整 CocoCat 系统做端到端串联测试，验证 core 启动、agent spawn、健康检查、队伍 roster 全链路正常。

## Scope

不依赖 LLM API key，测试下列节点：

1. **Core 启动** — 打印 "CocoCat Core starting..."
2. **加载配置** — 打印 "Loaded 4 agent definitions"
3. **Spawn agents** — 每个 agent 打印状态 `[enabled] 组长 (leader)`
4. **健康检查** — ping 所有 agent，输出 ✅/❌
5. **队伍 roster** — identify 所有 agent，输出 id/name/scene
6. **Clean exit** — 打印 "CocoCat Core exiting."

## Technique

- 在 `tests/` 下新增 Rust 集成测试 `e2e_test.rs`
- 通过 `std::process::Command` 启动编译好的 binary
- 使用 `wait_with_output()` 带 timeout（30s）
- 断言 stdout 包含关键字符串
- 无需 mock，不依赖 LLM API（ping/identify 不走 LLM）

## Risk Mitigations

- Leader task call 需要 LLM API key → 缺失时 LLM call 会失败，但不会 hang（有 retry/fail 逻辑），测试可以等 timeout
- `process_pending_hires()` 和 `check_user_questions()` 可能阻塞 → 测试前确保 `pending/` 目录和 `_ask_user.json` 不存在
