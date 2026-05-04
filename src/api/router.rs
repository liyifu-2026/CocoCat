use crate::auth;
use crate::db::pool::DbPool;
use axum::{routing::get, Router};
use tokio::sync::mpsc::Sender;
use tower_http::cors::CorsLayer;

use crate::dispatch::engine::TaskEvent;

use super::chat;

#[derive(Clone)]
pub struct AppState {
    pub db_pool: DbPool,
    pub task_tx: Sender<TaskEvent>,
    pub jwt: auth::JwtState,
}

pub fn build(state: AppState) -> Router {
    let cors = CorsLayer::permissive();

    Router::new()
        .route("/api/health", get(health))
        .route("/api/auth/login", axum::routing::post(auth::login))
        .route("/api/chat", axum::routing::post(chat::chat_handler))
        .layer(cors)
        .with_state(state)
}

async fn health() -> &'static str {
    "OK"
}
