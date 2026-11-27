#![allow(dead_code)]

use std::fs::{self, File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::PathBuf;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::adapter::SourceEvent;
use crate::kinds::KindDef;

/// A source adapter config entry — enough to reconstruct or re-register an
/// adapter instance across restarts without holding live Rust objects.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredSource {
    pub id: String,
    pub kind: String,
    pub config: Value,
}

/// File-backed persistence layer.
///
/// Layout inside `dir/`:
/// - `kinds.json`   — JSON array of dynamically registered [`KindDef`]s
/// - `sources.json` — JSON array of [`StoredSource`] adapter configs
/// - `events.jsonl` — append-only newline-delimited JSON event log
pub struct Store {
    dir: PathBuf,
    event_writer: Mutex<BufWriter<File>>,
}

impl Store {
    /// Open (or create) a store rooted at `dir`.
    pub fn open(dir: impl Into<PathBuf>) -> std::io::Result<Self> {
        let dir = dir.into();
        fs::create_dir_all(&dir)?;
        let events_path = dir.join("events.jsonl");
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(events_path)?;
        Ok(Self {
            dir,
            event_writer: Mutex::new(BufWriter::new(file)),
        })
    }

    // --- kinds ---

    pub fn load_kinds(&self) -> std::io::Result<Vec<KindDef>> {
        let path = self.dir.join("kinds.json");
        if !path.exists() {
            return Ok(vec![]);
        }
        let data = fs::read_to_string(&path)?;
        serde_json::from_str(&data)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
    }

    pub fn save_kinds(&self, kinds: &[KindDef]) -> std::io::Result<()> {
        let path = self.dir.join("kinds.json");
        let data = serde_json::to_string_pretty(kinds)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        fs::write(path, data)
    }

    // --- sources ---

    pub fn load_sources(&self) -> std::io::Result<Vec<StoredSource>> {
        let path = self.dir.join("sources.json");
        if !path.exists() {
            return Ok(vec![]);
        }
        let data = fs::read_to_string(&path)?;
        serde_json::from_str(&data)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
    }

    pub fn save_sources(&self, sources: &[StoredSource]) -> std::io::Result<()> {
        let path = self.dir.join("sources.json");
        let data = serde_json::to_string_pretty(sources)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        fs::write(path, data)
    }

    // --- event log ---

    /// Append one event to `events.jsonl`.  Flushes immediately so the log is
    /// consistent even if the process is killed between writes.
    pub fn append_event(&self, event: &SourceEvent) -> std::io::Result<()> {
        let line = serde_json::to_string(event)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        let mut writer = self.event_writer.lock().expect("event writer lock poisoned");
        writeln!(writer, "{line}")?;
        writer.flush()
    }
}
