# CocoCat Architecture: Unified Design

2026-05-09

A clear, minimal architecture for a multi-agent collaboration platform with the core model: **Main AI distributes tasks, Sub AIs execute in Scenes with KBs and Skills.**

## Design Principles

| Principle | Meaning |
|-----------|---------|
| **Single Python process** | No Rust layer, no subprocess-per-agent. Agents are Python objects in one asyncio event loop. |
| **Agent = Python object, not process** | Inspired by Hanako. An agent is a class instance with an id, profile, and a run method — not a forked subprocess. |
| **Session-based execution** | Each user message creates a short-lived session. Agent runs, returns result, session ends. No persistent long-running agent loop. |
| **File system as content store, SQLite as state store** | KB wiki, skill .md files, scene config live on disk for transparency. Agent state, message history, task tracking live in SQLite. |
| **EventBus over protocols** | Simple asyncio pub/sub for internal communication. No stdin/stdout JSON-RPC, no internal HTTP between components. |
| **KISS tools** | Tools are `{name, description, execute async fn}` objects. Flat array, no class hierarchy. |

## Core Model

```
                        用户                        外部渠道
                         │                            │
                         ▼                            ▼
                  ┌─────────────┐            ┌──────────────┐
                  │   主 AI      │            │  Scene 渠道   │
                  │  (永不绑场景) │            │  (WeChat等)  │
                  │  全局KB/Skills│           └──────┬───────┘
                  └──────┬──────┘                   │
                         │ 分配任务给空闲副AI         │ 直接对话绑定的副AI
         ┌───────────────┼───────────────┐           │
         ▼               ▼               ▼           ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐ ┌──────────┐
   │ 副 A(空) │   │ 副 B(空) │   │ 副 C(空) │ │ 副 D     │
   │ 全局权限  │   │ 全局权限  │   │ 全局权限  │ │ (工作)   │
   └──────────┘   └──────────┘   └──────────┘ └────┬─────┘
                                                   │
                                              绑定 Scene
                                              仅场景KB + 场景Skills + 自带Skills
                                              通过场景渠道回复外界
```

### Agent Types

| Role | State | KB Access | Skills Access | Dialogue Entry |
|------|-------|-----------|---------------|----------------|
| **Main AI** | Always online, never bound to a scene | All KBs (global) | All Skills (global) | Direct user chat (Web UI / CLI) |
| **Sub AI (idle)** | Not bound to any scene | All KBs (global) | All Skills (global) | Receives tasks assigned by Main AI |
| **Sub AI (working)** | Bound to a specific scene | Scene KBs only | Scene Skills + own Skills | Scene channel messages |

### Rules

1. **Main AI is sole user interface.** Users always talk to Main AI. Main AI never enters a scene.
2. **Sub AI 1:1 binding with scene.** A sub AI can only be bound to one scene at a time. When bound (= working state), Main AI cannot assign it new tasks.
3. **Sub AIs do not collaborate with each other.** Each sub AI works independently. For complex tasks, a sub AI can spawn **temporary sub-sub-agents** (local fork, not pooled agents).
4. **Permission scoping at bind time.** When a sub AI binds to a scene, its permissions switch immediately: only scene KBs + scene skills + own skills. When unbound (idle), permissions revert to global (all KBs, all skills). When Main AI assigns a task to an idle sub AI, the sub AI executes with **global permissions** — it is not bound to a scene during task execution.
5. **Scene channel messages are serial per scene.** If two messages arrive simultaneously via the same scene's channels, they are queued and processed sequentially by the bound sub AI. The first message completes (agent runs → returns reply) before the second begins.

## Agent Architecture (Hanako-inspired)

### Agent Instance Model

An agent is a Python class instance — NOT a subprocess:

```python
class Agent:
    id: str
    name: str
    role: "main" | "sub"
    state: "idle" | "working"
    bound_scene: str | None
    profile: dict          # from profile.yaml
    session_dir: str       # where session JSONL files go
    
    async def init(self):
        """One-time setup: compile system prompt, load tools."""
        self._system_prompt = await self._build_system_prompt()
        self._tools = self._build_tools()
    
    async def run(self, message: str, context: SessionContext) -> str:
        """Create a session, run the agent loop, return result."""
        session = Session.create(self._system_prompt, self._tools, context)
        result = await session.prompt(message)
        session.close()
        return result
```

### No Persistent Agent Loop

Unlike the current CocoCat (which has `agent_runtime.py` with `_mailbox_poll_loop` + `_control_poll_loop` background threads), agents are **purely reactive**:

- A message arrives → `agent.run(message)` is called → agent executes → returns result → agent goes idle
- No background polling. No waiting for inbox changes.
- Between messages, the agent is just an object in memory with cached state.

**Exception: Heartbeat.** See below.

### Heartbeat

Agents can autonomously perform background work during idle periods. This is the only persistent background activity — a lightweight scheduled wake-up, not a busy polling loop.

Only the **Main AI** has heartbeat. Sub AIs are purely reactive — they work when called, idle when not.

- **How it decides what to do**: Main AI reads its `heartbeat.md` — a list of responsibilities and focus areas. It evaluates current system state against this list and decides what actions to take.
- **Interval**: Every 15 minutes (configurable).
- **Log**: Each heartbeat session appends a summary to `heartbeat.log`.
- **heartbeat.md** is editable via the Schedule window in Web UI. Main AI can also update it itself (e.g., add new focus areas it discovers).

```
agents/main/
  heartbeat.md      # Main AI's responsibilities & focus areas
  heartbeat.log     # Append-only record of heartbeat sessions
```

### Session Model

Sessions are per-user: each external user (or the local user) has their own session directory and memory. Agent loads user context by `user_id` at session start.

```
agents/main/users/
  local/                            # Web UI user (you)
    sessions/{uuid}.jsonl           # Full turn history
    memory.md                       # Compiled personal memory
    memory/today.md / week.md / longterm.md / facts.md

  {channel_user_id}/                # Channel user (WeChat / ilink / Feishu)
    sessions/{uuid}.jsonl
    memory.md

scenes/{scene_id}/users/
  {channel_user_id}/                # External user via scene channel
    sessions/{uuid}.jsonl
    memory.md
```

- Sessions created on-demand, torn down after completion.
- Cached in memory with LRU eviction (max ~10 active sessions).
- JSONL entries: system prompt, user message, assistant response, tool calls, tool results.
- Memory (`memory.md`) is per-user: Main AI loads different memory for different users; scene sub AI loads the external user's memory.

### System Prompt (Prompt Caching Friendly)

Ordered for maximum LLM cache reuse:

```
[STATIC PREFIX — identical across all sessions for same agent]
  1. Platform intro role
  2. Tool usage discipline  
  3. Safety rules
  4. Action guidelines
━━━━━━━━ KV/Anthropic cache line ━━━━━━━━
[DYNAMIC SUFFIX — varies per session]
  5. Agent profile (identity, personality)
  6. Current scene context (if bound)
  7. Scene KB overview (if bound) or All KBs (if idle)
  8. Skill descriptions (scoped to agent's current permissions)
  9. Recent memory / pinned facts
  10. Current date/time
```

### Workspace

All agents share a single workspace (`workspace/`). Main AI and sub AIs see the same filesystem. This is intentional: when a user uploads a file to Main AI, it can immediately delegate processing to a sub AI without copying files between isolated directories.

