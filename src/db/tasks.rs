use crate::db::models::{NewTask, Task};
use crate::db::pool::DbPool;
use rusqlite::params;

pub fn create_task(
    pool: &DbPool,
    task: &NewTask,
) -> Result<Task, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status)
         VALUES (?1, ?2, ?3, ?4, ?5, 'pending')",
        params![
            task.task_uuid,
            task.target_agent,
            task.source,
            task.method,
            task.params,
        ],
    )?;

    let id = conn.last_insert_rowid();
    let mut stmt = conn.prepare(
        "SELECT id, task_uuid, target_agent, source, method, params, status,
                result, error, retry_count, max_retries, created_at, started_at, completed_at
         FROM tasks WHERE id = ?1"
    )?;

    Ok(stmt.query_row(params![id], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            created_at: row.get(11)?,
            started_at: row.get(12)?,
            completed_at: row.get(13)?,
        })
    })?)
}

pub fn claim_pending_task(
    pool: &DbPool,
) -> Result<Option<Task>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "UPDATE tasks SET status = 'running', started_at = datetime('now')
         WHERE task_uuid = (
             SELECT task_uuid FROM tasks
             WHERE status = 'pending'
             ORDER BY created_at ASC
             LIMIT 1
         )
         RETURNING id, task_uuid, target_agent, source, method, params, status,
                   result, error, retry_count, max_retries, created_at, started_at, completed_at"
    )?;

    let result = stmt.query_row([], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            created_at: row.get(11)?,
            started_at: row.get(12)?,
            completed_at: row.get(13)?,
        })
    });

    match result {
        Ok(task) => Ok(Some(task)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.into()),
    }
}

pub fn get_task_by_uuid(
    pool: &DbPool,
    task_uuid: &str,
) -> Result<Option<Task>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, task_uuid, target_agent, source, method, params, status,
                result, error, retry_count, max_retries, created_at, started_at, completed_at
         FROM tasks WHERE task_uuid = ?1"
    )?;
    let mut rows = stmt.query_map(params![task_uuid], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            created_at: row.get(11)?,
            started_at: row.get(12)?,
            completed_at: row.get(13)?,
        })
    })?;
    Ok(rows.next().and_then(|r| r.ok()))
}

pub fn complete_task(
    pool: &DbPool,
    task_uuid: &str,
    result: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE tasks SET status = 'completed', result = ?1, completed_at = datetime('now')
         WHERE task_uuid = ?2",
        params![result, task_uuid],
    )?;
    Ok(())
}

pub fn fail_task(
    pool: &DbPool,
    task_uuid: &str,
    error: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE tasks SET status = 'failed', error = ?1, completed_at = datetime('now')
         WHERE task_uuid = ?2",
        params![error, task_uuid],
    )?;
    Ok(())
}

pub fn list_all_tasks(
    pool: &DbPool,
) -> Result<Vec<serde_json::Value>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT t.id, t.task_uuid, t.target_agent, t.source, t.method, t.params,
                t.status, t.result, t.error, t.created_at, t.started_at, t.completed_at,
                COALESCE(a.name, t.target_agent) AS agent_name
         FROM tasks t
         LEFT JOIN agents a ON a.id = t.target_agent
         ORDER BY t.created_at DESC
         LIMIT 200"
    )?;
    let rows = stmt.query_map([], |row| {
        let params_str: String = row.get(5)?;
        let task_desc = serde_json::from_str::<serde_json::Value>(&params_str)
            .ok()
            .and_then(|p| p.get("task").and_then(|v| v.as_str().map(String::from)))
            .unwrap_or_default();
        Ok(serde_json::json!({
            "id": row.get::<_, i64>(0)?,
            "task": task_desc,
            "assigned_to": row.get::<_, String>(12)?,
            "status": row.get::<_, String>(6)?,
            "created_at": row.get::<_, String>(9)?,
            "result": row.get::<_, Option<String>>(7)?,
        }))
    })?;
    let mut tasks = Vec::new();
    for row in rows {
        tasks.push(row?);
    }
    Ok(tasks)
}

pub fn get_task_by_id(
    pool: &DbPool,
    task_id: i64,
) -> Result<Option<crate::db::models::Task>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, task_uuid, target_agent, source, method, params, status,
                result, error, retry_count, max_retries, created_at, started_at, completed_at
         FROM tasks WHERE id = ?1"
    )?;
    let mut rows = stmt.query_map(rusqlite::params![task_id], |row| {
        Ok(crate::db::models::Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            created_at: row.get(11)?,
            started_at: row.get(12)?,
            completed_at: row.get(13)?,
        })
    })?;
    Ok(rows.next().and_then(|r| r.ok()))
}

