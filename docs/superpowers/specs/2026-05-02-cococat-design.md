# CocoCat: Multi-Agent Team Management System

## Core Vision

Build a multi-agent team management system for small teams (~20 agents, called "smart employees").
Each agent works within "scenes" that provide scene-specific memory and skills.
Each agent has immutable personality attributes and a mutable skill system with tags.
Scenes can be dynamically created to allocate agent labor force across different work contexts.

## Tech Stack

| Layer       | Language         | Framework / Tools                      |
|-------------|------------------|----------------------------------------|
| Core Engine | Rust             | Agent process manager, message bus     |
| Agent Logic | Python           | Behavior, prompt, LLM, skills, Dream   |
| Web Panel   | Python (FastAPI) | Management UI, REST API                |
| LLM         | Cloud API        | OpenAI / Claude API                    |

## Architecture

```
┌───────────────────────────────────────────┐
│        Web Panel (Python FastAPI)         │
│    场景/员工/技能/群聊/知识库管理          │
└──────────────────┬────────────────────────┘
                   │ REST API
┌──────────────────▼────────────────────────┐
│           Rust Core Engine                │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Agent    │  │ Message  │  │ Memory │  │
│  │ Manager  │  │ Bus      │  │ Store  │  │
│  │ (进程管理)│  │ (群聊)   │  │ (向量) │  │
│  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       │  Task Scheduler (排班表)   │       │
└───────┼──────────────┼────────────┼───────┘
        │  JSON-RPC / ZeroMQ        │
┌───────▼──────────────▼────────────▼───────┐
│        Python Agent Runtime               │
│  ┌────────┐ ┌────────┐ ┌──────┐ ┌──────┐  │
│  │ Agent  │ │ Scene  │ │Skill │ │ LLM  │  │
│  │逻辑    │ │场景管理│ │技能  │ │客户端│  │
│  └────────┘ └────────┘ └──────┘ └──────┘  │
└───────────────────────────────────────────┘
```

### Communication

Rust ↔ Python: JSON-RPC over stdin/stdout per agent subprocess.

### Rust Core Responsibilities

- Agent subprocess lifecycle management
- Message bus for inter-agent communication (structured JSON, not display text)
- Memory storage engine (vector DB integration for KB retrieval)
- Task scheduler (maintained by Leader agent)
- Config and settings management

### Python Agent Runtime

- Agent behavior and prompt orchestration
- Scene context management
- Skill execution (learn, forget, tag)
- LLM client
- Nanobot-style "cultivation" features (Dream, Consolidator)

## Memory Architecture (nanobot-inspired)

```
workspace/
├── team/
│   ├── AGENT_ROSTER.md      # 每个员工都知道彼此技能（Dream 维护）
│   ├── TEAM_MEMORY.md        # 团队共享记忆
│   ├── schedule.json         # 共享排班表（组长维护）
│   └── chat/
│       └── group.jsonl       # 群聊消息存档（JSONL 游标模式，仅显示层）
│
├── agents/
│   ├── {agent_id}/
│   │   ├── profile.json     # 个性/基本属性（创建后不可变）
│   │   ├── SOUL.md          # 人格描述（从 profile 生成）
│   │   ├── MEMORY.md        # 个人记忆（Dream 进程维护）
│   │   ├── history.jsonl    # 个人活动存档（追加 JSONL）
│   │   └── skills/
│   │       ├── manifest.json # 技能清单 {技能名: 标签}
│   │       └── {skill}.md   # 技能实现
│   │
│   └── {agent_id2}/
│
├── scenes/
│   └── {scene_id}/
│       ├── CONTEXT.md       # 场景上下文
│       ├── mounted_kbs.json  # 此场景挂载的知识库列表
│       ├── skills/
│       │   └── manifest.json # env 标签技能
│       └── roster.json      # 在此场景工作的员工
│
├── knowledge/
│   └── {kb_id}/
│       ├── schema.md        # 知识库结构规则
│       ├── purpose.md       # 知识库目标
│       ├── index.md         # 内容目录
│       ├── raw/sources/     # 原始文件（用户投放）
│       ├── wiki/            # LLM 整理后的知识
│       │   ├── entities/
│       │   ├── concepts/
│       │   ├── sources/
│       │   └── ...
│       └── log.md
│
└── .git/                    # dulwich 版本控制
```

### Key Patterns (inherited from nanobot)

| Pattern      | nanobot                          | CocoCat Adaptation                          |
|-------------|----------------------------------|---------------------------------------------|
| SOUL.md     | Single agent personality         | Per smart employee                          |
| MEMORY.md   | Single-layer persistent memory   | Three-layer: personal + scene + team        |
| history.jsonl | Append JSONL with cursor       | Personal activity + group chat (separate)   |
| Dream       | Async: history → MEMORY.md updates | Personal Dream per agent + Team Dream       |
| Consolidator| Token-budget compression         | Same, per-agent history                     |
| GitStore    | dulwich versioning               | Same, all .md and .json files tracked       |
| Cursor      | `.cursor` / `.dream_cursor`      | Same, per-agent independent                 |

## Knowledge Base System (llm_wiki-inspired)

### Three-Layer Architecture

| Layer     | Path                   | Description                   |
|-----------|------------------------|-------------------------------|
| Raw       | `knowledge/{kb}/raw/`  | Immutable source files        |
| Wiki      | `knowledge/{kb}/wiki/` | LLM-generated structured pages|
| Config    | `knowledge/{kb}/`      | schema.md, purpose.md, index.md |

