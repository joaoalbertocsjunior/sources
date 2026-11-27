# sources-lib

**Connect any data source from any language — no Python required.**

sources-lib is a Rust crate that gives Go, Rust, C++, Java, and any other runtime a unified adapter layer over files, shell, HTTP, Git, GitHub, databases, AI executors, MCP servers, and A2A agents — exposed over JSON-RPC 2.0 and a REST control plane.

If your stack isn't Python or TypeScript, this is the missing integration layer.

---

## Why sources-lib

LangChain, LlamaIndex, and the MCP SDKs are Python/TypeScript-first. If you're running Rust, Go, or C++, your options are: FFI into Python (painful), reimplement adapters from scratch (expensive), or use sources-lib.

- **Language-agnostic** — JSON-RPC 2.0 wire protocol; call it from any runtime
- **Standalone binary** — spawn as a sidecar subprocess, no Python install needed on the target host
- **15 built-in adapters** — file, shell, env, HTTP poll, webhook, Git, GitHub, database, directory, codebase, local data, metrics, MCP server, A2A
- **Event bus** — broadcast fan-out so multiple consumers subscribe to adapter events independently
- **HTTP control plane** — REST API over the full adapter registry, ready for dashboards and orchestrators
- **File-backed persistence** — kinds, source configs, and event log survive restarts with no external database

---

## Install

```toml
[dependencies]
sources-lib = { git = "https://github.com/joaoalbertocsjunior/sources" }
```

> crates.io publish coming — track [#3](https://github.com/joaoalbertocsjunior/sources/issues/3)

---

## Quick start

```rust
use sources_lib::{SourceRegistry, SourceAdapter, SourceRecord};

let registry = SourceRegistry::new();
registry.register("file", sources_lib::adapters::file::FileAdapter::new());

let record = registry.add("file", serde_json::json!({"path": "/var/log/app.log"}))?;
let rows = registry.sync(&record.id)?;
```

---

## Adapters

| Kind | Description |
|---|---|
| `file` | Read and watch local files |
| `shell` | Run shell commands, capture stdout |
| `env` | Environment variable snapshots |
| `http_poll` | Poll HTTP endpoints at an interval |
| `webhook` | Receive HTTP push events (reverse of `http_poll`) |
| `git` | Git repo state, commits, diffs |
| `github` | GitHub issues, PRs, releases via API |
| `database` | Postgres query results (SQLx) |
| `directory` | Directory listings and change events |
| `codebase` | Source file indexing |
| `folder` | Folder trees with metadata |
| `local_data` | Arbitrary local JSON/YAML data files |
| `metric` | Numeric metric streams |
| `a2a` | A2A agent endpoints |
| `mcp_server` | Upstream MCP servers as sources — pulls resources via MCP protocol |

---

## MCP server

sources-lib can expose itself as an MCP server so any MCP client (Claude Code, goose, URACE, etc.) can read from all adapters via MCP `resources` and write to GitHub via MCP `tools`.

```rust
use std::{net::SocketAddr, sync::Arc};
use sources_lib::{McpServer, SourceRegistry, KindRegistry, SourceService};

let service = Arc::new(
    SourceService::new(Arc::new(SourceRegistry::new()), KindRegistry::new())
);

let server = McpServer::new(Arc::clone(&service), "0.0.0.0:7700".parse().unwrap());

// Register GitHub adapters for write-side tools
server.register_github("my-repo", "owner", "repo", Some("ghp_token"));

server.serve().await?;
```

**MCP endpoint:** `POST /mcp` — JSON-RPC 2.0, MCP protocol version `2024-11-05`

**Resources** (read-only, no auth):

| URI pattern | Returns |
|---|---|
| `sources://{id}/events` | Latest synced events from that adapter |
| `sources://{id}/agents-md` | AGENTS.md content from a GitHub adapter |
| `sources://{id}/skill-md` | SKILL.md content from a GitHub adapter |
| `sources://{id}/commits` | Last 20 commits from a GitHub adapter |
| `sources://{id}/releases` | Latest releases from a GitHub adapter |
| `sources://{id}/file/{path}` | Arbitrary file contents from a GitHub adapter |

**Tools** (GitHub write operations):

| Tool | Description |
|---|---|
| `github_create_issue` | Create a GitHub issue |
| `github_close_issue` | Close a GitHub issue |
| `github_comment_on_issue` | Comment on an issue or PR |
| `github_create_pr` | Open a pull request |
| `github_trigger_workflow` | Trigger a workflow dispatch |
| `github_update_file` | Create or update a file (for AGENTS.md, SKILL.md, etc.) |
| `github_create_release` | Create a release |

---

## M2M — JSON-RPC 2.0

Expose your registry over JSON-RPC 2.0 so any language can call it over HTTP:

```rust
use std::sync::Arc;
use sources_lib::{SourceRegistry, KindRegistry, SourceService, M2MServer};

let service = Arc::new(
    SourceService::new(Arc::new(SourceRegistry::new()), KindRegistry::new())
);

let server = M2MServer::new("0.0.0.0:7000".parse().unwrap());
server.wire_service(Arc::clone(&service)).await;  // registers sources.* methods
server.register("echo", |params| params).await;   // add custom methods
server.serve().await?;
```

Built-in methods wired by `wire_service`:

| Method | Description |
|---|---|
| `sources.list` | List registered source IDs |
| `sources.list_kinds` | List all kinds (built-in + dynamic) |
| `sources.register_kind` | Register a new kind, persisted if store attached |

---

## HTTP control plane

```rust
use std::sync::Arc;
use sources_lib::{SourceRegistry, KindRegistry, SourceService, Store, HttpControlServer};

let service = Arc::new(
    SourceService::new(Arc::new(SourceRegistry::new()), KindRegistry::new())
        .with_store(Arc::new(Store::open("./data")?))
);

let server = HttpControlServer::new(Arc::clone(&service), "0.0.0.0:8080".parse().unwrap());
server.serve().await?;
```

| Method | Route | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/sources` | List registered source IDs |
| GET | `/sources/kinds` | List all kinds (built-in + dynamic) |
| POST | `/sources/kinds` | Register a new adapter kind at runtime |
| POST | `/sources/{id}/sync` | Sync a source, return records |

---

## Dynamic kind registration

New adapter **kinds** (types) can be registered at runtime without recompiling — over both HTTP and M2M.

**Over HTTP:**

```bash
curl -X POST http://localhost:8080/sources/kinds \
  -H 'Content-Type: application/json' \
  -d '{
    "kind": "my_script",
    "description": "Custom shell-backed adapter",
    "backing": {"type": "shell", "command": "my-harvester --id {{id}}"}
  }'
