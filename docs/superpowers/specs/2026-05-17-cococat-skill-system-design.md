# CocoCat Skill System Design

**Date:** 2026-05-17
**Status:** draft

## 1. Overview

统一技能管理系统。所有技能定义为 `skills/` 目录下的 `.md` 文件，通过 YAML frontmatter 自描述。Agent 和 Scene 各自通过配置文件引用技能列表。加载时技能文件注入 system prompt，可选注册为可调用工具。

## 2. Directory Structure

```
skills/
  code_review.md
  prd_writing.md
  communication.md
  file-ops.md
  strategy.md
  knowledge-ingestion.md

agents/
  leader/
    profile.yaml      # ← skills 字段
    memory/
  employee_a/
    profile.yaml
    memory/

scenes/
  development/
    scene.yaml        # ← skills 字段
  customer-service/
    scene.yaml
  default/
    scene.yaml
```

**删除的旧文件/目录：**
- `skills/registry.json`
- `skills/public/`
- `skills/private/`
- `scenes/*/skills/`（场景技能 .md 文件移入 `skills/`）
- `agents/*/skills/manifest.json`
- `scenes/*/scene.json`、`scenes/*/config.json`
- `scenes/*/CONTEXT.md`（内容并入 scene.yaml）

## 3. Skill File Format

所有技能文件位于 `skills/` 根目录，文件名（不含 `.md`）是其唯一引用 ID。

```markdown
---
name: Code Review
description: Review code for quality, correctness, and style
tags: [development, review, qa]
as_tool: false
---

# Code Review Skill

Review code changes for quality, correctness, and style.

## Process
1. Read the changed files and understand the context
2. Check for: logic errors, edge cases, security issues, style violations
3. Provide constructive feedback with specific line references
4. Suggest improvements when applicable

## Guidelines
- Be specific: reference exact lines and logic
- Be constructive: explain why something is a problem
- Prioritize: critical bugs > correctness > style
```

### Frontmatter Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | No | filename | Display name |
| `description` | No | body[:200] | Summary |
| `tags` | No | `[]` | Classification labels (metadata only) |
| `as_tool` | No | `false` | Register as callable tool (see §5) |

## 4. Loading Behavior

### 4.1 Skill Loading

`cococat/skills.py` provides the core loading functions:

```python
Skill = dict  # {"name": str, "description": str, "tags": list[str],
               #  "body": str, "as_tool": bool}

def load_skill(name: str) -> Skill | None
    """Load single skill from skills/{name}.md"""

def resolve_skills(names: list[str]) -> list[Skill]
    """Load multiple skills; missing ones skip + log warning"""

def skills_to_prompt(skills: list[Skill], max_len: int = 4000) -> str
    """Join skill bodies into a prompt block"""

def skills_to_tools(skills: list[Skill]) -> list[dict]
    """Return tool definitions for skills with as_tool == true"""
```

### 4.2 Agent Initialization

1. `Agent.__init__` → `load_agent_profile(agent_dir)` 读取 `profile.yaml`
2. 从 profile 获取 `skills: [...]`
3. 调用 `resolve_skills(profile.skills)` 加载技能
4. 技能注入 system prompt（`skills_to_prompt`）
5. 有 `as_tool: true` 的技能注册到 tool set（`skills_to_tools`）

### 4.3 Scene Binding

`Agent.bind_to_scene(scene_id)`:

1. `load_scene_config(scene_id)` 读取 `scene.yaml` → 获取 scene 技能列表
2. 合并 agent 技能 + scene 技能，去重（union）
3. `resolve_skills(merged)` → `skills_to_prompt` 注入 prompt，`skills_to_tools` 注册工具
4. Unbind 时恢复为 agent 自身技能

### 4.4 Sub-Agents

子代理（worker / sub-agent）不自动继承父代理或场景的技能。子代理按自身 `profile.yaml`（若有）加载技能。

### 4.5 Prompt Injection Format

技能文本注入 system prompt 的格式：

```
## Active Skills

### code_review
<skill body>

### prd_writing
<skill body>
```

## 5. Callable Skills (`as_tool: true`)

当 `as_tool: true` 时，技能同时注册为 LLM 可调用的 tool：

```python
tool_def = {
    "name": skill_name,           # filename without .md
    "description": description,   # from frontmatter
    "parameters": {},             # none by default
}
```

