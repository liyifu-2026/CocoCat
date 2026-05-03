---
title: 配置 Agent
sidebar_position: 3
---

# 配置 Agent

Agent 的配置分布在多个文件中，存放在 `agents/{id}/` 目录下。配置项在首次创建时写入，部分字段不可变。

## 目录结构

```
agents/{id}/
├── profile.json       # 个性配置（不可变）
├── display.json       # 显示配置（可修改）
├── skills/
│   └── manifest.json  # 技能清单
├── entries.json       # 频道入口配置
├── memory/
│   ├── MEMORY.md      # 长期记忆
│   ├── history.jsonl  # 历史记录
│   └── .dream_cursor  # Dream 游标
└── PROFILE.md         # 当前用户 profile（自动维护）
```

## 1. profile.json — 个性配置

首次 hire 时写入，`skip if exists`，不可变。

```json
{
  "role": "资深工程师",
  "objective": "负责代码审查和技术方案设计",
  "traits": ["细致", "严谨"],
  "background": "10年后端开发经验",
  "rules": ["Always write tests before implementation"],
  "gender": "male"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `role` | 是 | Agent 角色名称 |
| `objective` | 是 | 核心目标，注入 system prompt |
| `traits` | 否 | 性格特征列表 |
| `background` | 否 | 背景描述 |
| `rules` | 否 | 行为规则列表 |
| `gender` | 否 | `male` / `female`，影响默认头像 |

## 2. display.json — 显示配置

控制 Web 面板中的展示样式，可通过 API 修改。

```json
{
  "nickname": "小程",
  "avatar": "👨‍💻",
  "color": "#4A90D9"
}
```

| 字段 | 说明 |
|------|------|
| `nickname` | 面板中显示的名称 |
| `avatar` | Emoji 或 SVG 头像标识 |
| `color` | 主题色（十六进制） |

## 3. skills/manifest.json — 技能清单

```json
{
  "public": ["code_review", "architecture_design"],
  "private": ["debug_script"]
}
```

| 字段 | 说明 |
|------|------|
| `public` | 其他 agent 可见的技能，通过 `search_skill` 可发现 |
| `private` | 仅自己可见的技能 |

通过 `learn_skill` / `forget_skill` 工具管理技能清单。

## 4. entries.json — 频道入口

```json
{
  "entries": [
    {
      "type": "channel",
      "channel": "webhook",
      "enabled": true,
      "config": {}
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `channel` | 渠道类型（`feishu`, `weixin`, `web_api` 等） |
| `enabled` | 是否启用 |
| `config` | 渠道配置参数 |

## 5. 系统配置（`agents/config.toml`）

由 Rust 核心读取，控制 Agent 生命周期：

```toml
[[agents]]
id = "leader"
name = "组长"
interpreter = "python"
script = "py-agent/agent_runtime.py"
enabled = true
scene = "development"
```

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识，用于 Rust 进程管理和 agent 间路由 |
| `name` | 可读名称 |
| `interpreter` | 解释器（目前仅 `python`） |
| `script` | Agent 运行时脚本路径 |
| `enabled` | 是否随 Rust 核心自动启动 |
| `scene` | 所属场景 ID |

## 6. 场景指派

Agent 的 `scene` 字段决定其归属场景。同一场景内的 agent 共享：
- `CONTEXT.md` — 场景上下文
- `mounted_kbs.json` — 挂载的知识库
- `skills/` — 场景级技能（env_skills）

场景目录位于 `scenes/{id}/`。