# → {"kind":"my_script","status":"registered"}
```

**Over M2M (JSON-RPC 2.0):**

```bash
curl -X POST http://localhost:7000/rpc \
  -H 'Content-Type: application/json' \
  -d '{
    "method": "sources.register_kind",
    "params": {
      "kind": "my_script",
      "description": "Custom shell-backed adapter",
      "backing": {"type": "shell", "command": "my-harvester --id {{id}}"}
    }
  }'
```

Dynamic kinds are stored to `kinds.json` automatically and reloaded on the next startup when a `Store` is attached.

---

## Persistence

Attach a `Store` to a `SourceService` to enable file-backed persistence with no external database required.

```rust
use std::sync::Arc;
use sources_lib::{SourceRegistry, KindRegistry, SourceService, Store, StoredSource};

let store = Arc::new(Store::open("./data")?);

// on startup: load previously saved sources so the application can re-register them
let service = Arc::new(
    SourceService::new(Arc::new(SourceRegistry::new()), KindRegistry::new())
        .with_store(Arc::clone(&store))   // also reloads persisted dynamic kinds
);
let saved = service.load_sources();       // Vec<StoredSource> from sources.json

// after registering adapters: persist their configs for next restart
service.save_sources(&[
    StoredSource { id: "logs".into(), kind: "file".into(), config: serde_json::json!({"path": "/var/log/app.log"}) },
]);

// log events as they are produced
service.log_event(&event);               // appends to events.jsonl
```

**Files written inside the store directory:**

| File | Contents |
|---|---|
| `kinds.json` | Dynamically registered kind definitions (built-ins excluded) |
| `sources.json` | Adapter config snapshots saved by the application |
| `events.jsonl` | Append-only newline-delimited JSON event log |

---

## Bridge

Connect two sources directly — pull from one, push to another:

```rust
use sources_lib::bridge::Bridge;

let bridge = Bridge::new("logs", "db", "push");
bridge.run(&registry).await?;
```

---

## Events

```rust
use sources_lib::events::EventBus;

let bus = EventBus::new();
let mut rx = bus.subscribe();
bus.publish(event);
```

---

## Module map

| Module | Contents |
|---|---|
| `sources_lib` | `SourceAdapter` trait, `SourceRegistry`, `SourceEvent`, `AdapterError` |
| `sources_lib::adapters` | All 14 built-in adapters |
| `sources_lib::kinds` | `KindRegistry`, `KindDef`, `KindBacking` — runtime kind registration |
| `sources_lib::service` | `SourceService` — shared business logic for HTTP and M2M |
| `sources_lib::store` | `Store`, `StoredSource` — file-backed persistence |
| `sources_lib::m2m` | JSON-RPC 2.0 server with `wire_service` |
| `sources_lib::http` | Axum REST control server |
| `sources_lib::bridge` | Stateless source-to-source connector |
| `sources_lib::events` | `EventBus` broadcast pub/sub |
| `sources_lib::registry` | `SourceRegistry` |
| `sources_lib::mcp` | `McpServer` — MCP 2024-11-05 server exposing adapters as resources and GitHub write tools |

---

## License

Apache-2.0
