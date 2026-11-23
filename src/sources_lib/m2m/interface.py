"""JSON-RPC 2.0 M2M server and client. Stdlib only."""
from __future__ import annotations

import dataclasses
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib import request as _urllib_request

from ..schema import validate_schema, SchemaError


# ── Data models ───────────────────────────────────────────────────────────────

@dataclasses.dataclass
class JobModel:
    """A submitted M2M job (maps to a JSON-RPC call)."""
    id: str
    method: str
    params: dict[str, Any]
    submitted_at: float = dataclasses.field(default_factory=time.time)
    status: str = "pending"      # pending | running | done | error
    result: Any = None
    error: str = ""


@dataclasses.dataclass
class TaskResult:
    """Result returned by dispatch_fn for a completed job."""
    job_id: str
    status: str          # done | error
    result: Any = None
    error: str = ""


class RpcError(Exception):
    """JSON-RPC 2.0 error."""
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            err["data"] = self.data
        return err


# Standard JSON-RPC 2.0 error codes
PARSE_ERROR      = RpcError(-32700, "Parse error")
INVALID_REQUEST  = RpcError(-32600, "Invalid Request")
METHOD_NOT_FOUND = RpcError(-32601, "Method not found")
INVALID_PARAMS   = RpcError(-32602, "Invalid params")
INTERNAL_ERROR   = RpcError(-32603, "Internal error")


# ── Server ────────────────────────────────────────────────────────────────────

