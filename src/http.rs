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

use crate::kinds::{KindDef, KindRegistry};
use crate::registry::SourceRegistry;

/// Shared state for the HTTP control server.
#[derive(Clone)]
struct AppState {
    registry: Arc<SourceRegistry>,
    kinds: KindRegistry,
}

/// Axum-based HTTP control server.
///
/// Routes:
/// - `GET  /health`              — 200 OK
/// - `GET  /sources`             — list registered source IDs
/// - `POST /sources/sync/:id`    — trigger a sync for a specific adapter (stub)
/// - `GET  /sources/kinds`       — list all known adapter kinds (built-in + dynamic)
/// - `POST /sources/kinds`       — register a new adapter kind at runtime
pub struct HttpControlServer {
    registry: Arc<SourceRegistry>,
    kinds: KindRegistry,
    bind_addr: SocketAddr,
}

impl HttpControlServer {
    pub fn new(
        registry: Arc<SourceRegistry>,
        kinds: KindRegistry,
        bind_addr: SocketAddr,
    ) -> Self {
        Self { registry, kinds, bind_addr }
    }

    /// Build the axum `Router` (useful for testing without binding a port).
    pub fn router(&self) -> Router {
        let state = AppState {
            registry: Arc::clone(&self.registry),
            kinds: self.kinds.clone(),
        };
        Router::new()
            .route("/health", get(health))
            .route("/sources", get(list_sources))
            .route("/sources/sync/:id", post(sync_source))
            .route("/sources/kinds", get(list_kinds))
            .route("/sources/kinds", post(register_kind))
            .with_state(state)
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

async fn list_sources(State(state): State<AppState>) -> impl IntoResponse {
    let ids = state.registry.list();
    Json(json!({ "sources": ids }))
}

async fn sync_source(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    let ids = state.registry.list();
    if ids.contains(&id) {
        (StatusCode::OK, Json(json!({ "id": id, "status": "sync_triggered" })))
    } else {
        (StatusCode::NOT_FOUND, Json(json!({ "error": "source not found", "id": id })))
    }
}

async fn list_kinds(State(state): State<AppState>) -> impl IntoResponse {
    let kinds = state.kinds.list();
    Json(json!({ "kinds": kinds }))
}

async fn register_kind(
    State(state): State<AppState>,
    Json(def): Json<KindDef>,
) -> impl IntoResponse {
    let kind = def.kind.clone();
    state.kinds.register(def);
    tracing::info!("Registered new source kind: {kind}");
    (StatusCode::CREATED, Json(json!({ "kind": kind, "status": "registered" })))
}
