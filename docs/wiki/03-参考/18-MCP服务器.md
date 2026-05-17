---
title: MCP 服务器
sidebar_position: 18
---

# MCP 服务器

MCP（Model Context Protocol）服务器将 CocoCat 的核心工具暴露给支持 MCP 的客户端（如 Claude Desktop）。

> **注意**: v2 中 MCP 服务器模块位于 `cococat/mcp/`，该模块可能尚未移植。以下为 v1 参考文档，v2 路径待确认。

## 启动模式

### Stdio 模式（Claude Desktop）

```bash
python -m cococat.mcp
```

用于 Claude Desktop 的 MCP 配置：

```json
{
  "mcpServers": {
    "cococat": {
      "command": "python",
      "args": ["-m", "cococat.mcp"]
    }
  }
}
```

### HTTP SSE 模式

```bash
python -m cococat.mcp --port 8080
```

启动 HTTP 服务器，SSE 端点 `/sse`，消息端点 `/messages`。

## 暴露的工具（6 个）

| 工具 | 说明 | 沙箱保护 |
|------|------|----------|
| `read_file` | 读取文件（支持 offset/limit） | PathValidator |
| `write_file` | 写入文件（自动创建目录） | PathValidator + atomic_write |
| `exec_command` | 执行 shell 命令 | CommandValidator + EnvironmentSanitizer + OutputTruncator |
| `glob_search` | Glob 模式搜索文件 | PathValidator |
| `grep_search` | 文件内容正则搜索 | PathValidator |
| `web_fetch` | 获取 URL 内容 | 内置 |

所有工具经过与主系统相同的沙箱组件保护。

## 协议

MCP Server 实现 JSON-RPC 2.0：

| 方法 | 说明 |
|------|------|
| `initialize` | 协议握手，返回 `protocolVersion: 2024-11-05` |
| `tools/list` | 返回工具列表 |
| `tools/call` | 调用指定工具 |
| `notifications/initialized` | 客户端初始化完成通知（忽略） |

## 工作空间

工作空间路径由环境变量 `COCOCAT_WORKSPACE` 指定，默认为项目根目录。所有文件操作受 `PathValidator` 约束，不可越界访问。
