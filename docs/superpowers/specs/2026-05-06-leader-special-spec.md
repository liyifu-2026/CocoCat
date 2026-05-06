# Leader Special Display

## Problem

Agents page treats all agents identically. Leader (组长) is a fixed role like a game's starting character — cannot be removed, should be visually distinct.

## Solution

Split Agents page into two sections: Leader hero card at top, team member grid below. Protect leader from deletion at both frontend and backend.

## Frontend: Agents Page

### Leader Card
- Full-width hero card at top of page
- Large AgentAvatar (lg size)
- Crown icon from lucide-react next to name
- Info: role, scene
- Action buttons: Edit Display, View Details (links to AgentDetail)
- No Disable or Delete buttons
- Status badge in top-right
- Visual distinction: `border-l-4 border-primary`, `bg-muted/30` background

### Team Members
- Section header: "Team Members (N)" with Users icon
- CSS grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3`
- Each member as Card component with AgentAvatar, name, status badge, scene, nickname edit
- No crown icon, compact layout

## Frontend: AgentDetail Page

- If `agent_id === "leader"`: hide "Delete Agent" button, hide "Disable" button
- Show leader badge `<Badge variant="outline">Leader</Badge>` in header

## Backend: Rust

- `DELETE /api/agents/leader` returns 403 Forbidden
- Existing `delete_agent` handler checks `if agent_id == "leader"`

## Data Flow

Pure frontend restructuring + one backend guard. No new tables or APIs.
