use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Query, State,
    },
    http::StatusCode,
    response::IntoResponse,
};
use futures_util::{SinkExt, StreamExt};
use serde::Deserialize;
use tokio::sync::broadcast::Sender;

use crate::auth;

use super::router::AppState;

#[derive(Deserialize)]
pub struct WsQuery {
    token: String,
}

pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
    Query(query): Query<WsQuery>,
) -> Result<impl IntoResponse, StatusCode> {
    let headers = {
        let mut h = axum::http::HeaderMap::new();
        let auth_val = format!("Bearer {}", query.token);
        h.insert(
            axum::http::header::AUTHORIZATION,
            axum::http::HeaderValue::from_str(&auth_val).unwrap(),
        );
        h
    };
    auth::verify_token(&headers, &state.jwt)?;

    Ok(ws.on_upgrade(move |socket| handle_socket(socket, state.event_tx.clone())))
}

async fn handle_socket(socket: WebSocket, event_tx: Sender<crate::dispatch::engine::WsEvent>) {
    let (mut ws_sender, mut ws_receiver) = socket.split();
    let mut event_rx = event_tx.subscribe();

    loop {
        tokio::select! {
            event = event_rx.recv() => {
                match event {
                    Ok(ws_event) => {
                        let json = serde_json::to_string(&ws_event).unwrap_or_default();
                        if ws_sender.send(Message::Text(json.into())).await.is_err() {
                            break;
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                }
            }
            msg = ws_receiver.next() => {
                match msg {
                    Some(Ok(Message::Close(_))) | None => break,
                    _ => continue,
                }
            }
        }
    }
}