### Page Types

| Type      | Directory                   | Description                |
|-----------|-----------------------------|----------------------------|
| entity    | `wiki/entities/`            | Named things               |
| concept   | `wiki/concepts/`            | Ideas, techniques          |
| source    | `wiki/sources/`             | Per-ingested-file summaries|
| query     | `wiki/queries/`             | Q&A entries                |

### Ingestion Workflow

```
User drops files to knowledge/{kb}/raw/sources/
  │
  ▼
User: "add these to KB X" / "create new KB Y"
  │
  ▼
Leader picks up → checks schedule → assigns to available employee
  │
  ▼
Employee runs two-phase Ingest (llm_wiki CoT):
  Phase 1 (Analysis): read source → extract entities/concepts → relate existing content
  Phase 2 (Generation): create/update wiki pages with frontmatter + content
  │
  ▼
Update index.md, log.md → git commit
```

### Scene-KB Mounting

- `scenes/{scene}/mounted_kbs.json` lists KBs active in this scene
- Employee working in a scene can **only** search mounted KBs
- Search: token search + optional vector search (LanceDB) → RRF fusion

### AGENT_ROSTER.md

Maintained by Team Dream process (like nanobot's Dream), every agent reads this to know:
- What every other agent is good at
- Their current status (idle/busy)
- Their skill tags (public/private)

## Communication Architecture

### Two-Layer Design

```
                     ┌──────────────┐
                     │  群聊显示面板  │  ← Human-readable display layer
                     │  (聊天框)     │
                     └──────┬───────┘
                            │ Auto-derived display text
                     ┌──────▼───────┐
                     │ Rust Message │  ← Structured inter-agent data
                     │ Bus          │    (full information, not display text)
                     └──────────────┘
```

- **Underlying communication**: Agents exchange structured JSON via Rust message bus
  - Full task details, document references, status updates, priority levels
  - NOT limited to human-readable text
  - "The more information the better" between agents
- **Display layer**: Chat panel auto-derives human-readable messages from the structured communication
  - Shows `@员工A 请处理 API 文档` but underlying message contains `{task_type: "kb_ingest", source_paths: [...], target_kb: "product_docs", priority: "high", ...}`
- **Knowledge of peers**: Every agent reads `AGENT_ROSTER.md` to know team members' skills
  - When A needs code review, A reads roster → knows B has `code_review` skill → sends structured request via message bus → chat displays the interaction

## Skill System

### Tag System

| Tag     | Location                                     | Effect                          |
|---------|----------------------------------------------|---------------------------------|
| public  | Every agent's `manifest.json`               | Mandatory for all               |
| private | Specific agent's `manifest.json`            | Agent-exclusive                 |
| env     | `scenes/{scene}/skills/manifest.json`       | Auto-loads on scene entry       |

### Lifecycle

- **Learn**: Leader/panel assigns skill → agent learns it → added to manifest
- **Forget**: Agent or leader can initiate forgetting → removed from manifest
- **Tags can change**, personality cannot (immutable after creation)

## UI Design (paperclip-inspired)

### Layout

```
┌──────┬────────────────────────────────────────────┐
│ Rail │  Sidebar                 │  Main Content    │
│  48px│  collapsible 240px       │  scrollable      │
├──────┼────────────────────────────────────────────┤
│  🏢  │  CocoCat 团队            │  Page Content    │
│      │  ├ 面板                  │                  │
│  🏢  │  ├ 场景管理              │                  │
│      │  ├ 员工管理              │                  │
│  🏢  │  ├ 知识库                │                  │
│      │  └ 交流群                │                  │
│      │  ─────────────────────── │                  │
│  👤  │  员工列表                │                  │
│      │  ● 组长 (在线)           │                  │
│      │  ● 员工A (忙碌)          │                  │
│      │  ○ 员工B (空闲)          │                  │
└──────┴────────────────────────────────────────────┘
```

### Aesthetic (paperclip-inspired)

- Zero border-radius (`--radius: 0`), sharp modern look
- Monochrome/grayscale base with oklch color space
- Tailwind CSS v4 + shadcn/ui (New York) + Radix UI + Lucide icons
- Light/dark mode

## Hiring Flow (paperclip-inspired)

```
Leader initiates hire → fills role requirements (role, desired skills)
  │
  ▼
Leader configures personality → generates SOUL.md from profile
  │
  ▼
Employee created → auto-provisioned with:
  ├ SOUL.md (personality, immutable)
  ├ MEMORY.md (empty memory)
  ├ skills/manifest.json (public skills auto-included)
  └ access to team chat + initial scene
```

## Implementation Order

1. Rust Core Engine (agent manager, message bus, file structure)
2. Python Agent Runtime (agent logic, LLM client, basic behavior)
3. Memory System (personal memory, history, cursor-based JSONL, Dulwich GitStore)
4. Skill System (manifest, tags, learn/forget)
5. Scene System (create scene, mount KBs, assign agents, scene context)
6. Knowledge Base (llm_wiki-inspired ingestion pipeline, search)
7. Team Leader Agent (scheduling, task assignment, hiring)
8. Communication (Rust message bus, group chat panel)
9. Dream/Consolidator (personal + team memory maintenance)
10. Web Panel (FastAPI frontend for all management)