pub fn update_task_status(
    pool: &DbPool,
    task_id: i64,
    status: &str,
    result: Option<&str>,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    if let Some(res) = result {
        conn.execute(
            "UPDATE tasks SET status = ?1, result = ?2, completed_at = datetime('now')
             WHERE id = ?3",
            rusqlite::params![status, res, task_id],
        )?;
    } else {
        conn.execute(
            "UPDATE tasks SET status = ?1 WHERE id = ?2",
            rusqlite::params![status, task_id],
        )?;
    }
    Ok(())
}

pub fn delete_task_by_id(
    pool: &DbPool,
    task_id: i64,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "DELETE FROM tasks WHERE id = ?1",
        rusqlite::params![task_id],
    )?;
    Ok(())
}

pub fn list_transfer_edges(
    pool: &DbPool,
) -> Result<Vec<serde_json::Value>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT t.id, t.task_uuid, t.source, t.target_agent, t.params, t.status, t.created_at
         FROM tasks t
         WHERE t.source != 'user'
           AND t.source != 'system'
           AND t.status IN ('completed','running')
         ORDER BY t.created_at DESC
         LIMIT 100"
    )?;
    let rows = stmt.query_map([], |row| {
        let params_str: String = row.get(4)?;
        let summary = serde_json::from_str::<serde_json::Value>(&params_str)
            .ok()
            .and_then(|p| {
                p.get("task")
                    .or_else(|| p.get("content"))
                    .and_then(|v| v.as_str().map(|s| s.chars().take(100).collect::<String>()))
            })
            .unwrap_or_default();
        Ok(serde_json::json!({
            "id": format!("task-{}", row.get::<_, i64>(0)?),
            "from": row.get::<_, String>(2)?,
            "to": row.get::<_, String>(3)?,
            "task_id": row.get::<_, i64>(0)?,
            "type": "task",
            "summary": summary,
            "timestamp": row.get::<_, String>(6)?,
            "replies": [],
        }))
    })?;
    let mut edges = Vec::new();
    for row in rows {
        edges.push(row?);
    }
    Ok(edges)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    #[test]
    fn test_create_and_claim_task() {
        let pool = create_test_pool();
        // Insert a matching agent for FK constraint
        let conn = pool.get().unwrap();
        conn.execute(
            "INSERT INTO agents (id, name, role, model, status) VALUES (?1, ?2, ?3, ?4, ?5)",
            params!["leader", "Leader", "manager", "gpt-4", "running"],
        ).unwrap();
        drop(conn);

        let task = NewTask {
            task_uuid: "task-1".into(),
            target_agent: "leader".into(),
            source: "test".into(),
            method: "chat".into(),
            params: "{}".into(),
        };

        create_task(&pool, &task).unwrap();
        let claimed = claim_pending_task(&pool).unwrap().unwrap();
        assert_eq!(claimed.task_uuid, "task-1");
        assert_eq!(claimed.status, "running");

        // Second claim should return None
        assert!(claim_pending_task(&pool).unwrap().is_none());
    }

    #[test]
    fn test_complete_and_fail() {
        let pool = create_test_pool();
        let conn = pool.get().unwrap();
        conn.execute(
            "INSERT INTO agents (id, name, role, model, status) VALUES (?1, ?2, ?3, ?4, ?5)",
            params!["leader", "Leader", "manager", "gpt-4", "running"],
        ).unwrap();
        drop(conn);

        let task = NewTask {
            task_uuid: "task-2".into(),
            target_agent: "leader".into(),
            source: "test".into(),
            method: "chat".into(),
            params: "{}".into(),
        };

        create_task(&pool, &task).unwrap();
        let claimed = claim_pending_task(&pool).unwrap().unwrap();

        complete_task(&pool, &claimed.task_uuid, r#"{"response":"ok"}"#).unwrap();

        let conn = pool.get().unwrap();
        let result: String = conn.query_row(
            "SELECT result FROM tasks WHERE task_uuid = ?1",
            params!["task-2"],
            |row| row.get(0),
        ).unwrap();
        assert_eq!(result, r#"{"response":"ok"}"#);
    }
}
