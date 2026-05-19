CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'stopped'
        CHECK (status IN ('stopped','running','error')),
    system_prompt TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_heartbeat_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_uuid TEXT UNIQUE NOT NULL,
    agent_id TEXT REFERENCES agents(id),
    user_id TEXT,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT 'default',
    chat_group TEXT NOT NULL DEFAULT 'general',
    metadata TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','replied','failed')),
    channel_type TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_scene_group
    ON messages(scene_id, chat_group, created_at);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uuid TEXT UNIQUE NOT NULL,
    target_agent TEXT NOT NULL REFERENCES agents(id),
    source TEXT NOT NULL,
    method TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    result TEXT,
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    task_type TEXT NOT NULL DEFAULT 'one_time',
    recurrence TEXT,
    parent_task_id INTEGER REFERENCES tasks(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_target
    ON tasks(status, target_agent)
    WHERE status IN ('pending','running');

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
