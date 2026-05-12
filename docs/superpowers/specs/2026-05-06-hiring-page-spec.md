# Hiring Page: Plan + Candidate Cards

## Problem

Current Hiring page is just a pending approval list. No way to create hiring plans or generate candidates.

## Solution

Add a hiring plan form at the top. Leader generates candidates via a `dream_candidates` skill. Candidates display as cards with approve/reject.

## Architecture

```
User fills form → POST /api/hiring/plan
  → FastAPI creates hire_plan record
  → Creates Task for leader agent
  → Leader calls dream_candidates skill (LLM)
  → Generates N candidates → writes to agents/hire_requests/pending/
  → Frontend polls → sees candidates → shows cards

Approve → POST /api/hiring/pending/{id}/approve
  → Creates agent in config.toml + filesystem
  → Frontend shows nickname dialog

Reject → POST /api/hiring/pending/{id}/reject
  → Moves to rejected dir
```

## Backend

### New API: POST /api/hiring/plan

Request:
```json
{
  "position": "客服专员",
  "skills": "耐心、沟通能力、问题解决",
  "responsibilities": "处理客户投诉",
  "traits": "细心、负责",
  "count": 5
}
```

Response: `{ "status": "plan_submitted", "task_uuid": "..." }`

Handler: Creates a task for leader agent with method `dream_candidates`. The task params include the hiring plan details.

### New Skill: dream_candidates

File: `py-agent/skills/dream_candidates.py`

Called by leader agent via tool_registry. Takes hiring plan, calls LLM, writes candidate JSON files to `agents/hire_requests/pending/{candidate_name}.json`.

Each candidate file:
```json
{
  "id": "candidate_xiaowang",
  "name": "小王",
  "scene": "default",
  "profile": {
    "role": "客服专员",
    "objective": "处理客户问题",
    "traits": ["细心", "耐心"],
    "rules": ["礼貌用语"],
    "background": "3年客服经验"
  }
}
```

### Existing Endpoints (unchanged)

- `GET /api/hiring/pending` — list candidates
- `POST /api/hiring/pending/{id}/approve` — accept + create agent
- `POST /api/hiring/pending/{id}/reject` — reject

### Agent Runtime Changes

Register `dream_candidates` as a tool in `tools.py` / `tool_registry.py` so leader agent can call it.

## Frontend

### Hiring.tsx — New Layout

```
┌──────────────────────────────────────────────────┐
│  Hiring                                 Pending N │
│                                                  │
│  ┌─ Post a Hiring Plan ────────────────────────┐  │
│  │  Position     [________________________]    │  │
│  │  Skills       [________________________]    │  │
│  │  Description  [________________________]    │  │
│  │  Traits       [________________________]    │  │
│  │  Candidates   [5]                           │  │
│  │  [Submit to Leader]                         │  │
│  └─────────────────────────────────────────────┘  │
│                                                  │
│  ── Pending Approval ──                           │
│                                                  │
│  ┌──────────────┐ ┌──────────────┐               │
│  │ CandidateCard │ │ CandidateCard │               │
│  │ name, role    │ │ name, role    │               │
│  │ traits, bg    │ │ traits, bg    │               │
│  │ [Accept][Rej] │ │ [Accept][Rej] │               │
│  └──────────────┘ └──────────────┘               │
└──────────────────────────────────────────────────┘
```

### Nickname Dialog on Accept

After clicking Accept, before the hire is approved, show a dialog:
```
┌─ Set Nickname ─────────────────────┐
│                                    │
│  Candidate: 小王                    │
│  Nickname:  [__________________]   │
│                                    │
│  (If left empty, use original name)│
│                                    │
│  [Skip]  [Confirm & Create]        │
└────────────────────────────────────┘
```

If nickname is provided, set it via `PATCH /api/agents/{id}/display` after agent creation.
