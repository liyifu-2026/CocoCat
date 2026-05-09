# CocoCat 自底向上重构设计方案

> **日期:** 2026-05-04
> **状态:** 已批准

## 概述

对 CocoCat 四层架构（Rust 核心 → Python Agent 运行时 → FastAPI 后端 → Channel 系统）进行系统性重构，每层独立提升至 Beta 质量。

## 重构路径

### Layer 1: Rust 核心引擎 (Prototype → Beta)
- 替换所有 unwrap/expect 为优雅错误传播
- 静默吞错误加 tracing 日志
- Agent 调用加 60s 超时
- 健康检查加退避重试
- 信号处理 (SIGTERM/SIGINT)
- println → tracing 结构化日志
- main.rs 拆分

### Layer 2: Python Agent 运行时 (Alpha → Beta)
- 修死代码
- 归一化 prompt 构建
- EditFileTool TOCTOU 修复
- SubAgent timeout
- consolidate 深度保护
- Dream 并发锁
- 去重 _user_hash
- print → structlog
- 测试覆盖

### Layer 3: FastAPI 后端 (Prototype → Beta)
- 空密钥启动检查
- main.py 拆分
- 异步 subprocess
- CORS + 全局异常 + 请求日志
- schedule 实际执行
- Pydantic 模型补全

### Layer 4: Channel 系统 (Early → Beta)
- Discord send() 重写
- Feishu token 定时刷新 + WS 重连
- 基类增强 + 重连 mixin
- Entry Manager 自动创建默认配置
- 删除死代码
