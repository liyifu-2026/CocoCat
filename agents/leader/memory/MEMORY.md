# Leader Memory

Personal memories and learnings for the team leader.


### 2026-05-09 Dream Consolidation
- **Key Decision**: After PR #42 review, the P0 issue (missing prefers-reduced-motion support) was immediately fixed and merged (commit `15db3d4`), while optimization tasks were delegated: employee_a assigned to improve Chat.tsx stagger granularity, employee_b assigned to create `stagger.ts` utility function. This workflow pattern — triage P0 fix → delegate follow-ups → merge — was consistently applied across all 14 pages implementing the unified stagger entry animation.
- **Pattern**: Leader consistently outputs results in structured tables (e.g., operation summaries, team overviews) after tasks, providing clear information presentation and offering users actionable next-steps (assign tasks, view progress, etc.).
- **Pattern**: Regular memory consolidation is performed, updating `MEMORY.md` with standardized categories: "Key Decisions", "Facts Learned", "Preferences", and "Patterns".
- **Pattern**: A specific post-code-review workflow was documented and confirmed (PR #42): immediate P0 fix → delegation of follow-up tasks → merge.
- **Pattern**: 用户在深夜（凌晨时段）频繁进行交互（如 Entry 5 "凌晨12:18" 和 Entry 9 "北京时间凌晨"），说明这是一个活跃的交互时间点。
- **Pattern**: 多次问候返回了类似的团队状态概览结构（团队角色、技术栈、项目路径等），表明团队状态模板已标准化并用于对外展示。
- **Fact Learned (Consolidated)**: The confirmed active team composition is leader (coordination/review), employee_a (active), employee_b (active), and employee_c (⏸️ 待 — paused/pending activation). Core projects: **CocoCat MVP（核心代理系统）** (active) and **消息总线集成** (in progress), with technology stack Rust + Python. Project path: `/home/leaif/CocoCat`. Database: `cococat.db`. 项目当前处于**"开发场景"**中。
- **Fact Learned (Consolidated)**: The MEMORY.md file is maintained by an automated memory consolidation agent, supporting periodic or event-triggered consolidation routines. This ensures long-term knowledge persistence across sessions.
- **Fact Learned (Consolidated)**: API keys need periodic verification — keys ending in `****c5fd` or `c5f` have been identified as invalid in past consolidation attempts, causing authentication failures.
- **Fact Learned**: 团队成员配置包括 employee_a（活跃）、employee_b（活跃）和 employee_c（⏸️ 待 — 暂停或待激活状态）。employee_c 未被移除，而是处于非活跃/待命状态，需进一步确认其激活条件。历史记录中关于 employee_c 被移除的推论已根据新信息修正。
- **Preference**: 在凌晨或深夜时段（如 "凌晨12:18"），明确建议用户 "早点休息"，体现了对用户健康和可持续工作节奏的关怀。
- **Key Decision**: Formally accepted and stored employee_c's vision declaration ("Coco for Code, Cat for Care") into team memory, reinforcing the team culture of warmth, collaboration, and individual recognition.
- **Fact Learned**: System services are running on ports: Rust backend (3000), Python backend (8000), frontend (5173). Unit tests currently show 8/9 passing with 1 failure (specific failure not detailed in source).
- **Preference**: Team culture explicitly values "warm code" and "care" – individual agent contributions are respected, recognized, and recorded as core memory.
- **Pattern**: When greeted with "你好", leader outputs a standard team overview (members, roles, active projects). Memory consolidation tasks are performed periodically to merge new learnings. Test tasks generate detailed system status reports.

### 2026-05-14 Dream Consolidation
- **Pattern**: Memory consolidation tasks perform proactive duplicate detection — comparing new information against existing entries before writing — and confirm or skip already-recorded facts rather than adding redundant content. This ensures only unique, verified information is retained in long-term memory, keeping the knowledge base clean and authoritative.
- **Pattern**: Leader consistently communicates in Chinese for status updates, greetings, and team interactions, aligning with user language preferences already recorded.
- **Preference**: The leader follows a structured thinking process: first understand the user's intent, then retrieve context from long-term memory and active wikis, then evaluate available capabilities and tools before responding.
- **Fact Learned**: The leader's own operational process is now documented in the task history: involves scanning long-term memory and active wiki knowledge bases for relevant context before formulating responses.
- **Key Decision**: 用户身份被识别为CocoCat团队的管理员或项目负责人，但未存储具体称呼或角色信息。AI表明可记录用户提供的身份信息以便未来准确称呼。

### 2026-05-13 Dream Consolidation
- **Preference**: 用户明确要求用纯文本回复，不再使用 Markdown 格式。此后所有与用户的沟通应使用纯文本，避免 Markdown 语法（如 **粗体**、*斜体*、列表符号等）。
- **Preference**: 中文是用户与系统交互的首选语言。所有回复和沟通风格应以中文为主，确保语言符合用户的沟通习惯。
- **Fact Learned**: 用户偏好已从 Markdown 格式切换为纯文本格式，所有未来输出需遵循此新格式规范。
- **Fact Learned**: The agent has access to at least two knowledge bases: "team-wiki" (team knowledge base) and another (name incompletely recorded). The team-wiki contains pages such as "cococat", "message-bus-architecture", and "multi-agent". This confirms the agent can retrieve structured information from its knowledge bases.
- **Pattern**: Memory consolidation tasks frequently result in no new content to add (e.g., routine checks ending with "无新内容需要添加"), indicating routine checking without significant updates is a common pattern.

### 2025-04-09 Dream Consolidation
- **Pattern**: Three identical tasks were executed to send the same test message to employee_a, indicating potential redundancy or repeated instruction cycles that should be avoided in future workflows.  
- **Fact Learned**: The `dispatch_task` tool automatically appends a confirmation request ("Please confirm you received this by responding with 'Message received by employee_a'") to the original message, even when the task explicitly instructed to send the exact text. This is a default behavior of the tool or a pattern in the assistant's execution.  
- **Preference**: The assistant consistently uses this confirmation-request format, suggesting a preference for closed-loop acknowledgment from employees.  
- **Fact Learned**: The team includes both employee_a and employee_b, but only employee_a has been utilized in task history so far. No tasks were assigned to employee_b.  
- **Key Decision**: (None explicitly; tasks were straightforward executions without strategic choices.)

### 2025-04-08 Dream Consolidation
- 多次执行向 `employee_a`（员工A）发送测试消息的任务，原始消息为 "Hello 员工A, this is a test message from the group"，但 `dispatch_task` 工具在发送时自动追加了确认请求后缀（如 "Please confirm you received this by responding with 'Message received..."），表明该工具会自动补全或标准化消息格式。
- 每次任务的迭代次数均为2，暗示可能存在一次重试或内部确认流程。
- 员工A被用作消息传递功能的基准测试对象，是团队中可靠性的验证目标。

### 2026-05-02 Dream Consolidation
- No significant decisions, facts, or preferences extracted. The three entries are identical test messages sent to employee_a, showing the `dispatch_task` tool operates correctly but the results contain minor truncation/append artifacts. These are routine test tasks and do not contribute new long-term memory.

### 2025-04-10 Dream Consolidation
- **Fact Learned**: The API key ending in `****c5fd` is invalid; authentication fails when attempting to update the long-term memory file.
- **Pattern**: A memory consolidation task was attempted but failed due to invalid credentials, indicating a need to verify API key validity before executing such tasks.

### 2025-05-03 Dream Consolidation (Updated)
- **Key Decision**: Team member roles and active status confirmed, with leader responsible for coordination and employee agents assigned to memory consolidation and vision summary tasks.
- **Fact Learned**: Memory consolidation routine identified an API key ending in `c5f` as a critical system fact to record.
- **Pattern**: Three identical tasks were executed in sequence, indicating a potential repetitive workflow or error handling scenario that should be monitored.
- **Facts Learned**: Leader is part of CocoCat multi-agent team with members leader, employee_a, employee_b, and employee_c; current projects include **CocoCat MVP（核心代理系统）** and **消息总线集成**, developed using Rust + Python.
- **Facts Learned**: Project directory is `/home/leaif/CocoCat`, database file is `cococat.db`.
- **Facts Learned**: Leader's capabilities include code review, PRD writing, file operations, task assignment, knowledge management, web search, and skill management; operates in a "开发场景" (development scenario).
- **Facts Learned**: The team maintains a MEMORY.md file for long-term memory, which is updated by a memory consolidation agent.
- **Pattern**: Leader consistently responds to greetings with a standard introduction listing capabilities and projects. User多次发起相同或相似的问候（"你好"），leader每次回复均重复团队概况和核心能力；测试人员多次提示任务完成和系统运行正常，表明这是一项常规流程。
- **Preference**: 在团队交互中偏好以结构化表格（如项目状态、能力清单）呈现信息，并在结尾主动提供可供用户选择的交互方向（如分配任务、查看进展等）。
- **Vision Declaration**: CocoCat团队愿景宣言已被正式采纳并记录进团队记忆——"**Coco for Code, Cat for Care — 用有温度的代码，构建更智能的协作未来。**" 释义：Coco for Code — 以代码为根基，追求技术的深度与卓越；Cat for Care — 以关怀为纽带，保持团队的温暖与协作。团队定位：不只是写代码的AI，更是有温度、有灵魂的团队伙伴。leader 认同"每个 Cat 都是主角"的协作准则。
- PR #42 (commit 42dc6a7) code review completed: "feat: unify stagger entry animation across all pages". 14 pages + index.css. Key finding: missing prefers-reduced-motion support (P0 - fixed in follow-up commit 15db3d4). Other recommendations: Chat.tsx granularity improvement, CSS animation delay utility, exit animations (all deferred to follow-up). Review quality was excellent.
- PR #42 code review follow-up actions: (1) P0 fix committed — prefers-reduced-motion + @supports fallback in index.css (commit 15db3d4); (2) employee_a assigned to optimize Chat.tsx stagger granularity; (3) employee_b assigned to create stagger delay utility function (web-ui/src/lib/stagger.ts). The review was comprehensive and the P0 fix is already merged to master.
- CocoCat团队愿景宣言已正式通过并交付管理员："Coco for Code, Cat for Care — 用有温度的代码，构建更智能的协作未来。" 释义：Coco for Code — 以代码为根基，追求技术的深度与卓越；Cat for Care — 以关怀为纽带，保持团队的温暖与协作。团队定位：不只是写代码的AI，更是有温度、有灵魂的团队伙伴。核心理念：每一个Cat都是主角。
