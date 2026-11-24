# sources-lib

Agnostic sources adapter, JSON-RPC 2.0 M2M interface, HTTP control server, and event/transport utilities. Stdlib only at core — extras add richer backends.

**Python 3.11+ required for library use.** Non-Python stacks (Rust, Go, Node, …) use the standalone binary — no Python install needed on the target machine.

## Install

```bash
pip install sources-lib
pip install sources-lib[validation]   # jsonschema-backed config validation
pip install sources-lib[ai]           # AIExecutorAdapter (litellm)
pip install sources-lib[mcp]          # MCPSourceAdapter (mcp SDK)
pip install sources-lib[github]       # GitHubAdapter (PyGithub)
pip install sources-lib[http]         # HttpxTransport (httpx)
```

## Standalone binary (polyglot stacks)

Pre-built binaries for Linux x86\_64, macOS arm64, and Windows x86\_64 are published on every [GitHub Release](../../releases). Download, make executable, and spawn from any language:

```rust
// Rust example — no Python install required on target machine
Command::new("sources-lib")
    .args(["serve", "--port", "7000", "--token", "secret"])
    .spawn()?;
```

```go
// Go
exec.Command("sources-lib", "serve", "--port", "7000").Start()
```

Then talk to it over HTTP (see M2M and HTTP Control sections below). Build locally:

```bash
pip install ".[all]" pyinstaller
pyinstaller sources_lib.spec
# → dist/sources-lib
```

## Serve (CLI)

```bash
# Start REST + JSON-RPC server on port 8080
python -m sources_lib serve --port 8080 --token mysecret

# Pre-load sources from a JSON config file
python -m sources_lib serve --port 8080 --config sources.json
```

## Layers

| Layer | Import | Description |
|---|---|---|
| Sources | `from sources_lib import ...` | Adapter protocol, registry, exceptions |
| M2M | `from sources_lib.m2m import M2MServer, M2MClient` | JSON-RPC 2.0 server + client |
| HTTP Control | `from sources_lib.http import HTTPControlServer` | REST server over sources + M2M |
| Bridge | `from sources_lib import Bridge` | Stateless source-to-source connector |
| Events | `from sources_lib.events import EventEmitter, EventBus` | Pub/sub (strong refs and weak refs) |
| Transport | `from sources_lib.transport import LocalTransport, make_http_transport` | Local I/O + HTTP JSON-POST |

## Quick start

```python
from sources_lib import SourceRegistry, BaseSourceAdapter

class MyAdapter(BaseSourceAdapter):
    config_schema = {"type": "object", "required": ["url"]}

    def sync(self, record, config):
        return [{"url": record.config["url"]}]

registry = SourceRegistry()
registry.register_kind("my", MyAdapter())
record = registry.add("my", config={"url": "https://example.com"})
rows = registry.sync(record.id)
```

## Adapters

| Kind | Class | Extra |
|---|---|---|
| `file` | `FileAdapter` | — |
| `shell` | `ShellAdapter` | — |
| `env` | `EnvAdapter` | — |
| `http_poll` | `HttpPollAdapter` | — |
| `webhook` | `WebhookAdapter` | — |
| `database` | `DatabaseAdapter` | — |
| `directory` | `DirectoryAdapter` | — |
| `a2a_agent` | `A2ASourceAdapter` | — |
| `ai_executor` | `AIExecutorAdapter` | `[ai]` |
| `mcp_server` | `MCPSourceAdapter` | `[mcp]` |
| `github` | `GitHubAdapter` | `[github]` |

## M2M — JSON-RPC 2.0

```python
from sources_lib.m2m import M2MServer, M2MClient

server = M2MServer(auth_fn=lambda t: t == "secret")
server.register("echo", lambda params: params,
                params_schema={"type": "object", "properties": {"msg": {"type": "string"}}})
server.start(port=7000)

client = M2MClient("http://127.0.0.1:7000", token="secret")
print(client.call("echo", {"msg": "hi"}))
print(client.call("rpc.listMethods"))
```

Built-in methods: `ping`, `jobs.list`, `jobs.get`, `jobs.submit`, `rpc.listMethods`, `sources.add`, `sources.remove`.

## HTTP Control

```python
from sources_lib.http import HTTPControlServer
from sources_lib.m2m import M2MServer

server = HTTPControlServer(registry=registry, m2m=M2MServer(), auth_fn=lambda t: t == "token")
server.start(port=8080)
```

Routes: `GET /health`, `GET /sources`, `GET /sources/kinds` (returns `{kind: schema}`), `POST /sources`, `POST /sources/{id}/sync`, `POST /sources/{id}/verify`, `POST /sources/{id}/act/{action}`, `POST /rpc`, `GET /jobs`, `GET /jobs/{id}`.

**Embedding in your own framework:** `SourceRegistry` and `M2MServer` are plain objects — no server is started until you call `.start()`. If you already run Flask, FastAPI, or any other HTTP framework, skip `HTTPControlServer` and call the registry/M2M objects directly from your own route handlers.

**Remaining platform constraint:** the standalone binary must be built for the target OS/arch. The release CI covers Linux x86\_64, macOS arm64, and Windows x86\_64. Other targets (e.g. Linux arm64, musl libc) require a local build with `pyinstaller sources_lib.spec` on the target platform.

## Bridge

```python
from sources_lib import Bridge

# Sync from "logs" file source, write each row to "db" database source
bridge = Bridge("logs", "db", action="push")
results = bridge.run(registry)
```

## Registry — JSON config

```python
registry.load_config({
    "sources": [
        {"kind": "file",  "id": "logs",  "config": {"path": "/var/log/app.log"}},
        {"kind": "env",   "id": "env",   "config": {"prefix": "APP_"}},
    ]
})
```

## Events

```python
from sources_lib.events import EventEmitter, EventBus

# Strong-reference emitter (default)
emitter = EventEmitter()
emitter.on("source.synced", lambda event, **kw: print(kw))
emitter.emit("source.synced", source_id="logs")

# Weak-reference bus (handlers can be GC'd)
bus = EventBus()
bus.subscribe("goal.added", handler)
bus.publish("goal.added", goal_id="abc")
```

## Transport

```python
from sources_lib.transport import LocalTransport, make_http_transport

# Local JSON/CSV/SQLite
t = LocalTransport(max_rows=1000, max_bytes=10 * 1024 * 1024)
rows = t.read("/path/to/data.json")
t.write("sqlite:///mydb.sqlite", rows, table="events")

# HTTP JSON-POST (httpx if installed, stdlib fallback)
http = make_http_transport()
result = http.post_json("https://api.example.com/rpc", {"method": "ping"})
```
