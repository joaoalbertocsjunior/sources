#![allow(dead_code)]

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde_json::json;

use crate::kinds::KindDef;
use crate::service::SourceService;

/// Axum-based HTTP control server.
///
/// Routes:
/// - `GET  /health`              — 200 OK
/// - `GET  /sources`             — list registered source IDs
/// - `POST /sources/sync/:id`    — trigger a sync for a specific adapter (stub)
/// - `GET  /sources/kinds`       — list all known adapter kinds (built-in + dynamic)
/// - `POST /sources/kinds`       — register a new adapter kind at runtime
pub struct HttpControlServer {
    service: Arc<SourceService>,
    bind_addr: SocketAddr,
}

impl HttpControlServer {
    pub fn new(service: Arc<SourceService>, bind_addr: SocketAddr) -> Self {
        Self { service, bind_addr }
    }

    /// Build the axum `Router` (useful for testing without binding a port).
    pub fn router(&self) -> Router {
        Router::new()
            .route("/health", get(health))
            .route("/sources", get(list_sources))
            .route("/sources/sync/:id", post(sync_source))
            .route("/sources/kinds", get(list_kinds))
            .route("/sources/kinds", post(register_kind))
            .with_state(Arc::clone(&self.service))
    }

    /// Bind and serve.
    pub async fn serve(self) -> Result<(), std::io::Error> {
        let addr = self.bind_addr;
        let router = self.router();
        let listener = tokio::net::TcpListener::bind(addr).await?;
        tracing::info!("HttpControlServer listening on {addr}");
        axum::serve(listener, router).await
    }
}

// --- handlers ---

async fn health() -> impl IntoResponse {
    (StatusCode::OK, Json(json!({"status": "ok"})))
}

async fn list_sources(State(svc): State<Arc<SourceService>>) -> impl IntoResponse {
    Json(json!({ "sources": svc.list_sources() }))
}

async fn sync_source(
    State(svc): State<Arc<SourceService>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    if svc.list_sources().contains(&id) {
        (StatusCode::OK, Json(json!({ "id": id, "status": "sync_triggered" })))
    } else {
        (StatusCode::NOT_FOUND, Json(json!({ "error": "source not found", "id": id })))
    }
}

async fn list_kinds(State(svc): State<Arc<SourceService>>) -> impl IntoResponse {
    Json(json!({ "kinds": svc.list_kinds() }))
}

async fn register_kind(
    State(svc): State<Arc<SourceService>>,
    Json(def): Json<KindDef>,
) -> impl IntoResponse {
    let kind = def.kind.clone();
    svc.register_kind(def);
    tracing::info!("Registered new source kind: {kind}");
    (StatusCode::CREATED, Json(json!({ "kind": kind, "status": "registered" })))
}
