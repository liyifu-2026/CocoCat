# Chat Page: Direct Messages per Agent

## Problem

Chat page only has a single "General" group. Users can't send direct messages to individual agents. They have to use `@mention` in General and hope the right agent responds.

## Solution

Each agent gets an auto-created DM group. Chat sidebar splits into Channels + Direct Messages.

## DM Group

- Group ID: `dm_{agent_id}` (e.g. `dm_leader`, `dm_employee_a`)
- Members: admin (owner) + agent (member)
- Created automatically by `init_default_group()` on Rust core startup
- DM groups are hidden from the regular groups list (they're not user-manageable)

## Chat Sidebar

```
Chat
├── Channels
│   └── # General
│
├── Direct Messages
│   ├── 🟢 组长 (running)
│   ├── 🔴 员工A (error)
│   ├── ⚪ 员工B (stopped)
│   └── 🟢 员工C (running)
│
└── [+] New Group
```

Status dots: `running` → green, `error`/`busy` → red, `stopped` → no dot (gray circle).

## Message Flow

When sending in a DM group:
```
POST /api/chat/groups/dm_leader/messages
  → send_message() detects group_id starts with "dm_"
  → Extracts agent_id from dm_{agent_id}
  → Creates task for that agent (without needing @mention)
  → Agent replies → written to messages table
  → Frontend polls GET /messages → sees reply
```

## Backend Changes

### Rust: `init_default_group`

After creating the "general" group, iterate agents table and for each agent:

```sql
INSERT OR IGNORE INTO chat_groups (id, name, announcement, is_default)
VALUES ('dm_leader', '组长', '', 0);
INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role)
VALUES ('dm_leader', 'admin', 'Admin', 'owner');
INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role)
VALUES ('dm_leader', 'leader', '组长', 'member');
```

### Rust: `send_message` in API handler

When creating tasks for a message, check if `group_id` starts with `dm_`:
- If yes, extract agent_id from after `dm_`
- Dispatch to that agent directly (no mention parsing needed)

### Frontend: Chat page

- Split sidebar into "Channels" and "Direct Messages" sections
- Show regular groups in Channels (exclude `dm_*`)
- Show DM groups in Direct Messages section (prefixed with status dot)
- DM list fetches agent status from agents API for the dot color
