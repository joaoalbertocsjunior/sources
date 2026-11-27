#![allow(dead_code)]

use std::sync::Arc;

use crate::adapter::SourceEvent;
use crate::kinds::{KindDef, KindRegistry, BUILTIN_KINDS};
use crate::registry::SourceRegistry;
use crate::store::Store;

/// Thin orchestration layer shared by the HTTP control plane and the M2M
/// JSON-RPC server.
///
/// Both transports hold an `Arc<SourceService>` and delegate all business
/// logic here.  Neither transport knows about the other.
///
/// # Persistence
///
/// Pass a [`Store`] via [`SourceService::with_store`].  Dynamic kind
/// definitions are flushed automatically on every [`register_kind`] call.
/// Source configs and event appends are explicit — call [`save_sources`] and
/// [`log_event`] from the application after mutations.
pub struct SourceService {
    pub registry: Arc<SourceRegistry>,
    pub kinds: KindRegistry,
    store: Option<Arc<Store>>,
}

impl SourceService {
    pub fn new(registry: Arc<SourceRegistry>, kinds: KindRegistry) -> Self {
        Self {
            registry,
            kinds,
            store: None,
        }
    }

    /// Attach a store.  Immediately loads any previously persisted dynamic
    /// kind definitions so they are available before serving requests.
    pub fn with_store(mut self, store: Arc<Store>) -> Self {
        if let Ok(defs) = store.load_kinds() {
            for def in defs {
                self.kinds.register(def);
            }
        }
        self.store = Some(store);
        self
    }

    // --- kinds ---

    /// Register a kind and persist it if a store is attached.
    /// Built-in kinds are updated in memory only (they never need to be
    /// re-persisted since `KindRegistry::new()` always provides them).
    pub fn register_kind(&self, def: KindDef) {
        self.kinds.register(def);
        self.flush_dynamic_kinds();
    }

    pub fn list_kinds(&self) -> Vec<KindDef> {
        self.kinds.list()
    }

    // --- sources ---

    pub fn list_sources(&self) -> Vec<String> {
        self.registry.list()
    }

    /// Persist the given source configs.  Call after registering adapters so
    /// the application can rebuild the registry on next startup.
    pub fn save_sources(&self, sources: &[crate::store::StoredSource]) {
        if let Some(store) = &self.store {
            let _ = store.save_sources(sources);
        }
    }

    /// Return previously saved source configs (empty if no store or no file).
    pub fn load_sources(&self) -> Vec<crate::store::StoredSource> {
        self.store
            .as_ref()
            .and_then(|s| s.load_sources().ok())
            .unwrap_or_default()
    }

    // --- event log ---

    /// Append an event to the persistent log (no-op if no store is attached).
    pub fn log_event(&self, event: &SourceEvent) {
        if let Some(store) = &self.store {
            let _ = store.append_event(event);
        }
    }

    // --- internal ---

    fn flush_dynamic_kinds(&self) {
        let Some(store) = &self.store else { return };
        let dynamic: Vec<KindDef> = self
            .kinds
            .list()
            .into_iter()
            .filter(|k| !BUILTIN_KINDS.contains(&k.kind.as_str()))
            .collect();
        let _ = store.save_kinds(&dynamic);
    }
}
