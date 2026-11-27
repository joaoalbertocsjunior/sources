//! `sources-lib` — source adapters, registry, JSON-RPC server, and HTTP control plane.
//!
//! # Quick start
//!
//! ```rust,no_run
//! use sources_lib::{SourceRegistry, SourceBridge};
//! use sources_lib::adapters::shell::ShellAdapter;
//! use std::time::Duration;
//!
//! # async fn example() {
//! let registry = SourceRegistry::new();
//! registry.register(Box::new(ShellAdapter::new("uname", "uname -a")));
//! let (bridge, mut rx) = SourceBridge::new(registry, Duration::from_secs(30));
//! tokio::spawn(bridge.run());
//! while let Some(event) = rx.recv().await {
//!     println!("{}: {}", event.kind, event.payload);
//! }
//! # }
//! ```

#![allow(dead_code)]

pub mod adapter;
pub mod adapters;
pub mod bridge;
pub mod events;
pub mod http;
pub mod kinds;
pub mod rpc;
pub mod mcp;
pub mod registry;
pub mod service;
pub mod store;

// Re-export the most commonly used types at the crate root.
pub use adapter::{AdapterError, SourceAdapter, SourceEvent};
pub use bridge::SourceBridge;
pub use events::EventBus;
pub use http::HttpControlServer;
pub use kinds::{KindBacking, KindDef, KindRegistry};
pub use rpc::RpcServer;
pub use mcp::server::McpServer;
pub use registry::SourceRegistry;
pub use service::SourceService;
pub use store::{Store, StoredSource};