工具执行时返回技能完整正文（前 2000 字符），供 LLM 参考：

```python
def execute(params, ctx):
    return body[:2000]
```

**使用场景示例：** `knowledge-ingestion` 有明确的处理流程，agent 不需要始终看到它（避免 prompt 污染），但可以按需调用。

## 6. Configuration

### 6.1 Agent: `agents/{id}/profile.yaml`

```yaml
name: Leader
role: resident
personality: Strategic and decisive team coordinator
skills:
  - communication
  - file-ops
  - strategy
```

`cococat/profile.py` 已有 `load_agent_profile()` 读取此文件。新增 `skills` 字段处理。

### 6.2 Scene: `scenes/{id}/scene.yaml`

```yaml
id: development
name: Development
context: |
  Software development work environment.

  ## Guidelines
  - Focus on code quality, testing, and documentation
  - Follow the team's coding standards
  - Use sub_agent for complex multi-file changes
kbs:
  - team-wiki
skills:
  - code_review
  - prd_writing
roster:
  - leader
  - employee_a
```

`cococat/scene/config.py` 的 `SceneConfig` dataclass 和 `load_scene_config()` 已支持所有字段，无需修改数据结构。

### 6.3 Residents Config

`config/residents/*.yaml` 中的 `skills: []` 字段保留，作为 resident agent 的初始技能列表传入 `Agent.__init__`。

## 7. Tags

Tags 是纯元数据，仅用于前端展示 / 过滤 / 搜索，不参与运行时技能匹配。

- 技能可选零个或多个 tag
- 同一个技能可以有多个 tag（如 `[development, review, qa]`）
- 配置时直接按文件名选择技能，不按标签匹配

## 8. Migration Steps

### Phase 1: Unify skill files
- 将 `scenes/development/skills/code_review.md` → `skills/code_review.md`（补 frontmatter）
- 将 `scenes/development/skills/prd_writing.md` → `skills/prd_writing.md`（补 frontmatter）
- 将 `skills/public/knowledge-ingestion.md` → `skills/knowledge-ingestion.md`（补 frontmatter）
- 将 `skills/private/strategy.md` → `skills/strategy.md`（补 frontmatter）
- 新建 `skills/communication.md`、`skills/file-ops.md`

### Phase 2: Create config files
- 为 leader / employee_a / employee_b 创建 `profile.yaml`（包含 skills）
- 为 development / customer-service / default 创建 `scene.yaml`
- 删除旧 CONTEXT.md / scene.json / config.json / manifest.json

### Phase 3: Update loader code
- 重写 `cococat/skills.py`：实现 `load_skill` / `resolve_skills` / `skills_to_prompt` / `skills_to_tools`
- 修改 `cococat/core/agent.py`：从 profile 加载 skills，bind_to_scene 合并 skills
- 修改 `cococat/prompt.py`：`build_system_prompt` 接受已渲染的技能文本块
- 更新 `cococat/routes/skills.py`：API 路径指向新的 `skills/` 目录
- 删除旧路径兼容代码（`skills/scenes/`、`skills/public/`）

### Phase 4: Update tests
- 更新 `tests/cococat/test_skills.py`
- 新增 tag 解析、as_tool 转换、merged skills 的测试

### Phase 5: Cleanup
- 删除 `skills/registry.json`
- 删除 `skills/public/`、`skills/private/` 目录
- 删除 `scenes/*/skills/` 目录
- 删除 `agents/*/skills/manifest.json`
- 删除 `scenes/*/CONTEXT.md`、`scene.json`、`config.json`

## 9. Error Handling

| Scenario | Behavior |
|----------|----------|
| Skill .md file not found | Log warning, skip, continue |  
| Invalid YAML frontmatter | Use defaults (filename as name, body[:200] as description) |
| Duplicate skill names in config | De-duplicate silently |
| Skill body too large (>4000 chars) | Truncate in prompt with `[...truncated]` |
| `as_tool` skill referenced but no tool system | Ignore tool registration, still inject prompt |

## 10. API Routes

`/api/skills` — 保持现有路由结构，更新加载逻辑：

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/skills` | List all skills (from `skills/*.md`), with tags/description preview |
| `GET` | `/api/skills/{name}` | Get single skill body + metadata |
| `GET` | `/api/skills?tag=development` | Filter by tag |
