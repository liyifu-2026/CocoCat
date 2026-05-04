use axum::Json;
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Clone)]
pub struct JwtState {
    pub secret: Arc<String>,
}

impl JwtState {
    pub fn from_env() -> Self {
        let secret = std::env::var("JWT_SECRET")
            .unwrap_or_else(|_| {
                tracing::warn!("JWT_SECRET not set, using insecure default");
                "cococat-insecure-dev-secret".to_string()
            });
        if secret == "cococat-dev-jwt-secret-2024" || secret == "cococat-insecure-dev-secret" {
            tracing::warn!("JWT_SECRET is using a known default value - set a strong secret in production");
        }
        Self {
            secret: Arc::new(secret),
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub exp: usize,
    pub role: String,
}

#[derive(Deserialize)]
pub struct LoginRequest {
    pub password: String,
}

#[derive(Serialize)]
pub struct LoginResponse {
    pub token: String,
}

pub async fn login(
    Json(req): Json<LoginRequest>,
) -> Result<Json<LoginResponse>, axum::http::StatusCode> {
    let expected = std::env::var("WEB_PASSWORD").unwrap_or_else(|_| "123456".to_string());
    if req.password != expected {
        return Err(axum::http::StatusCode::UNAUTHORIZED);
    }

    let secret = std::env::var("JWT_SECRET")
        .unwrap_or_else(|_| "cococat-insecure-dev-secret".to_string());

    let claims = Claims {
        sub: "admin".into(),
        exp: (std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            + 28800) as usize,
        role: "admin".into(),
    };

    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )
    .map_err(|_| axum::http::StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(LoginResponse { token }))
}

pub fn verify_token(
    headers: &axum::http::HeaderMap,
    jwt: &JwtState,
) -> Result<Claims, axum::http::StatusCode> {
    let auth_header = headers
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .ok_or(axum::http::StatusCode::UNAUTHORIZED)?;

    let token = auth_header
        .strip_prefix("Bearer ")
        .ok_or(axum::http::StatusCode::UNAUTHORIZED)?;

    let data = decode::<Claims>(
        token,
        &DecodingKey::from_secret(jwt.secret.as_bytes()),
        &Validation::default(),
    )
    .map_err(|_| axum::http::StatusCode::UNAUTHORIZED)?;

    Ok(data.claims)
}