class M2MServer:
    """JSON-RPC 2.0 HTTP server.

    dispatch_fn: callable(method: str, params: dict) -> Any
                 Called for every inbound RPC call. Raise RpcError for errors.
                 If None, only built-in methods (ping, job.*) are available.

    auth_fn:     callable(token: str) -> bool
                 Return True if the bearer token is valid.
                 If None, all requests are admitted (use only for local/trusted nets).

    Usage::

        def handle(method, params):
            if method == "echo":
                return params
            raise RpcError(-32601, "Method not found")

        server = M2MServer(dispatch_fn=handle, auth_fn=lambda t: t == "secret")
        server.start(port=7000)
        # ... later ...
        server.stop()
    """

    def __init__(
        self,
        dispatch_fn: Callable[[str, dict[str, Any]], Any] | None = None,
        auth_fn: Callable[[str], bool] | None = None,
        registry=None,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._auth_fn = auth_fn
        self._registry = registry
        self._jobs: dict[str, JobModel] = {}
        self._jobs_lock = threading.Lock()
        self._methods: dict[str, tuple[Callable, dict | None]] = {}
        self._methods_lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None

    def start(self, host: str = "127.0.0.1", port: int = 7000) -> None:
        """Start the server in a background thread."""
        handler = self._make_handler()
        self._server = ThreadingHTTPServer((host, port), handler)
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    def handle(self, method: str, params: dict[str, Any]) -> Any:
        """Call directly (without HTTP) for testing or embedded use."""
        return self._dispatch(method, params)

    def register(
        self,
        method: str,
        handler: Callable[[dict[str, Any]], Any],
        params_schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a named RPC method with an optional JSON Schema for params validation."""
        with self._methods_lock:
            self._methods[method] = (handler, params_schema)

    # ── internals ─────────────────────────────────────────────────────────────

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        # Built-in methods
        if method == "ping":
            return {"pong": True, "at": time.time()}
        if method == "jobs.list":
            with self._jobs_lock:
                return [dataclasses.asdict(j) for j in self._jobs.values()]
        if method == "jobs.get":
            jid = params.get("id", "")
            with self._jobs_lock:
                job = self._jobs.get(jid)
            if not job:
                raise RpcError(-32602, f"Unknown job: {jid}")
            return dataclasses.asdict(job)
        if method == "jobs.submit":
            job = JobModel(
                id=uuid.uuid4().hex,
                method=params.get("method", ""),
                params=params.get("params", {}),
            )
            with self._jobs_lock:
                self._jobs[job.id] = job
            if self._dispatch_fn:
                threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
            return {"id": job.id, "status": job.status}
        if method == "rpc.listMethods":
            builtin = ["ping", "jobs.list", "jobs.get", "jobs.submit", "rpc.listMethods",
                       "sources.add", "sources.remove"]
            with self._methods_lock:
                registered = list(self._methods)
            return {"methods": builtin + registered}
        if method == "sources.add":
            if self._registry is None:
                raise RpcError(-32603, "No registry configured")
            kind = params.get("kind", "")
            sid = params.get("id")
            config = params.get("config", {})
            record = self._registry.add(kind, source_id=sid, config=config)
            return {"id": record.id, "kind": record.kind}
        if method == "sources.remove":
            if self._registry is None:
                raise RpcError(-32603, "No registry configured")
            sid = params.get("id", "")
            self._registry.remove(sid)
            return {"removed": sid}
        # Registered methods
        with self._methods_lock:
            entry = self._methods.get(method)
        if entry is not None:
            handler, schema = entry
            if schema:
                try:
                    validate_schema(params, schema)
                except SchemaError as exc:
                    raise RpcError(-32602, f"Invalid params: {exc}")
            return handler(params)
        # Delegate
        if self._dispatch_fn:
            return self._dispatch_fn(method, params)
        raise RpcError(-32601, f"Method not found: {method}")

    def _run_job(self, job: JobModel) -> None:
        with self._jobs_lock:
            job.status = "running"
        try:
            result = self._dispatch_fn(job.method, job.params)  # type: ignore[misc]
            with self._jobs_lock:
                job.result = result
                job.status = "done"
        except Exception as exc:
            with self._jobs_lock:
                job.error = str(exc)
                job.status = "error"

    def _make_handler(self) -> type:
        server_self = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                # Auth
                auth = self.headers.get("Authorization", "")
                token = auth.removeprefix("Bearer ").strip()
                if server_self._auth_fn and not server_self._auth_fn(token):
                    self._reply({"jsonrpc": "2.0", "error": {"code": -32001,
                                 "message": "Unauthorized"}, "id": None}, 401)
                    return
                # Parse body
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except Exception:
                    self._reply({"jsonrpc": "2.0",
                                 "error": PARSE_ERROR.to_dict(), "id": None})
                    return
                # Validate envelope
                if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
                    self._reply({"jsonrpc": "2.0",
                                 "error": INVALID_REQUEST.to_dict(), "id": None})
                    return
                rpc_id = body.get("id")
                method = body.get("method", "")
                params = body.get("params") or {}
                # Dispatch
                try:
                    result = server_self._dispatch(method, params)
                    self._reply({"jsonrpc": "2.0", "result": result, "id": rpc_id})
                except RpcError as exc:
                    self._reply({"jsonrpc": "2.0",
                                 "error": exc.to_dict(), "id": rpc_id})
                except Exception as exc:
                    self._reply({"jsonrpc": "2.0",
                                 "error": {"code": -32603, "message": str(exc)},
                                 "id": rpc_id})

            def _reply(self, data: dict, status: int = 200):
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass  # suppress default access log

        return _Handler


# ── Client ────────────────────────────────────────────────────────────────────

class M2MClient:
    """Minimal JSON-RPC 2.0 client. Stdlib only.

    Usage::

        client = M2MClient("http://127.0.0.1:7000", token="secret")
        result = client.call("echo", {"message": "hi"})
    """

    def __init__(self, base_url: str, token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Make a synchronous JSON-RPC 2.0 call. Raises RpcError on RPC-level errors."""
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": uuid.uuid4().hex,
        }).encode()
        req = _urllib_request.Request(
            self.base_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            method="POST",
        )
        with _urllib_request.urlopen(req, timeout=10) as resp:
            response = json.loads(resp.read())
        if "error" in response:
            err = response["error"]
            raise RpcError(err.get("code", -1), err.get("message", "unknown"))
        return response.get("result")
