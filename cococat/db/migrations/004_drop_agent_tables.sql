DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS dag_runs;
DROP TABLE IF EXISTS tasks;

CREATE TABLE scenes_new (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    context TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    purpose TEXT DEFAULT '',
    kbs TEXT DEFAULT '[]',
    skills TEXT DEFAULT '[]',
    tools TEXT DEFAULT '[]',
    channels TEXT DEFAULT '{}',
    llm_config TEXT DEFAULT '{}',
    visibility TEXT DEFAULT 'private',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    archived_at TEXT
);
INSERT INTO scenes_new SELECT
    id, name, description, context, status, purpose,
    kbs, skills, tools, channels, llm_config, visibility,
    created_at, updated_at, archived_at
FROM scenes;
DROP TABLE scenes;
ALTER TABLE scenes_new RENAME TO scenes;
