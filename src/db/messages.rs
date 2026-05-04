use crate::db::models::{Message, NewMessage};
use crate::db::pool::DbPool;
use rusqlite::params;

pub fn insert_message(
    pool: &DbPool,
    msg: &NewMessage,
) -> Result<Message, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, chat_group, metadata)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            msg.msg_uuid,
            msg.agent_id,
            msg.user_id,
            msg.role,
            msg.content,
            msg.scene_id,
            msg.chat_group,
            msg.metadata,
        ],
    )?;

    let id = conn.last_insert_rowid();
    let mut stmt = conn.prepare(
        "SELECT id, msg_uuid, agent_id, user_id, role, content,
                scene_id, chat_group, metadata, created_at
         FROM messages WHERE id = ?1"
    )?;

    Ok(stmt.query_row(params![id], |row| {
        Ok(Message {
            id: row.get(0)?,
            msg_uuid: row.get(1)?,
            agent_id: row.get(2)?,
            user_id: row.get(3)?,
            role: row.get(4)?,
            content: row.get(5)?,
            scene_id: row.get(6)?,
            chat_group: row.get(7)?,
            metadata: row.get(8)?,
            created_at: row.get(9)?,
        })
    })?)
}

pub fn get_recent_messages(
    pool: &DbPool,
    scene_id: &str,
    chat_group: &str,
    limit: i64,
) -> Result<Vec<Message>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, msg_uuid, agent_id, user_id, role, content,
                scene_id, chat_group, metadata, created_at
         FROM messages
         WHERE scene_id = ?1 AND chat_group = ?2
         ORDER BY created_at DESC
         LIMIT ?3"
    )?;

    let messages = stmt
        .query_map(params![scene_id, chat_group, limit], |row| {
            Ok(Message {
                id: row.get(0)?,
                msg_uuid: row.get(1)?,
                agent_id: row.get(2)?,
                user_id: row.get(3)?,
                role: row.get(4)?,
                content: row.get(5)?,
                scene_id: row.get(6)?,
                chat_group: row.get(7)?,
                metadata: row.get(8)?,
                created_at: row.get(9)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

    Ok(messages)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    #[test]
    fn test_insert_and_query_message() {
        let pool = create_test_pool();
        let msg = NewMessage {
            msg_uuid: "test-uuid-1".into(),
            agent_id: None,
            user_id: Some("user1".into()),
            role: "user".into(),
            content: "Hello".into(),
            scene_id: "default".into(),
            chat_group: "general".into(),
            metadata: "{}".into(),
        };

        let saved = insert_message(&pool, &msg).unwrap();
        assert_eq!(saved.content, "Hello");
        assert_eq!(saved.role, "user");

        let recent = get_recent_messages(&pool, "default", "general", 10).unwrap();
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].content, "Hello");
    }
}