- File tools (`read_file`, `write_file`, `edit_file`, `bash`) operate within the workspace directory.
- Path traversal outside the workspace is blocked.
- Workspace is browsable from the Chat Page right panel.

### Tool System

All tools are flat objects: `{name, description, parameters, execute}`. No class hierarchy. Categorized as core (always present) or optional.

#### Core Tools (always available)

| Tool | Category | Description |
|------|----------|-------------|
| `read_file` | File | Read file with offset/limit, supports text + images + PDF/DOCX/XLSX/PPTX |
| `write_file` | File | Write content, create parent directories |
| `edit_file` | File | String-replace edit with multi-level fallback matching |
| `list_dir` | File | List directory contents, recursive option |
| `bash` | Shell | Execute shell command with timeout, sandbox, env isolation |
| `glob` | Search | Find files by glob pattern, sorted by mtime |
| `grep` | Search | Search file contents with regex, context lines |
| `web_search` | Web | Multi-backend search with auto-fallback |
| `web_fetch` | Web | Fetch URL content, SSRF protection, readability extraction |
| `browser` | Browser | Navigate, click, fill, extract, screenshot, scroll (persistent session) |
| `sub_agent` | Orchestration | **Async** fire-and-forget: spawn sub-agent, continue working, receive result via callback |
| `check_tasks` | Orchestration | Query status of pending async sub-agent tasks |
| `stop_task` | Orchestration | Cancel a running background task |
| `todo_write` | Planning | Structured task list with pending/in_progress/completed states |
| `recall` | Memory | Search memory by keyword (FTS5 on facts table) |
| `pin` / `unpin` | Memory | Pin/unpin facts for persistent context injection into system prompt |
| `record_experience` | Memory | Record categorized experience entry (deduplicated) |
| `recall_experience` | Memory | Recall experience entries by category or listing index |
| `cron` | Scheduling | Schedule recurring/one-shot tasks (at/every/cron expr) |
| `current_status` | System | Runtime introspection: agent model, time, scene, pending tasks |
| `wait` | Utility | Sleep for specified seconds |

#### Optional / Contextual Tools

| Tool | Category | When Available |
|------|----------|----------------|
| Scene skills | Skill | Only when agent is bound to a scene or scene skills are explicitly loaded |
| Global skills | Skill | Available to Main AI and idle sub AIs |

#### Removed (from old CocoCat)

| Tool | Reason |
|------|--------|
| `hire_agent` | Use UI settings to create agents instead |
| `dispatch_task` | Tied to old Rust dispatch engine; replaced by EventBus |
| `lsp_query` | Requires LSP server setup, low usage |
| `send_delivery` | Niche admin function |
| `send_message` | Replaced by in-process EventBus |
| `ask_user` | Replaced by direct chat UI interaction |
| `dream` | Moved to background auto-trigger (memoryTicker), not a user tool |

#### Key Change: Async Sub-agent

`sub_agent` is now **asynchronous** (aligned with Hanako/Nanobot):

```
Main AI calls sub_agent(task="查退款流程", agent="agent_a")
  → Returns immediately with task_id
  → Main AI continues working (can spawn more sub-agents in parallel)
  → When sub-agent completes, result delivered via EventBus callback
  → Main AI calls check_tasks() to collect completed results
```

## Scene Architecture

### Scene Definition

```yaml
# scenes/{id}/scene.yaml
id: customer-service
name: Customer Service
context: |
  You are handling customer inquiries for...
  (Markdown system prompt injected into bound sub AI's context)
roster:
  - agent_a
  - agent_c
kbs:
  - product-manual
  - faq
skills:
  - crm-lookup
  - refund-procedure
channels:
  - type: wechat
    config: {...}
```

### Scene File Layout

```
scenes/{id}/
  scene.yaml          # Scene config (roster, KBs, skills, channels, context)
  channels/           # Channel-specific configs
    wechat.yaml
```

### Scene Lifecycle

```
Scene Created
  │
  ▼
IDLE ──── 渠道消息进入 ────▶ Select free agent from roster → Bind agent → BUSY
  │                               │
  │                           Agent processes → replies via channel
  │                               │
  │                           Conversation ends / timeout
  │                               │
  │                           Agent unbound → Scene back to IDLE
  ▼
Deleted / Archived
```

### Scene Concurrency

- **One bound sub AI per scene.** A scene's channels share the same bound sub AI.
- **Serial message processing.** Incoming channel messages per scene are queued as FIFO. Messages from different users within the same scene are processed sequentially — one completes before the next begins.
- **Queue persistence in SQLite.** The message queue is stored in the `messages` table with `status` column (`pending` → `processing` → `replied`). On restart, pending messages are reloaded from DB. No message loss.
- **WeChat passive reply timeout.** WeChat 公众号 requires a passive reply within 5 seconds. If the bound sub AI is busy processing a prior message when a new WeChat message arrives, the passive reply window is missed. In this case, CocoCat sends the reply via WeChat's proactive customer service API instead (bypassing the 5s limit). Other channels (ilink, Feishu) have no passive timeout and use their standard reply path.
- **User identity preserved.** Queue items track `user_id` and `channel_type` so the reply is routed back to the correct external user via the correct channel.

## KB Architecture (llm-wiki aligned)

### Core Principles

- **Two-phase ingest**: Analysis (LLM reads source, produces structured analysis) → Generation (LLM takes analysis as context, produces wiki files). Separate LLM calls with different system prompts ("research analyst" vs "wiki maintainer").
- **Deterministic where possible**: Frontmatter array union, path safety, file block parsing, sanitization are programmatic. LLM handles only content decisions.
- **Defense in depth**: Cache, backup, sanitize, validate at every step. Never trust LLM output blindly.
- **Filesystem as store**: wiki pages are markdown files with YAML frontmatter. Transparent, git-friendly, agent-readable.

### File Structure
```
knowledge/{kb_name}/
  .llm-wiki/
    ingest-cache.json          # SHA256 source → last written file list
    ingest-queue.json          # Persistent queue with crash recovery
    dedup-queue.json           # Dedup task queue
    dedup-not-duplicates.json  # Whitelist: confirmed non-duplicate pairs
    page-history/              # Pre-modification backup snapshots
      {sanitized-path}-{timestamp}.md
      dedup-{timestamp}/       # Dedup batch backups

  purpose.md                   # KB goals, scope, key questions
  schema.md                    # Wiki conventions (naming, frontmatter, linking)
  index.md                     # Auto-maintained entity/concept catalog
  overview.md                  # Auto-regenerated 2-5 paragraph global summary
  log.md                       # Append-only operation log

  raw/sources/                 # Original uploaded files
    {filename}                 # Raw binary
    {filename}.md              # Extracted text with YAML frontmatter

  wiki/
    entities/                  # Named things (agents, tools, projects, people)
      {slug}.md
    concepts/                  # Ideas, patterns, techniques
      {slug}.md
    sources/                   # Source-summary pages
      {slug}.md
    queries/                   # Persistent query pages
      {slug}.md
    synthesis/                 # Synthesized topic pages
      {slug}.md
    comparisons/               # A vs B comparison pages
      {slug}.md
```

### Wiki Page Format

