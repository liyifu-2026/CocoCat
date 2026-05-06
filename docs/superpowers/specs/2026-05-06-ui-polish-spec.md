# UI Polish: Nickname System, Real Status, SceneRail Animation

## Problem

Multiple UI features are incomplete or use fake data:
1. Agent names displayed everywhere are the raw `name` field — no nickname override
2. Agent online/offline badges read `enabled` from config.toml (always true) instead of real runtime status
3. AgentAvatar status dots (green/red) are never wired in — always invisible
4. SceneRail exists but has no hover-to-expand or label behavior

## Part 1: Nickname System

### Rule

- Each agent can set a nickname exactly once, locked after first set
- Agents list page has an inline "set nickname" button (pencil icon) on each row
- If nickname is already set, the button hides and the nickname displays
- Everywhere an agent name is shown: use `display.nickname || agent.name`
  - Dashboard agent cards
  - Agents list
  - Chat message bubbles
  - AgentDetail header
  - Hiring cards (future)
- Hiring flow: after accepting a new hire, prompt to set nickname (to be implemented in hiring phase)

### Backend

- `PATCH /api/agents/{id}/display` — if `nickname` already exists and is non-empty, return 409 for the nickname field
- Allow updating `avatar`, `color`, `gender` freely regardless

### Frontend

- Agents list page: add inline `<AgentNicknameDialog>` per row
- `chatApi.getMessages` response: map `from` through `agentNames` map which uses `display.nickname || agent.name`
- Dashboard: same mapping

## Part 2: Real Status Detection

### Backend Change

Migrate `web/routes/agents.py` from reading `config.toml` to proxying through Rust HTTP API (same pattern as chat_groups migration).

```
Before: FastAPI reads config.toml → { id, name, enabled, scene }
After:  FastAPI proxies GET/PATCH/DELETE to Rust /api/agents/* → real SQLite data
```

Rust core already has:
- `GET /api/agents/list` (need to add this endpoint)
- `GET /api/agents/{id}` (need to add this endpoint)
- `PATCH /api/agents/{id}` (need to add this endpoint)
- `DELETE /api/agents/{id}` → stop + remove

New Rust endpoints needed:
- `GET /api/agents` — query agents from SQLite
- `GET /api/agents/{id}` — single agent with status
- `PATCH /api/agents/{id}` — update agent fields
- `DELETE /api/agents/{id}` — stop + remove

### Frontend Change

- Agent list and detail: pass `agent.status` to `<AgentAvatar status={status === "running" ? "idle" : status === "busy" ? "busy" : undefined} />`
- Dashboard agent cards: use badge derived from status, not `enabled`

### Status Mapping

| DB status | Badge text | Dot |
|-----------|-----------|-----|
| running | Online | green |
| busy | Busy | red |
| stopped | Offline | gray (no dot) |
| error | Error | red |

## Part 3: SceneRail Animation

### Behavior

- SceneRail starts at 11rem wide (`w-11`)
- On mouse hover: expands to ~8rem (`w-32`) with a smooth transition
- Expanded state shows scene labels next to avatars
- On mouse leave: collapses back to `w-11`
- Tooltip when collapsed can be removed (replaced by label on hover)

### Implementation

- Use CSS `transition-all duration-200` on width
- Add `onMouseEnter`/`onMouseLeave` handlers for a `hovered` state
- When hovered, show text labels (scene.id) next to each avatar, collapse button stays visible
- Use `overflow-hidden` to prevent content bleed during animation
