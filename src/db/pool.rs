use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;

pub type DbPool = Pool<SqliteConnectionManager>;

pub fn create_pool() -> Result<DbPool, Box<dyn std::error::Error>> {
    let db_path = std::env::var("COCOCAT_DB").unwrap_or_else(|_| "cococat.db".to_string());
    let manager = SqliteConnectionManager::file(&db_path);
    let pool_size = std::thread::available_parallelism()
        .map(|n| (n.get() * 2).max(4).min(32))
        .unwrap_or(8);
    let pool = Pool::builder()
        .max_size(pool_size as u32)
        .build(manager)?;
    tracing::info!("SQLite pool size: {}", pool_size);

    let conn = pool.get()?;
    conn.execute_batch(
        "PRAGMA journal_mode=WAL;
         PRAGMA synchronous=NORMAL;
         PRAGMA foreign_keys=ON;
         PRAGMA busy_timeout=5000;
         PRAGMA cache_size=-64000;"
    )?;

    Ok(pool)
}

pub fn run_migrations(pool: &DbPool) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS agents (
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
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            started_at TEXT,
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status_target
            ON tasks(status, target_agent)
            WHERE status IN ('pending','running');

        CREATE TABLE IF NOT EXISTS mailbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_uuid TEXT UNIQUE NOT NULL,
            from_agent TEXT NOT NULL REFERENCES agents(id),
            to_agent TEXT NOT NULL REFERENCES agents(id),
            subject TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS hire_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_uuid TEXT UNIQUE NOT NULL,
            requester_agent TEXT NOT NULL REFERENCES agents(id),
            new_agent_id TEXT NOT NULL,
            new_agent_name TEXT NOT NULL,
            new_agent_role TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','approved','rejected')),
            reviewer TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            roster TEXT NOT NULL DEFAULT '[]',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            scope TEXT NOT NULL CHECK (scope IN ('public','private','scene')),
            content TEXT NOT NULL,
            scene_id TEXT REFERENCES scenes(id),
            agent_id TEXT REFERENCES agents(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            from_agent TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            files TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            announcement TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_group_members (
            group_id TEXT NOT NULL REFERENCES chat_groups(id),
            agent_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            PRIMARY KEY (group_id, agent_id)
        );"
    )?;

    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS skill_warehouse (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            version TEXT NOT NULL DEFAULT '1.0',
            source TEXT NOT NULL DEFAULT 'builtin',
            source_url TEXT,
            author TEXT NOT NULL DEFAULT 'CocoCat',
            tags TEXT NOT NULL DEFAULT '[]',
            deps TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS agent_skills (
            agent_id TEXT NOT NULL REFERENCES agents(id),
            skill_id TEXT NOT NULL REFERENCES skill_warehouse(id),
            enabled INTEGER NOT NULL DEFAULT 1,
            assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (agent_id, skill_id)
        );"
    )?;

    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS hire_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_uuid TEXT NOT NULL UNIQUE,
            position TEXT NOT NULL,
            skills TEXT DEFAULT '',
            responsibilities TEXT DEFAULT '',
            traits TEXT DEFAULT '',
            requested_count INTEGER DEFAULT 5,
            status TEXT DEFAULT 'generating',
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS hire_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_uuid TEXT NOT NULL UNIQUE,
            plan_uuid TEXT NOT NULL,
            name TEXT NOT NULL,
            profile TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            decided_at TEXT,
            reviewer TEXT,
            FOREIGN KEY (plan_uuid) REFERENCES hire_plans(plan_uuid)
        );"
    )?;

    Ok(())
}

#[cfg(test)]
pub fn create_test_pool() -> DbPool {
    let manager = SqliteConnectionManager::memory();
    let pool = Pool::builder()
        .max_size(2)
        .build(manager)
        .expect("failed to create test pool");
    run_migrations(&pool).expect("test migration failed");
    pool
}