```yaml
---
type: entity
title: "Human Title"
created: "2026-05-09"
updated: "2026-05-09"
tags: ["tag1", "tag2"]
related: ["other-slug-1"]
sources: ["source-filename.md"]
summary: "One-line description"
---
# Human Title

Body content with [[wikilink]] cross-references...

## See Also
- [[other-slug-1]]
```

### Ingest Pipeline (8 Steps)

1. **Upload & Extract**: Raw file → `raw/sources/{filename}`. Python text extraction (PDF, DOCX, XLSX, PPTX, HTML) → `{filename}.md` with YAML frontmatter.

2. **Queue & Cache**: SHA256 hash of source content checked against `.llm-wiki/ingest-cache.json`. If hash matches and all previously-written files still exist → skip LLM, return cached result. Otherwise push to `ingest-queue.json`.

3. **Phase 1 — Analysis**: LLM with "research analyst" prompt reads:
   - Source text
   - Existing index.md (all pages)
   - purpose.md
   - Related existing wiki pages
   Produces structured analysis: key entities (name, type, role), key concepts (definition, significance), main arguments, connections to existing wiki, contradictions, recommendations for page creation/update.

4. **Phase 2 — Generation**: LLM with "wiki maintainer" prompt receives the analysis as context. Produces `---FILE:` blocks — one per wiki file to create or update. Structured output parser handles CRLF, stream truncation, fence-awareness, path-traversal rejection.

5. **Sanitization** (programmatic, before writing):
   - Fix code-fence-wrapped YAML frontmatter (strip ```yaml...``` wrappers)
   - Fix `frontmatter:` key prefix
   - Fix invalid YAML wikilink lists (`related: [[a]], [[b]]`)
   - Validate minimum body length

6. **Page Merge & Write**: For existing pages being updated:
   - **Frontmatter array union** (deterministic): `sources[]`, `tags[]`, `related[]` always merged.
   - **Body merge** (LLM): if bodies differ, LLM merges coherently with sanity check (result ≥ 70% of max(old, new) or reject).
   - **Locked fields**: `type`, `title`, `created` preserved from existing page.
   - **Backup**: pre-merge snapshot saved to `.llm-wiki/page-history/`.
   - New pages: write directly (no merge needed).

7. **Index & Overview Update**: `index.md` updated with new/updated entries. `overview.md` auto-regenerated (2-5 paragraph global summary). `log.md` appended with operation record.

8. **Cache Write**: SHA256 + written file list saved to `ingest-cache.json`. Cache write skipped if any block had disk failure (prevents freezing partial results).

### Dedup Pipeline (3 Stages)

1. **Summarize**: Extract (slug, title, description, tags) from every entity/concept page.
2. **Detect**: LLM identifies groups of likely-duplicate slugs with reason + confidence (high/medium/low). "Not duplicates" whitelist persisted to avoid re-suggesting dismissed pairs.
3. **Merge**: LLM merges bodies (union frontmatter, rewrite every wikilink/related/index entry across whole wiki). Backup snapshots saved before any destructive action.

### Cascade Deletion

When a source file is removed:
1. Delete its wiki page(s)
2. Remove all cross-references ([[wikilink]]) from other pages
3. Clean `related:` frontmatter arrays across all pages
4. Update `index.md` and `overview.md`
5. Clean up dedup state if affected

### Ingest Queue (Crash-Safe)

- Persistent JSON file (`ingest-queue.json`)
- Serial processing (prevents concurrent LLM race on wiki files)
- Crash recovery: in-flight tasks reverted to "pending" on restart
- Retry: up to 3 attempts per item
- Cancel with partial-file cleanup
- Project-switch pause/restore (flush state to disk)

### Image Pipeline

- Extract embedded images from PDF/PPTX/DOCX during text extraction
- Vision LLM captioning with SHA256 cache (shared logos/charts captioned once)
- Captions injected into source-summary pages
- Re-embedded after caption refresh

### Lint System

Automated health checks:
- Orphan pages (no inbound links)
- Broken wikilinks (point to non-existent page)
- Missing frontmatter fields
- Semantic issues (outdated summaries, contradictory facts)
- Run on schedule or on-demand

### Knowledge Graph

- 4-signal relevance scoring: direct links x3.0, source overlap x4.0, Adamic-Adar x1.5, type affinity x1.0
- Louvain community detection
- Graph insights: surprising connections, knowledge gaps, bridge nodes
- Visualized in Web UI

## Channel Architecture

### Principle

One mechanism, two targets. All channels share the same adapter pattern. A `target` field determines whether messages route to Main AI or a scene's bound sub AI.

### Channel Config

```yaml
# Scene config (scene.yaml) — channels that belong to a scene
channels:
  - type: wechat
    config:
      app_id: "xxx"
      app_secret: "xxx"

  - type: weixin
    config:
      qr_login: true

  - type: feishu
    config:
      app_id: "xxx"
      app_secret: "xxx"

# Main AI config — channels that connect to the main AI
channels:
  - type: telegram    # future
    target: main
```

### Routing

```
Channel message received
  │
  ├── target is scene → find bound sub AI → agent.run()
  │     (sub AI uses scene KB + scene skills + own skills)
  │
  └── target is main → Main AI.run()
        (Main AI has global KB + global skills)
```

### Supported Channels

| Channel | Status | Target |
|---------|--------|--------|
| WeChat 公众号 | Active | Scene / Main |
| WeChat ilink (个人微信) | Active | Scene / Main |
| Feishu | Active | Scene / Main |

### Channel Capabilities (full target)

#### WeChat 公众号

| Direction | Type | Capability |
|-----------|------|------------|
| Receive | text | Plain text message |
| Receive | image | Download via `media_id` + media API |
| Receive | voice | Download + speech recognition (WeChat built-in) |
| Send | text | Passive XML reply (within 5s) + proactive push via customer service API |
| Send | image | Via customer service message API |
| Send | voice | Via customer service message API |
| Send | news | Rich card with title/description/url/image |

#### WeChat ilink (个人微信)

| Direction | Type | Capability |
|-----------|------|------------|
| Receive | text | Plain text message |
| Receive | image | CDN download + AES decryption |
| Receive | voice | CDN download + AES decryption |
| Receive | file | CDN download + AES decryption |
| Receive | video | CDN download + AES decryption |
| Receive | text+media | Combo messages (text with attached media) |
| Receive | sticker | Emoji/sticker (render as description text) |
| Send | text | Chunked for long messages (4000 char chunks) |
| Send | image | CDN upload + send |
| Send | file | CDN upload + send |
| Send | video | CDN upload + send |
| Send | card | Mini-program card / link card |

#### Feishu

| Direction | Type | Capability |
|-----------|------|------------|
| Receive | text | Plain text |
| Receive | post | Rich text with embedded images/links |
| Receive | image | Download via `image_key` |
| Receive | audio | Download via `file_key` |
| Receive | file | Download via `file_key` |
| Receive | media | Video download |
| Receive | share | Link/share card |
| Receive | sticker | Animated sticker |
| Send | text | Plain text via REST API |
| Send | post | Rich text with formatting, images, links |
| Send | interactive | CardKit cards with markdown, tables, buttons, forms |
| Send | image | Upload + send |
| Send | audio | Upload + send |
| Send | file | Upload + send |
| Send | media | Video upload + send |
| **Advanced** | | |
| Streaming | typewriter | CardKit card with progressive text update (streaming LLM output) |
| Reaction | emoji | Thumbsup / Done / custom emoji reactions on messages |
| Thread | reply | Threaded reply in group chats |
| Group | @mention | Detect and respond to @mentions in group chat |
| Dedup | idempotency | OrderedDict-based message deduplication |

