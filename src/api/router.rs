use crate::db::pool::DbPool;
use axum::Router;
use tokio::sync::mpsc::Sender;

use crate::dispatch::engine::TaskEvent;

#[derive(Clone)]
pub struct AppState {
    pub db_pool: DbPool,
    pub task_tx: Sender<TaskEvent>,
}

pub fn build(_state: AppState) -> Router {
    Router::new()
        .route("/api/health", axum::routing::get(|| async { "OK" }))
}
