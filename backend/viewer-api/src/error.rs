use axum::Json;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("bad request: {0}")]
    BadRequest(String),
    #[error("not found")]
    NotFound,
    #[error("database error: {0}")]
    Db(#[from] sqlx::Error),
    #[error("storage error: {0}")]
    Storage(String),
    #[error("configuration error: {0}")]
    Config(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = match self {
            ApiError::BadRequest(_) => StatusCode::BAD_REQUEST,
            ApiError::NotFound => StatusCode::NOT_FOUND,
            ApiError::Db(_) | ApiError::Storage(_) | ApiError::Config(_) => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
        };
        let body = Json(json!({ "error": self.to_string() }));
        (status, body).into_response()
    }
}

pub type ApiResult<T> = Result<T, ApiError>;
