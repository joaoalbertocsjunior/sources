#![allow(dead_code)]

use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::post, Json, Router};
use serde_json::Value;
use tokio::sync::Mutex;

use crate::adapter::{AdapterError, SourceAdapter, SourceEvent};

type EventQueue = Arc<Mutex<Vec<SourceEvent>>>;

/// Receives HTTP push events on a local endpoint and surfaces them on `sync()`.
///
/// Callers POST JSON to `http://127.0.0.1:{port}/webhook`; each payload is
/// buffered and returned (then cleared) on the next `sync()` call.
///
/// # Example
/// ```no_run
/// use sources_lib::adapters::webhook::WebhookAdapter;
/// use std::net::SocketAddr;
///
/// # async fn run() {
/// let (adapter, server) = WebhookAdapter::new(
///     "my-hook",
///     "0.0.0.0:9000".parse().unwrap(),
/// );
/// tokio::spawn(server);  // start the HTTP listener
/// # }
/// ```
pub struct WebhookAdapter {
    id: String,
    queue: EventQueue,
}

impl WebhookAdapter {
    /// Create the adapter and a future that runs the HTTP listener.
    /// Spawn the returned future (e.g. with `tokio::spawn`) before calling `sync()`.
    pub fn new(
        id: impl Into<String>,
        addr: SocketAddr,
    ) -> (Self, impl std::future::Future<Output = ()>) {
        let id = id.into();
        let queue: EventQueue = Arc::new(Mutex::new(Vec::new()));

        let state = WebhookState {
            id: id.clone(),
            queue: Arc::clone(&queue),
        };

        let server = async move {
            let app = Router::new()
                .route("/webhook", post(webhook_handler))
                .with_state(state);

            match tokio::net::TcpListener::bind(addr).await {
                Ok(listener) => {
                    tracing::info!("WebhookAdapter listening on {addr}");
                    let _ = axum::serve(listener, app).await;
                }
                Err(e) => tracing::error!("WebhookAdapter failed to bind {addr}: {e}"),
            }
        };

        (Self { id, queue }, server)
    }
}

#[async_trait]
impl SourceAdapter for WebhookAdapter {
    fn id(&self) -> &str {
        &self.id
    }

    fn kind(&self) -> &str {
        "webhook"
    }

    async fn sync(&mut self) -> Result<Vec<SourceEvent>, AdapterError> {
        let mut queue = self.queue.lock().await;
        Ok(std::mem::take(&mut *queue))
    }
}

#[derive(Clone)]
struct WebhookState {
    id: String,
    queue: EventQueue,
}

async fn webhook_handler(
    State(state): State<WebhookState>,
    Json(payload): Json<Value>,
) -> impl IntoResponse {
    let event = SourceEvent {
        source_id: state.id.clone(),
        kind: "webhook.push".to_owned(),
        payload,
        at_unix: unix_now(),
    };
    state.queue.lock().await.push(event);
    StatusCode::ACCEPTED
}

fn unix_now() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}
