use crate::auth;
use crate::db::pool::DbPool;
use axum::extract::DefaultBodyLimit;
use axum::{routing::get, Json, Router};
use tokio::sync::broadcast;
use tokio::sync::mpsc::Sender;
use tower_http::compression::CompressionLayer;
use tower_http::cors::CorsLayer;

use crate::dispatch::engine::{TaskEvent, WsEvent};

use super::{agents_detail, agents_list, chat, chat_groups, collab, deliveries, hire, knowledge, mailbox, scenes, schedule, skills, tasks, usage, ws};

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
        .route("/api/mailbox", axum::routing::get(mailbox::list_handler))
        .route("/api/mailbox/send", axum::routing::post(mailbox::send_handler))
        .route("/api/mailbox/:agent_id", axum::routing::get(mailbox::get_messages_handler))
        .route("/api/mailbox/:agent_id/read", axum::routing::post(mailbox::mark_read_handler))
        .route("/api/hiring/request", axum::routing::post(hire::create_handler))
        .route("/api/hiring/pending", axum::routing::get(hire::list_handler))
        .route("/api/hiring/:request_uuid/approve", axum::routing::post(hire::approve_handler))
        .route("/api/hiring/:request_uuid/reject", axum::routing::post(hire::reject_handler))
        .route("/api/scenes", axum::routing::get(scenes::list_handler).post(scenes::create_handler))
        .route("/api/scenes/:id", axum::routing::get(scenes::get_handler).delete(scenes::delete_handler))
        .route("/api/skills", axum::routing::get(skills::list_handler).post(skills::create_handler))
        .route("/api/skills/:id", axum::routing::get(skills::get_handler))
        .route("/api/tasks/:task_uuid", axum::routing::get(tasks::get_task_handler))
        .route("/api/chat/groups", axum::routing::get(chat_groups::list_groups).post(chat_groups::create_group))
        .route("/api/chat/groups/:group_id", axum::routing::get(chat_groups::get_group).patch(chat_groups::update_group).delete(chat_groups::delete_group))
        .route("/api/chat/groups/:group_id/members", axum::routing::post(chat_groups::add_member))
        .route("/api/chat/groups/:group_id/members/:agent_id", axum::routing::delete(chat_groups::remove_member))
        .route("/api/chat/groups/:group_id/messages", axum::routing::post(chat_groups::send_message).get(chat_groups::get_messages))
        .route("/api/chat/groups/:group_id/messages/:msg_id/recall", axum::routing::post(chat_groups::recall_message))
        .route("/api/chat/groups/:group_id/messages/:msg_id/read", axum::routing::post(chat_groups::mark_read))
        .route("/api/deliveries/create", axum::routing::post(deliveries::create_delivery))
        .route("/api/deliveries", axum::routing::get(deliveries::list_deliveries))
        .route("/api/deliveries/:id", axum::routing::get(deliveries::get_delivery))
        .route("/api/deliveries/:id/archive", axum::routing::post(deliveries::archive_delivery))
        .route("/api/deliveries/:id/read", axum::routing::post(deliveries::mark_read))
        .route("/api/deliveries/:id/approve", axum::routing::post(deliveries::approve_delivery))
        .route("/api/deliveries/:id/request-changes", axum::routing::post(deliveries::request_changes))
        .route("/api/deliveries/:id/files/:filename", axum::routing::get(deliveries::download_file))
        .route("/api/agents", axum::routing::get(agents_list::list_agents))
        .route("/api/agents/display", axum::routing::get(agents_detail::list_displays_handler))
        .route("/api/agents/:id", axum::routing::get(agents_list::get_agent).patch(agents_list::update_agent).delete(agents_list::delete_agent))
        .route("/api/agents/:id/profile", axum::routing::get(agents_detail::get_profile_handler))
        .route("/api/agents/:id/skills", axum::routing::get(agents_detail::get_skills_handler).patch(agents_detail::update_skills_handler))
        .route("/api/agents/:id/memory", axum::routing::get(agents_detail::get_memory_handler))
        .route("/api/agents/:id/history", axum::routing::get(agents_detail::get_history_handler))
        .route("/api/agents/:id/display", axum::routing::get(agents_detail::get_display_handler).put(agents_detail::update_display_handler))
        .route("/api/activity", get(|| async { Json(serde_json::json!({"activities": []})) }))
        .route("/api/usage", axum::routing::get(usage::get_usage_handler))
        .route("/api/schedule", axum::routing::get(schedule::list_schedule_handler))
        .route("/api/schedule/tasks", axum::routing::post(schedule::create_schedule_handler))
        .route("/api/schedule/tasks/:id", axum::routing::patch(schedule::update_schedule_handler).delete(schedule::delete_schedule_handler))
        .route("/api/collaboration/graph", axum::routing::get(collab::get_collab_graph_handler))
        .route("/api/knowledge", axum::routing::get(knowledge::list_handler))
        .route("/api/knowledge/upload", axum::routing::post(knowledge::upload_handler))
        .route("/api/knowledge/:kb_name", axum::routing::get(knowledge::kb_detail_handler))
        .route("/api/knowledge/:kb_name/process", axum::routing::post(knowledge::process_handler))
        .route("/api/knowledge/:kb_name/tasks", axum::routing::get(knowledge::tasks_handler))
        .route("/api/knowledge/:kb_name/wiki", axum::routing::get(knowledge::wiki_list_handler))
        .route("/api/knowledge/:kb_name/wiki/:page_type/:page_name", axum::routing::get(knowledge::wiki_page_handler))
        .route("/api/knowledge/:kb_name/search", axum::routing::get(knowledge::search_handler))
        .route("/api/upload/extract", axum::routing::post(knowledge::extract_handler))
        .route("/ws", get(ws::ws_handler))
        .layer(DefaultBodyLimit::max(10 * 1024 * 1024)) // 10MB
        .layer(CompressionLayer::new())
        .layer(cors)
        .with_state(state)
}
