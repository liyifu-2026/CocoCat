# Delivery System: Agent-to-Admin Deliverable Inbox

## Problem

Chat is real-time conversation. When agents complete work, the results get buried in chat history. No way to properly manage delivered files.

## Solution

Mailbox becomes a one-way deliverable inbox. Agents can send completed work (files + description) to admin via a `send_delivery` tool. Admin views, downloads, archives.

## Data Flow

```
Chat: "Write a report and send it to me"
  → Leader gets Task → processes → generates files
  → Calls send_delivery(subject, body, files)
  → Tool copies files to data/deliveries/{uuid}/
  → Writes record to SQLite deliveries table
  → Admin opens Mailbox → sees new delivery → downloads
```

## Database

New SQLite table:
```sql
CREATE TABLE IF NOT EXISTS deliveries (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    from_agent TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    files TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## Backend

### Python: send_delivery tool
Registered in leader's tool registry. Called by LLM. Copies files to `data/deliveries/{uuid}/`, writes DB record.

### Rust: new API endpoints
- `GET /api/deliveries` — list all, ordered by created_at DESC
- `GET /api/deliveries/{id}` — single delivery details
- `POST /api/deliveries/{id}/archive` — set status=archived
- `POST /api/deliveries/{id}/read` — set status=read
- `GET /api/deliveries/{id}/files/{filename}` — serve file

### FastAPI: proxy to Rust
Same pattern as chat_groups + agents proxy.

## Frontend: Mailbox page rewrite

Split into two-panel layout:
- Left: delivery list (table: icon, subject, from, time, status badge)
- Right: detail panel (subject, from, body, file list with download buttons)

No input box. No reply. Admin only reads and archives.

Files show with type icons:
- pdf → FileText icon
- png/jpg → Image icon  
- csv/xlsx → Table icon
- other → File icon
