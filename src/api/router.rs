use crate::auth;
use crate::db::pool::DbPool;
use axum::{routing::get, Router};
use tokio::sync::broadcast;
use tokio::sync::mpsc::Sender;
use tower_http::cors::CorsLayer;

use crate::dispatch::engine::{TaskEvent, WsEvent};

use super::{chat, hire, mailbox, scenes, skills, ws};

#[derive(Clone)]
pub struct AppState {
    pub db_pool: DbPool,
    pub task_tx: Sender<TaskEvent>,
    pub jwt: auth::JwtState,
    pub event_tx: broadcast::Sender<WsEvent>,
}

async fn health() -> &'static str {
    "OK"
}

pub fn build(state: AppState) -> Router {
    let cors = CorsLayer::permissive();

    Router::new()
        .route("/api/health", get(health))
        .route("/api/auth/login", axum::routing::post(auth::login))
        .route("/api/chat", axum::routing::post(chat::chat_handler))
        .route("/api/mailbox/send", axum::routing::post(mailbox::send_handler))
        .route("/api/mailbox/inbox", axum::routing::get(mailbox::inbox_handler))
        .route("/api/mailbox/{id}/read", axum::routing::put(mailbox::read_handler))
        .route("/api/hiring/request", axum::routing::post(hire::create_handler))
        .route("/api/hiring/pending", axum::routing::get(hire::list_handler))
        .route("/api/hiring/{request_uuid}/approve", axum::routing::post(hire::approve_handler))
        .route("/api/hiring/{request_uuid}/reject", axum::routing::post(hire::reject_handler))
        .route("/api/scenes", axum::routing::get(scenes::list_handler).post(scenes::create_handler))
        .route("/api/scenes/{id}", axum::routing::get(scenes::get_handler).delete(scenes::delete_handler))
        .route("/api/skills", axum::routing::get(skills::list_handler).post(skills::create_handler))
        .route("/api/skills/{id}", axum::routing::get(skills::get_handler))
        .route("/ws", get(ws::ws_handler))
        .layer(cors)
        .with_state(state)
}
