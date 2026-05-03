---
title: 雇佣第一个 Agent
sidebar_position: 2
---

# 雇佣第一个 Agent

本教程演示如何通过对话雇佣一个新的 agent 加入团队。

## 步骤

### 1. 进入聊天

启动 Rust 核心和 Web 后端（参考 [第一次对话](./01-第一次对话.md)）。

### 2. 发起雇佣请求

在聊天中发送：

```
帮我雇佣一个叫 Diana 的 employee，擅长数据分析
```

或者直接调用 hire_agent 工具（通过 Python）：

```python
from py-agent.tools import hire_agent

hire_agent(
    name="Diana",
    role="employee",
    scene="default",
    interpreter="python",
    script="py-agent/agent_runtime.py"
)
```

### 3. 观察 pending 文件

雇佣请求已写入 `agents/hire_requests/pending/`：

```bash
ls agents/hire_requests/pending/
```

你会看到类似 `hire_diana.json` 的文件。

### 4. 在控制台批准

切回 Rust 守护进程终端，你会看到：

```
[Diana] requests to join as employee. Approve? (y/N)
```

输入 `y` 并回车。

### 5. 确认批准

Rust 自动执行以下操作：

```
1. 将请求文件移到 approved/ 目录
2. 追加 [[agents]] 到 config.toml
3. 创建 agents/memory/diana/
4. 生成初始 profile.json
5. 启动 Diana 进程
6. 写入系统消息
```

终端输出：

```
[INFO] Diana (employee, default) 已启动
[MSG] System: Diana (employee) 已加入场景 default
```

### 6. 验证

查看 agent 列表：

```bash
> status
Agent         Status    Role      Scene
─────────────────────────────────────────
alice         running   leader    default
bob           running   employee  default
charlie       running   employee  default
diana         running   employee  default
```

查看 config.toml：

```bash
cat agents/config.toml
```

你会看到新增的 `[[agents]]` 条目。

### 7. 在 Web 面板中查看

打开 Web 面板 `http://localhost:8000`，进入 Agent 管理页面，Diana 已出现在列表中，状态为"运行中"。

## 完成

你成功雇佣了 Diana！她现在可以接收 Alice 分配的任务，也可以直接在场景对话中与你交流。

## 故障排除

| 问题 | 解决 |
|------|------|
| 未收到审批提示 | 确保 Rust 守护进程正在运行 |
| Agent 启动失败 | 检查 `py-agent/agent_runtime.py` 路径是否正确 |
| 状态显示 stopped | 运行 `restart diana` 手动重启 |