### Channel Adapter Pattern

```python
class ContextType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    IMAGE_CREATE = "image_create"
    FILE = "file"
    VIDEO = "video"
    SHARING = "sharing"

class ReplyType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    IMAGE_URL = "image_url"
    FILE = "file"
    VIDEO = "video"
    VIDEO_URL = "video_url"
    ERROR = "error"
    INFO = "info"

class ChatMessage:
    channel_type: str       # "wechat" | "weixin" | "feishu"
    scene_id: str
    user_id: str            # Platform user ID
    content: str            # Text content (or placeholder for media)
    msg_type: str           # "text" | "image" | "voice" | "file" | "video"
    msg_id: str             # Unique message ID (for dedup)
    extra: dict             # Platform-specific payload
                            # - image: {"media_id": "...", "url": "..."}
                            # - voice: {"media_id": "...", "format": "amr"}
                            # - file: {"media_id": "...", "filename": "..."}
                            # - video: {"media_id": "...", "thumb_id": "..."}
                            # - share: {"url": "...", "title": "..."}

class Channel:
    target: str          # "main" or "scene:{scene_id}"
    
    async def start(self, config: dict)
    async def stop(self)
    async def send_text(self, user_id: str, content: str)
    async def send_image(self, user_id: str, file_path: str)
    async def send_file(self, user_id: str, file_path: str, filename: str)
    async def send_card(self, user_id: str, card_data: dict)
    
    # Called by framework when message arrives
    on_message: Callable[[ChatMessage], Awaitable[None]]
```

## Provider Architecture (Hanako-inspired)

### Design Principles

- **Plugins, not hardcode**: Each provider is a declarative spec. Adding a new OpenAI-compatible provider = one entry in a registry.
- **Data drives behavior**: Model capabilities (context window, vision, reasoning, quirks) come from JSON metadata, not code.
- **Shared compat normalization**: Chat path and utility path use the same `normalizeRequest()` function. No drift.
- **Retry everywhere**: Smart transient detection, exponential backoff + jitter, Retry-After parsing, non-retryable error triage.

### Provider Registry

Flat declarative list. Each provider:

```python
@dataclass
class ProviderSpec:
    name: str                    # "openai", "deepseek", "anthropic"
    keywords: list[str]          # ["deepseek", "deepseek-chat"] ← for auto-detection
    env_key: str                 # "OPENAI_API_KEY" ← env var fallback
    display_name: str            # "OpenAI"
    backend: str                 # "openai_compat" | "anthropic"
    default_api_base: str        # "https://api.openai.com/v1"
    supports_streaming: bool
    auth_type: str               # "api_key" | "oauth" | "none" | "optional"
```

**Auto-detection priority chain**:
1. Model-name keyword match (e.g., `"deepseek-chat"` matches keyword `"deepseek"`)
2. Environment variable detection (`os.environ.get(spec.env_key)`)
3. First provider with any API key configured
4. Ultimate fallback (first in registry)

### Model Routing (4 Roles)

| Role | Purpose | Model Selection | Thinking |
|------|---------|-----------------|----------|
| `chat` | Primary conversation | Per-agent config `models.chat` | Enabled |
| `utility` | Lightweight tasks (50-200 token outputs: summarization, classification) | Per-agent `models.utility` or global pref | **Disabled** (wasteful for short outputs) |
| `utility_large` | Heavy analysis (complex reasoning, compilation) | Per-agent `models.utility_large` or global pref | Enabled |
| `embed` | Embedding generation for search/memory | Global config | N/A |

**Resolution order**: agent config → global preferences → fallback to chat model

### Credential Management

```
auth.json → {
    "openai": "sk-...",       // Can be literal key or "${OPENAI_API_KEY}"
    "deepseek": "${DEEPSEEK_API_KEY}",
    "ollama": ""              // auth_type: "none" — no key needed
}
```

- `${ENV_VAR}` resolved at read time (regex pattern match)
- Config files `chmod 600` on write
- Web UI masks keys: `sk-a●●●●1234`
- `auth_type: "none"` / `"optional"` or localhost base_url → skip credential check
- OAuth tokens managed separately (if adding OAuth providers later)

### Provider Compat Layer

Each provider with API quirks gets a small, self-contained sub-module:

```python
# provider_compat/deepseek.py
def matches(model_id: str) -> bool: ...
def apply(request: dict, model_id: str, options: dict) -> dict: ...
```

| Module | What it handles |
|--------|----------------|
| `deepseek` | Thinking format (`thinking: {type: "enabled"/"disabled"}`), reasoning_effort mapping |
| `anthropic` | Prompt caching markers, message format translation |
| `qwen` | Video URL normalization, utility thinking disable |
| `output_budget` | Generic max_tokens stripping for providers where optional |

**Rules**:
- First-match-wins dispatch (more specific first)
- Return same object if no change needed (immutability)
- Both chat (streaming) and utility (direct HTTP) go through the same `normalizeRequest()`
- Adding a new quirky provider = one 50-150 line module, no changes elsewhere

### Model Metadata Enrichment

Model capabilities (context window, vision support, reasoning, quirks) stored as JSON metadata, not hardcoded. `quirks` field drives compat module dispatch. Adding model knowledge = JSON update, not code change.

### Model Sync Pipeline

User config → `syncModels()` → SDK-format `models.json` → `ModelRegistry` → agent runtime. Atomic write (tmp + rename). Change detection prevents unnecessary refreshes.

### Streaming & Retry

- **Streaming**: SSE parsing, non-streaming fallback, configurable idle timeout
- **Retry**: Exponential backoff + jitter. Smart transient detection (retries on 429/408/409/5xx, skips quota/billing). Retry-After header parsing. Image-stripping fallback for non-vision models.
- **Two modes**: `standard` (bounded retries) and `persistent` (unlimited, for critical operations)
- Detailed retry parameters (delays, max counts, heartbeat intervals) defined in implementation plan, not here.

## Vision Bridge (Hanako-inspired)

### Problem

Users send images to agents. The agent may be using a text-only model (cheaper, faster). Without a vision model, images are invisible to the agent.

### Solution

A dedicated **vision auxiliary model** preprocesses all images before they reach the chat model.

```
User sends image
  │
  ▼
Before LLM call: scan messages for image content
  │
  ├── Chat model supports images? → send image directly (native path)
  │
  └── Chat model is text-only? → Vision Bridge
        │
        ▼
      Vision model analyzes image:
        ├── image_overview: what's in the image
        ├── visible_text: OCR'd text
        ├── objects_and_layout: spatial description
        ├── charts_or_data: data/chart interpretation
        └── visual_primitives: bounding boxes (if model supports grounding)
        │
        ▼
      Structured notes injected into prompt as <vision-context>
      Original image stripped from messages
      Chat model now "sees" the image through text notes
```

### Output Modes

| Mode | When | Output |
|------|------|--------|
| Plain text note | Vision model has no grounding capability | Structured text (overview, OCR, layout, data) |
| With primitives | Vision model supports grounding | Same + `<visual-primitives>` XML with normalized coordinates (0-1000) |

