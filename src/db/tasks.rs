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
