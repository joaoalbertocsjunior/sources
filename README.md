# sources-lib

**Connect any data source from any language — no Python required.**

sources-lib is a Rust crate that gives Go, Rust, C++, Java, and any other runtime a unified adapter layer over files, shell, HTTP, Git, GitHub, databases, AI executors, MCP servers, and A2A agents — exposed over JSON-RPC 2.0 and a REST control plane.

If your stack isn't Python or TypeScript, this is the missing integration layer.

---

## Why sources-lib

LangChain, LlamaIndex, and the MCP SDKs are Python/TypeScript-first. If you're running Rust, Go, or C++, your options are: FFI into Python (painful), reimplement adapters from scratch (expensive), or use sources-lib.

- **Language-agnostic** — JSON-RPC 2.0 wire protocol; call it from any runtime
- **Standalone binary** — spawn as a sidecar subprocess, no Python install needed on the target host
- **13 built-in adapters** — file, shell, env, HTTP poll, Git, GitHub, database, directory, codebase, local data, metrics, MCP, A2A
- **Event bus** — broadcast fan-out so multiple consumers subscribe to adapter events independently
- **HTTP control plane** — REST API over the full adapter registry, ready for dashboards and orchestrators

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
| `git` | Git repo state, commits, diffs |
| `github` | GitHub issues, PRs, releases via API |
| `database` | Postgres query results (SQLx) |
| `directory` | Directory listings and change events |
| `codebase` | Source file indexing |
| `folder` | Folder trees with metadata |
| `local_data` | Arbitrary local JSON/YAML data files |
| `metric` | Numeric metric streams |
| `a2a` | A2A agent endpoints |

---

## M2M — JSON-RPC 2.0

Expose your registry over JSON-RPC 2.0 so any language can call it over HTTP:

```rust
use sources_lib::m2m::{M2MServer, M2MClient};

let server = M2MServer::new(|token| token == "secret");
server.register("echo", |params| Ok(params));
server.start(7000).await?;

// from any language — curl, Go, Python, Node, ...
let client = M2MClient::new("http://127.0.0.1:7000", "secret");
let result = client.call("echo", serde_json::json!({"msg": "hi"})).await?;
```

---

## HTTP control plane

```rust
use sources_lib::{SourceRegistry, http::HttpControlServer};

let registry = SourceRegistry::new();
let server = HttpControlServer::new(registry, |token| token == "mytoken");
server.start(8080).await?;
```

| Method | Route | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/sources` | List all registered sources |
| GET | `/sources/kinds` | List available adapter kinds |
| POST | `/sources` | Register a new source |
| POST | `/sources/{id}/sync` | Sync a source, return records |
| POST | `/sources/{id}/verify` | Verify source connectivity |
| POST | `/sources/{id}/act/{action}` | Trigger a source action |
| POST | `/rpc` | JSON-RPC 2.0 endpoint |
| GET | `/jobs` | List background jobs |
| GET | `/jobs/{id}` | Job status |

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
bus.subscribe("source.synced", |event| println!("{:?}", event));
bus.publish("source.synced", serde_json::json!({"source_id": "logs"}));
```

---

## Module map

| Module | Contents |
|---|---|
| `sources_lib` | `SourceAdapter` trait, `SourceRegistry`, `SourceRecord`, `SourceError` |
| `sources_lib::adapters` | All 13 built-in adapters |
| `sources_lib::m2m` | JSON-RPC 2.0 server and client |
| `sources_lib::http` | Axum-based REST control server |
| `sources_lib::bridge` | Stateless source-to-source connector |
| `sources_lib::events` | `EventBus` pub/sub, `EventEmitter` |
| `sources_lib::registry` | `SourceRegistry` |

---

## License

Apache-2.0