### Protocol Auto-Detection

Vision model output format is auto-detected from model metadata:
- `hanako` — `{ id, type, ref, box, confidence }`
- `gemini` — `box_2d` with `[ymin, xmin, ymax, xmax]`
- `qwen` — `bbox_2d` as `[x1, y1, x2, y2]`

All normalized to `xyxy` order, clamped to 0-1000.

### Caching & Policy

- In-memory LRU cache keyed by (image hash, user_prompt, model_signature) — max 256 entries. Same image with different user prompts is cached separately (the vision model's analysis depends on what the user asked about the image).
- Persistent sidecar: `agents/{agent_id}/sessions/{session_id}-vision-notes.json` — survives restarts within the session.
- **`vision_enabled` toggle**: controls whether the Vision Bridge runs at all.
  - `vision_enabled=true` + vision model configured → Vision Bridge preprocesses images.
  - `vision_enabled=true` + no vision model configured → images stripped, a placeholder `[image: user sent an image but no vision model is configured]` is injected into the prompt. No error — graceful degradation.
  - `vision_enabled=false` + chat model is vision-capable → images sent natively (no bridge needed).
  - `vision_enabled=false` + chat model is text-only → images stripped, a placeholder `[image: user sent an image but vision is disabled]` is injected. No error.
- Separate vision model config (independent provider/key/model from chat model).

### Fallback Chain

When an image is present in the message and the chat model is text-only:

1. `vision_enabled=false` → strip image, inject `[image: vision disabled]` placeholder.
2. `vision_enabled=true` + vision model configured → Vision Bridge runs, injects structured notes.
3. `vision_enabled=true` + vision model NOT configured → strip image, inject `[image: no vision model configured]` placeholder.

At no point does the system throw a hard error that blocks the chat flow.

## Communication Architecture

```
┌────────────────────────────────────────────────┐
│                  EventBus                       │
│  events: message, task, state_change, ...       │
│                                                  │
│  ┌──────────┐   ┌──────────┐   ┌─────────┐     │
│  │ Agent     │   │ Agent    │   │ Channel │     │
│  │ (Main AI) │   │ (Sub AI) │   │ Adapter │     │
│  └──────────┘   └──────────┘   └─────────┘     │
└────────────────────────────────────────────────┘
```

Simple asyncio pub/sub. No external message broker. No mailbox JSONL files. All agents (Main + Sub) and channel adapters communicate through the same event bus.

### API Endpoints

All endpoints served by FastAPI on a single port. No authentication required — CocoCat runs as a local tool.

#### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message to Main AI |
| GET | `/api/chat/history` | List past conversations (paginated) |
| GET | `/api/chat/history/{id}` | Load specific conversation |

#### Agents
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents with status |
| GET | `/api/agents/{id}` | Agent detail (profile, state, bound scene) |
| PATCH | `/api/agents/{id}` | Update agent config (name, model, identity) |
| POST | `/api/agents` | Create new sub agent |

#### Scenes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scenes` | List scenes |
| POST | `/api/scenes` | Create scene |
| GET | `/api/scenes/{id}` | Scene detail (kbs, skills, channels, context) |
| PATCH | `/api/scenes/{id}` | Update scene config |
| DELETE | `/api/scenes/{id}` | Delete scene |
| PATCH | `/api/scenes/{id}/kbs` | Mount/unmount KBs |
| PATCH | `/api/scenes/{id}/skills` | Add/remove scene skills |

#### Knowledge Base
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/knowledge` | List KBs |
| POST | `/api/knowledge` | Create new KB |
| DELETE | `/api/knowledge/{name}` | Delete KB |
| POST | `/api/knowledge/{name}/upload` | Upload file for ingestion |
| GET | `/api/knowledge/{name}/wiki` | Wiki index (entities + concepts) |
| GET | `/api/knowledge/{name}/wiki/{type}/{page}` | Read wiki page |
| GET | `/api/knowledge/{name}/search?q=` | Search KB (substring + FTS5 on facts) |
| GET | `/api/knowledge/{name}/tasks` | KB ingestion task status |

#### Skills
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills` | List all skills (global + per-scene) |
| POST | `/api/skills` | Create/import skill |
| DELETE | `/api/skills/{name}` | Delete skill |
| GET | `/api/skills/{name}` | Read skill markdown |

#### Channels
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/channels` | List configured channels |
| POST | `/api/channels/connect` | Start channel (connects scene to platform) |
| POST | `/api/channels/disconnect` | Stop channel |
| GET | `/api/channels/{type}/status` | Channel connection status |

#### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/providers` | List configured LLM providers |
| GET | `/api/models` | List available models per provider |
| WebSocket | `/ws` | Real-time event stream (see WebSocket Event Schema)

## Storage Architecture

**Principle: DB for cross-object queries, filesystem for self-contained content.**

### SQLite (queryable state + memory)

```sql
agents: id, name, role, state, bound_scene, created_at
messages: id, scene_id, agent_id, user_id, channel_type, role, content, status, created_at
scenes: id, name, created_at
facts: id, agent_id, fact, search_text, tags, session_id, created_at
facts_fts: fact, search_text, tags (FTS5 virtual table)
cron_tasks: id, name, schedule, description, agent_id, next_run, enabled, created_at
```

- **agents**: Fast lookup: "which sub AI is free?"
- **messages**: Chat history (role: user/agent), paginated by scene/user. `channel_type` tracks which platform the message came from. `status` applies only to scene channel messages (`pending → processing → replied`) to serve as the per-scene FIFO message queue. Web UI chat messages have `status = NULL`.
- **scenes**: List scenes, query binding status
- **facts**: FTS5 full-text search for long-term conversation memory. `search_memory` tool queries this table.
- **cron_tasks**: Recurring/one-shot scheduled tasks created via `cron` tool or Schedule Window. `schedule` stores cron expression or `@every Nm`.

### Filesystem (agent-self-contained content)

```
agents/{id}/
  profile.yaml             # Identity, personality
  heartbeat.md             # Main AI only: responsibilities & focus areas  
  heartbeat.log            # Main AI only: heartbeat session records
  memory/
    memory.md              # Compiled memory (injected into system prompt)
    summaries/             # Per-session summary JSONs
    today.md / week.md / longterm.md / facts.md   # Daily compilations
  users/
    local/                 # Web UI user (local)
      sessions/{uuid}.jsonl
      memory.md
    {channel_user_id}/     # Channel users (WeChat ilink Feishu)
      sessions/{uuid}.jsonl
      memory.md

scenes/{id}/
  scene.yaml               # Context (markdown), roster, kbs, skills, channels
  users/
    {channel_user_id}/     # External users via scene channels
      sessions/{uuid}.jsonl
      memory.md

skills/
  public/{name}.md          # Global skills (all agents)
  scenes/{name}.md          # Scene-specific skills

workspace/                    # All agents share one workspace

knowledge/{name}/           # KB wiki — see KB Architecture section for full structure
```

### Memory Pipeline (Hanako-aligned, fully automatic)

Memory writing is **fully automatic**. No manual `remember` tool. The memoryTicker runs as a background asyncio task. Memory is **per-user**: each user (local or channel) has their own `memory.md` and facts.

**Model usage**: Memory compilation uses the `utility` and `utility_large` models, not the primary `chat` model — keeping memory operations cheap.

```
Session JSONL (raw conversation, auto-written every turn — pure file I/O, no LLM)
  │
  │  memoryTicker (every 6 turns + session end)  ← uses utility model
  ▼
Rolling Summary → memory/summaries/{session_id}.json
  │  Fingerprint-cached: skip LLM if inputs unchanged
  ▼
Daily job (midnight or on date change):
  compileToday  → memory/today.md    (3-5 coarse events)     ← utility_large
  compileWeek   → memory/week.md     (7-day sliding window)   ← utility_large
  compileLongterm → memory/longterm.md (fold week into profile) ← utility_large
  compileFacts  → memory/facts.md    (deduplicate 30-day facts) ← utility
  │
  │  assemble (pure file concat, no LLM)
  ▼
memory.md (4 sections: Key Facts + Today + Week + Longterm)
  → Injected into system prompt at session creation
  │
  │  deep-memory: diff summary vs snapshot → extract atomic facts  ← utility
  ▼
facts table (SQLite + FTS5)
  → searchable via recall tool
  → Agent can pin/unpin facts via pin/unpin tools
  → Agent can record/recall categorized experiences
```

## Data Flow: User Chat (Complete)

```
1. User sends message via Web UI
   POST /api/chat {"content": "帮我查一下产品手册里关于退款的流程"}

2. FastAPI → Main AI.run(message)
   Main AI session created (session.jsonl)

3. Main AI analyzes:
   - "Need to query KB 'product-manual'" → sub AI could do this
   - Finds idle sub AI: agent_a

4. Main AI assigns task:
   Main AI's tool call → spawn_subagent(agent_a, prompt="查询产品手册退款流程")
   → Sub AI agent_a.run() in isolated session
   → agent_a reads KB index → finds "refund" entity → reads page → returns summary

5. Main AI receives sub AI result
   Main AI formats final answer → returns to user

6. FastAPI streams result to user via WebSocket
   Session JSONL saved
```

## Data Flow: Scene Channel (Complete)

```
1. Customer sends WeChat message to scene "customer-service"

2. WeChat channel → on_message(user_id, content)
   → EventBus: scene_message {scene_id: "customer-service", user_id, content}

3. Scene handler:
   - Find bound agent for this scene: agent_c (working state)
   - agent_c.run(content) with scene context + scene KBs + scene skills

4. agent_c processes:
   - Uses scene KB "product-manual" to find answer
   - Uses scene skill "crm-lookup" to check customer history
   - Uses scene skill "refund-procedure" to compose reply

5. agent_c returns reply → channel.send(user_id, reply)

6. Session JSONL saved
   Message logged to DB
```

## What to Cut

| Remove | Reason |
|--------|--------|
| Rust daemon (src/) | Over-engineered for current scope. Python-only. |
| agent_runtime.py subprocess model | Agents are Python objects, not subprocesses. Includes `_mailbox_poll_loop` + `_control_poll_loop` background threads. |
| Mailbox JSONL (agents/mailbox/) | Replaced by in-process EventBus. |
| Control JSONL (control.jsonl) | Replaced by direct method calls. |
| SceneManager state machine | Simplified: scene is active when sub AI is bound. |
| AgentHandle | Replaced by direct agent method calls. |
| SceneRuntime | Replaced by scene + bound agent state in DB. |
| Telegram / Discord channels | Out of scope; keep WeChat, ilink, Feishu only. |
| Mailbox system (API, DB, Web UI) | No agent-to-agent messaging needed in v2. EventBus handles system events. |
| Hiring system (API, DB, Web UI, agent method) | Agent creation via simple CRUD in settings, not LLM-driven "recruitment." |
| Deliveries system (API, DB) | Replaced by workspace file tree; agents read/write files directly. |
| Login page + JWT auth middleware | Local tool; listen on localhost, no user authentication needed. |
| Collab graph (API endpoint) | Agents don't collaborate in v2. Visualization of agent-scene-KB-skill relationships can be rebuilt if needed. |
| Chat Groups (API, DB, Web UI) | v2 is Main AI + sub agent delegation, not multi-agent parallel chat. Scene page covers per-scene conversation. |
| git_store.py (Git memory versioning) | Replaced by filesystem backup snapshots (same pattern as `.llm-wiki/page-history/`). |
| All prior spec docs | Consolidated into this single architecture doc. |

## What to Keep & Simplify

| Keep | Simplify |
|------|----------|
| KB wiki system (knowledge/) | Full llm-wiki alignment |
| Skill .md files | Keep as-is |
| Scene config | Migrate to scene.yaml |
| Agent profile | Migrate to profile.yaml |
| Web UI (React) | Rebuild layout per new UI design |
| CLI (typer) | Keep; good for admin |
| FastAPI server | Consolidate all routes here |
| WebSocket streaming | Keep; essential for UX |
| ReAct agent loop | Simplify: delegate to a focused AgentLoop class |
| Tool system | Simplify: flat dict array, no plugin hooks for now |

## Migration Strategy

### Guiding Principle

Incremental migration: each Rust component is replaced by a Python equivalent and validated end-to-end before the Rust process is retired. No big-bang rewrite.

### Phase 1: Map the Gap

For every Rust handler in `src/api/`, identify whether a Python equivalent already exists in `web/routes/` or `web/main.py`. Some endpoints are already proxied through FastAPI; others read filesystem directly and must be migrated to DB-backed logic.

### Phase 2: Replace Infrastructure Components (one at a time)

| Rust Component | Python Replacement |
|---------------|-------------------|
| `src/db/pool.rs` (SQLite connection pool) | `sqlite3` with `asyncio` (single-writer, WAL mode) |
| `src/dispatch/engine.rs` (task dispatch queue) | `asyncio.Queue` + worker coroutine |
| `src/agent/manager.rs` (agent process spawner) | `AgentPool` class (in-process Agent objects, not subprocesses) |
| `src/scheduler.rs` (recurring task scheduler) | `asyncio` background task with `asyncio.sleep` loop |
| `src/api/ws.rs` (WebSocket broadcast) | FastAPI `WebSocket` endpoint + `asyncio` broadcast |
| `src/auth.rs` (JWT verification) | Removed — no user authentication in v2 (localhost-only local tool) |
| `src/agent/health_check_loop` | `AgentPool.health_check()` via asyncio periodic task |

### Phase 3: Remove Rust

Once all Rust responsibilities are migrated and verified, remove `src/` and `Cargo.toml`. FastAPI becomes the sole HTTP server. Agent processes are replaced with in-process Agent objects.

### Phase 4: Migrate Filesystem State to SQLite

Data currently in filesystem (agent profiles in `agents/config.toml`, scene metadata spread across multiple files) is consolidated into `scene.yaml` and `profile.yaml`. Existing filesystem data serves as the migration source — read once, write to DB, then files become the canonical copy for content (not state).

### Rollback Safety

Each phase can be reversed by restarting the old Rust daemon. DB schema is additive (new tables, no destructive column changes). Filesystem files are preserved during migration (read-only).

## Deployment Model

### Single-Process Architecture

CocoCat runs as a **single Python process** containing:
- FastAPI HTTP server (uvicorn)
- Agent pool (in-process Agent objects)
- EventBus (asyncio pub/sub)
- Scheduler (asyncio background task)
- Channel adapters (started on demand, stopped on scene unbind)

No external process management (no supervisor, no systemd dependency). Start with: `python -m cococat serve`

### Serving the React Frontend

In production, FastAPI serves the built React SPA from `web-ui/dist/`. In development, Vite dev server runs separately on `:5173` with proxy to FastAPI.

### Platform

- **Development**: `python -m cococat serve --dev` (auto-reload, debug logging)
- **Production**: single process behind nginx or direct uvicorn with multiple workers (each worker has its own AgentPool; agents are per-worker; scenes are shared via DB)

## Error Handling

### Agent Runtime Errors

| Scenario | Behavior |
|----------|----------|
| Agent.run() raises exception | Error logged, message returned to user as "处理出错了，请重试" |
| Agent crashes during scene channel processing | Message remains queued in DB, retried when agent restarts |
| LLM API call fails after all retries | Error surfaced to user with provider-specific hint |
| Tool execution fails | Tool error returned to LLM as tool result, LLM decides next step |

### Channel Errors

| Scenario | Behavior |
|----------|----------|
| Channel connection lost | Auto-reconnect with exponential backoff (max 5 min interval) |
| Channel send fails | Retry 3 times, then log error + surface to Web UI |
| Channel auth expires (WeChat token) | Refresh token, retry; if fails, channel status set to "auth_error" |

### System-Level

| Scenario | Behavior |
|----------|----------|
| DB connection lost | Retry with backoff, return 503 to clients during outage |
| All sub agents busy | Main AI returns "当前助手都在忙，请稍后重试" |
| Disk full (KB upload) | Upload rejected with clear error before processing |

## Security

### KB Permission Isolation

Sub AI bound to scene only has access to that scene's KB files. Implemented via tool-level path filtering: when agent calls `read_file`, the tool wrapper validates the path is within `knowledge/{scene_kb}/` or `skills/scenes/{scene_skill}` directories.

### Workspace Access

Bound sub AIs have **read-only** access to the shared `workspace/`. They can read files (e.g., Main AI shares a file for the sub AI to process) but cannot write or execute. Idle sub AIs and Main AI have full read/write access. This prevents scene-bound agents from polluting the shared workspace.

### Path Traversal Protection

All file operation tools (`read_file`, `write_file`, `edit_file`) validate paths against allowed directories. Reject `../` sequences, absolute paths outside workspace, symlink following beyond allowed roots.

### API Authentication

No user authentication. CocoCat is a local tool — access is controlled at the OS/network level (listen on localhost only by default).

### API Keys

Provider credentials stored in `auth.json` with `chmod 600`. Supports `${ENV_VAR}` references for production secrets. Web UI masks key display.

## Agent Pool Management

### Pool Rules

- Configurable max sub agent count (default: `MAX_SUB_AGENTS = 10`)
- Agents are created via settings UI, not auto-scaled
- Pool status queryable: `GET /api/agents` returns state for each agent

### Binding Enforcement

```
assign_agent_to_scene(scene_id):
  1. Query DB: any IDLE sub agent in scene's roster?
  2. If yes → bind, set state = WORKING, return agent_id
  3. If no → log warning, scene stays IDLE
```

### Free Agent Selection

When Main AI needs a sub agent for a task, query `agents WHERE role='sub' AND state='idle'`. Pick first available. If none, Main AI handles the task itself (no delegation).

## Testing Strategy

### Unit Tests
- Agent session creation, tool execution, permission scoping
- KB ingest pipeline stages (cache hit/miss, file block parsing, sanitization)
- Provider compat modules (each module tested with known input/output pairs)
- EventBus publish/subscribe delivery

### Integration Tests
- Full chat flow: user message → Main AI → sub agent delegation → result
- Scene channel: external message → channel → bound sub AI → reply
- KB upload → task → agent ingest → wiki page created
- Memory pipeline: session → summary → daily compile → facts extraction

### Test Infrastructure
- In-memory SQLite for DB tests
- Mock LLM provider (returns predefined responses for known prompts)
- Mock channel adapter (simulates external message arrival)
- Test fixtures: pre-built KB structures, agent configs, scene configs

## WebSocket Event Schema

### Event Types

All events have the form `{"type": "<string>", "data": {...}}`.

| Event | Direction | Description | data fields |
|-------|-----------|-------------|-------------|
| `text_delta` | server → client | Streaming text chunk | `content: str`, `agent_id: str` |
| `tool_start` | server → client | Tool execution begins | `tool_name: str`, `tool_call_id: str`, `agent_id: str` |
| `tool_end` | server → client | Tool execution completes | `tool_name: str`, `tool_call_id: str`, `success: bool`, `output: str` (truncated) |
| `task_assign` | server → client | Main AI dispatches to sub AI | `agent_id: str`, `task_description: str` |
| `task_complete` | server → client | Sub AI finishes task | `agent_id: str`, `result_summary: str` |
| `agent_state` | server → client | Agent status change | `agent_id: str`, `state: "idle"\|"working"`, `bound_scene: str\|null` |
| `scene_message` | server → client | Scene channel message received | `scene_id: str`, `channel: str`, `user_id: str`, `content: str` |
| `kb_ingest_progress` | server → client | KB file processing status | `kb_name: str`, `filename: str`, `agent_id: str`, `status: "processing"\|"done"\|"failed"` |
| `error` | server → client | Non-fatal operational error | `code: str`, `message: str`, `recoverable: bool` |

### Connection Lifecycle

1. Client connects to `ws://host/ws`
2. Server sends `{"type": "connected", "data": {"session_id": "..."}}`
3. Server pushes events as they occur
4. Client sends `{"type": "ping"}` every 30s; server responds `{"type": "pong"}`

### Layout System

Three-column base layout with collapsible panels:

- **Rail (44px)**: Always visible. Logo + name at top, scene icons in middle (hover to expand name), gear ⚙ settings at bottom.
- **Sidebar**: Collapsible/hideable. Conversation history on chat page. Hidden on scene page.
- **Main Area**: Content varies by page.
- **Right Panel**: Collapsible/hideable. 4 pages switched via ● dots at top.

### Chat Page (Main AI)

```
┌────┬──────────────┬──────────────────────┬──────────────────┐
│Rail│ Sidebar       │      Chat Area        │ ● ○ ○ ○          │
│    │ (对话历史)     │                       │  Workspace       │
│    │              │  主 AI 对话流            │  / KB / Skills   │
│    │  今天         │  · 流式 Markdown 输出   │  / Memory        │
│    │  · 退款       │  · 副 AI 任务内嵌展开    │                  │
│    │  · 订单       │  · 工具调用实时展示      │                  │
│    │  昨天         │                       │                  │
│    │  · 登录       │  ┌─────────────────┐   │                  │
│    │              │  │ 输入框 + 工具栏    │   │                  │
│    │              │  └─────────────────┘   │                  │
└────┴──────────────┴──────────────────────┴──────────────────┘
```

- **Sidebar**: `⏰` schedule button at top, then conversation history grouped by date (today / yesterday / earlier) below. Click `⏰` opens Schedule window modal. Click history item to navigate past chats. Sidebar is toggleable.
- **Right Panel**: 4 pages switched by top dots:
  - ● Workspace file tree (browse, click to preview)
  - ● KB file tree (browse wiki entities/concepts, click to preview)
  - ● Skills list (view skill markdown, click to preview)
  - ● Memory (today/week memories, pinned facts, system status)
  - Click any file → preview slides out from panel left edge with close button.
- **Chat Area**: Messages rendered as content blocks, not plain text. Block rendering below.

### Chat Content Block System (Hanako-inspired)

Each assistant message is composed of ordered content blocks. Two categories:

**Species A — Text Decorators** (upserted during streaming, replace previous version):
| Block | Rendering |
|-------|-----------|
| `thinking` | Collapsible `<details>`. Active: `"Thinking..."` + animated dots cycling `. → .. → ...`. Done: `"思考完成"` with green ✓. Body: muted italic text with left border accent. |
| `tool_group` | Tool calls grouped. Running: animated dots + tool name + detail. Done: green ✓ or red ✗. Single tool inline. Multiple tools in bordered group with count summary. Auto-collapse when all complete. |
| `text` | Rendered Markdown. 200ms batched refresh (not character-by-character typewriter). Code blocks with syntax highlighting + copy button. |

**Species B — Rich Content** (appended, never replaced):
| Block | Rendering |
|-------|-----------|
| `subagent` | Card: avatar + name + status badge + task title. Running: pulsing avatar + live text line + `✕` abort on hover. Done: green "已完成" + final summary. Expandable to view sub-agent session transcript. |
| `file` | Card: icon + filename + type. Image preview (max 450px) clickable to full viewer. Expired files: dashed border. |
| `screenshot` | Inline image from base64, max 600px wide, clickable. |
| `cron_confirm` | Action card with approve/reject buttons. Shows result after action. |
| `settings_confirm` | Toggle/select/text confirmation card with confirm/cancel. |

**Block order in message**: thinking → tool_group → text → species B blocks.

**Streaming**: Events arrive via WebSocket. `StreamBufferManager` accumulates deltas with 200ms batched flush, updates the in-progress message in-place. Events: `text_delta`, `thinking_start/delta/end`, `tool_start/end`, `turn_end`.

### Scene Page (Per-Scene Channel Monitor)

```
┌────┬──────────────────────────────────────┬──────────────┐
│Rail│  ● WeChat  ○ Feishu  ○ ilink        │   ┌────┐     │
│    │                       [用户: 张三 ▼] │   │头像│     │
│    ├──────────────────────────────────────┤  agent_c    │
│    │  张三: 我要退款                       │  最近操作     │
│    │  agent_c: 正在查询产品手册...          │  · 查退款流程  │
│    │  ┌─ read_file 退款流程.md ✓ ──┐     │  · 回复客户   │
│    │  └────────────────────────────┘     │  状态 ● 工作  │
│    │  agent_c: 退款流程分三步...            │              │
│    ├──────────────────────────────────────┴──────────────┤
│    │ 📚 KB: 产品手册 FAQ   │ 🔧 Skills: 话术 退款 crm    │
│    │ 点击增删 (下拉选择已有 KB / Skills)                  │
└────┴─────────────────────────────────────────────────────┘
```

- **No sidebar, no right panel**.
- **Top bar**: Channel dots (switch between scene's channels) + user selector dropdown + agent card.
- **Agent card**: Large avatar, name, recent actions log, current status indicator (idle/work). Uses `position: sticky; top: 0` so it stays visible while scrolling chat content. Equal height to the chat area is achieved via CSS flexbox (`align-self: stretch`), not JS calculation.
- **Chat area**: Same content block system as Chat Page (thinking, tool_group, text blocks). Channel messages + sub AI replies + tool calls inline.
- **Bottom bar**: Mounted KBs and Skills displayed as tags. Click to open dropdown select for add/remove (reuses the Select component from SceneDetail).

### Settings Window (Modal)

Modal overlay with left navigation + right content. Not a separate page.

**Navigation**: 智能体 | 供应商 | 场景 | 技能 | 知识库 | 渠道 | 外观 | 通用

| Tab | Content |
|-----|---------|
| **Agent** | Agent selector (main + subs). Per-agent: name, model dropdown, identity textarea. Create new. |
| **供应商** | Provider list with masked API keys + show/hide. Add provider. Global model assignments (chat, utility, utility_large, vision). |
| **场景** | Scene cards: KBs, Skills, channels, context. Click to edit. Create new. |
| **技能** | Global skills list. Per-scene skill groups. Create / import skill file. Enable/disable. |
| **知识库** | KB circle icon selector (scrollable, + to create). Upload drop zone. File status (processing / complete). Wiki index preview below. |
| **渠道** | Main AI channels. Per-scene channel configs, connect/disconnect. Add channel. |
| **外观** | Theme: light / dark / follow system. |
| **通用** | Language locale. Workspace path. |

#### Knowledge Base Tab Detail

```
┌────────────┬──────────────────────────────────────────┐
│            │  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐               │
│            │  │产│ │F │ │代│ │内│ │＋│ ← scrollable     │
│            │  │品│ │A │ │码│ │部│ │  │   horizontal     │
│            │  │手│ │Q │ │库│ │文│ │  │               │
│            │  │册│ │  │ │  │ │档│ │  │               │
│            │  └──┘ └──┘ └──┘ └──┘ └──┘               │
│            │  当前: 产品手册                            │
│            │  ─────────────────────────────────────    │
│            │  ┌─ 拖拽文件到此处上传 ────────────┐      │
│            │  │       📂  点击或拖拽上传          │      │
│            │  └─────────────────────────────────┘      │
│            │  ─────────────────────────────────────    │
│            │  已上传文件:                                │
│            │  📄 退款政策.md  [agent_a 正在处理...]     │
│            │  📄 订单管理.md  ✓ 已完成                  │
│            │  ─────────────────────────────────────    │
│            │  索引: 📁 entities 📁 concepts 📁 sources    │
│            │        📁 queries 📁 synthesis 📁 comparisons │
│            │        📄 index.md 📄 purpose.md              │
└────────────┴──────────────────────────────────────────┘
```

- **KB selector**: Circle icon row. Hover shows name. Horizontal scroll if many. + to create new KB.
- **Upload zone**: Large drop area. During injection, file shows `[agent 正在处理 filename]` — no view/delete options while processing. ✓ when complete.
- **Wiki index**: entities, concepts, sources, queries, synthesis, comparisons, index.md, purpose.md listed at bottom (full KB structure from KB Architecture).

### Schedule Window (Modal)

Opened from `⏰` button in chat page sidebar.

```
┌──────────────────────────────────┐
│  ⏰ 定时任务                  [✕] │
├──────────────────────────────────┤
│                                  │
│  Cron 任务                        │
│  ┌──────────────────────────────┐│
│  │ ⏰ 每天 9:00  检查 KB 摄入    ││
│  │   下次: 明天 09:00    [编辑]  ││
│  ├──────────────────────────────┤│
│  │ ⏰ 每 2 小时  客服质量检查    ││
│  │   下次: 11:30       [编辑]  ││
│  └──────────────────────────────┘│
│  + 新建定时任务                   │
│                                  │
│  [编辑 heartbeat.md]             │
└──────────────────────────────────┘
```

- **Cron tasks**: Created via agent's `cron` tool or manually here. Shows schedule, next run time, edit button.
- **heartbeat.md button**: Opens Main AI's heartbeat instructions file for editing. Heartbeat itself runs silently in background — no status display needed.
