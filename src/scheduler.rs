use std::time::{Duration, SystemTime, UNIX_EPOCH};

use tokio::sync::mpsc::Sender;

use crate::db::models::NewTask;
use crate::db::pool::DbPool;
use crate::db::tasks;
use crate::dispatch::engine::TaskEvent;

fn parse_sqlite_datetime(s: &str) -> Option<u64> {
    // Parse "YYYY-MM-DD HH:MM:SS" to unix timestamp
    let parts: Vec<&str> = s.split(|c| c == ' ' || c == '-' || c == ':' || c == 'T').collect();
    if parts.len() < 6 { return None; }
    let y: u64 = parts[0].parse().ok()?;
    let m: u64 = parts[1].parse().ok()?;
    let d: u64 = parts[2].parse().ok()?;
    let hh: u64 = parts[3].parse().ok()?;
    let mm: u64 = parts[4].parse().ok()?;
    let ss: u64 = parts[5].parse().ok()?;
    // Rough unix timestamp (leap seconds ignored)
    let days_since_epoch = (y - 1970) * 365 + (y - 1970) / 4 + // leap years
        match m { 1 => 0, 2 => 31, 3 => 59, 4 => 90, 5 => 120, 6 => 151,
                  7 => 181, 8 => 212, 9 => 243, 10 => 273, 11 => 304, _ => 334 } +
        d - 1;
    Some(days_since_epoch * 86400 + hh * 3600 + mm * 60 + ss)
}

fn now_unix() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

pub struct SchedulerService;

impl SchedulerService {
    pub fn start(db_pool: DbPool, task_tx: Sender<TaskEvent>) {
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(60));
            interval.tick().await;
            loop {
                interval.tick().await;
                if let Err(e) = Self::check_recurring(&db_pool, &task_tx).await {
                    tracing::error!("SchedulerService: {}", e);
                }
            }
        });
        tracing::info!("SchedulerService started (interval: 60s)");
    }

    async fn check_recurring(
        db_pool: &DbPool,
        task_tx: &Sender<TaskEvent>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let now = now_unix();
        let templates = tasks::list_recurring_templates(db_pool)?;
        for template in templates {
            let interval_minutes: i64 = serde_json::from_str::<serde_json::Value>(
                &template.recurrence.clone().unwrap_or_default()
            )
            .ok()
            .and_then(|v| v.get("interval").and_then(|n| n.as_i64()))
            .unwrap_or(60);

            let last_instance = tasks::get_last_recurring_instance(db_pool, template.id)?;

            let should_run = match &last_instance {
                Some(inst) => {
                    inst.completed_at.as_ref().map_or(true, |completed| {
                        parse_sqlite_datetime(completed).map_or(true, |last| {
                            (now - last) >= (interval_minutes as u64 * 60)
                        })
                    })
                }
                None => {
                    parse_sqlite_datetime(&template.created_at).map_or(true, |created| {
                        (now - created) >= (interval_minutes as u64 * 60)
                    })
                }
            };

            if should_run {
                let task_uuid = uuid::Uuid::new_v4().to_string();
                let new_task = NewTask {
                    task_uuid: task_uuid.clone(),
                    target_agent: template.target_agent.clone(),
                    source: "system".into(),
                    method: "recurring".into(),
                    params: template.params.clone(),
                    task_type: Some("recurring_instance".into()),
                    recurrence: None,
                    parent_task_id: Some(template.id),
                };
                tasks::create_task(db_pool, &new_task)?;
                let _ = task_tx.send(TaskEvent::NewTask { task_uuid }).await;
                tracing::info!(
                    "Scheduler: created instance of recurring task {} for agent {}",
                    template.id, template.target_agent
                );
            }
        }
        Ok(())
    }
}
