#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};

/// How a dynamically registered kind produces data.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum KindBacking {
    /// Run a shell command; `{{id}}` and `{{config.*}}` are substituted at sync time.
    Shell { command: String },
    /// Poll an HTTP endpoint; `{{config.url}}` is substituted at sync time.
    Http { url_template: String, method: String },
}

/// Definition of a dynamically registered source kind.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KindDef {
    pub kind: String,
    pub description: String,
    pub backing: KindBacking,
}

/// Registry of adapter *kinds* (types), both built-in and runtime-registered.
///
/// Built-in kinds are pre-populated; new ones can be added at runtime via the
/// HTTP control plane (`POST /sources/kinds`) or the M2M JSON-RPC server
/// (`sources.register_kind`).
#[derive(Clone)]
pub struct KindRegistry {
    kinds: Arc<Mutex<HashMap<String, KindDef>>>,
}

impl KindRegistry {
    /// Create a registry pre-populated with the built-in kind names.
    pub fn new() -> Self {
        let mut map: HashMap<String, KindDef> = HashMap::new();
        for name in BUILTIN_KINDS {
            map.insert(
                name.to_string(),
                KindDef {
                    kind: name.to_string(),
                    description: format!("Built-in {name} adapter"),
                    backing: KindBacking::Shell {
                        command: String::new(),
                    },
                },
            );
        }
        Self {
            kinds: Arc::new(Mutex::new(map)),
        }
    }

    /// Register or replace a kind definition.
    pub fn register(&self, def: KindDef) {
        let mut map = self.kinds.lock().expect("kind registry lock poisoned");
        map.insert(def.kind.clone(), def);
    }

    /// Return all registered kind definitions.
    pub fn list(&self) -> Vec<KindDef> {
        let map = self.kinds.lock().expect("kind registry lock poisoned");
        map.values().cloned().collect()
    }

    /// Look up a kind by name.
    pub fn get(&self, kind: &str) -> Option<KindDef> {
        let map = self.kinds.lock().expect("kind registry lock poisoned");
        map.get(kind).cloned()
    }
}

impl Default for KindRegistry {
    fn default() -> Self {
        Self::new()
    }
}

const BUILTIN_KINDS: &[&str] = &[
    "file",
    "shell",
    "env",
    "http_poll",
    "webhook",
    "git",
    "github",
    "database",
    "directory",
    "codebase",
    "folder",
    "local_data",
    "metric",
    "a2a",
];
