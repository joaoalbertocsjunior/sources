"""HTTPControlServer — stdlib HTTP server mirroring sources + M2M."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse, parse_qs

from ..registry import SourceRegistry
from ..m2m.interface import M2MServer, RpcError


class HTTPControlHandler(BaseHTTPRequestHandler):
    """Public base name for the HTTP control handler.

    The live handler used by :class:`HTTPControlServer` is a subclass of this
    created per-server instance so it can close over the server's state.
    """

    def log_message(self, *a):  # pragma: no cover
        pass


class HTTPControlServer:
    """HTTP control server exposing sources and M2M over a simple REST-ish API.

    Routes:
      GET  /health                        — liveness check
      GET  /sources                       — list sources
      GET  /sources/kinds                 — list registered kinds
      GET  /sources/{id}                  — get source record
      POST /sources/{id}/sync             — trigger sync, return rows
      POST /sources/{id}/verify           — verify connectivity
      POST /sources/{id}/act/{action}     — perform action
      POST /rpc                           — JSON-RPC 2.0 passthrough to M2MServer
      GET  /jobs                          — list jobs (via M2M)
      GET  /jobs/{id}                     — get job status (via M2M)

    auth_fn: callable(token: str) -> bool
             Checks the Bearer token on every request.
             If None, all requests are admitted.
    """

    def __init__(
        self,
        registry: SourceRegistry | None = None,
        m2m: M2MServer | None = None,
        auth_fn: Callable[[str], bool] | None = None,
    ) -> None:
        self.registry = registry or SourceRegistry()
        self.m2m = m2m
        self.auth_fn = auth_fn
        self._server: ThreadingHTTPServer | None = None

    def start(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        handler = self._make_handler()
        self._server = ThreadingHTTPServer((host, port), handler)
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    def _make_handler(self) -> type:
        ctrl = self

        class _BoundHandler(HTTPControlHandler):

            def do_GET(self):
                if not self._auth():
                    return
                path = urlparse(self.path).path.rstrip("/")

                if path == "/health":
                    self._json({"ok": True, "at": time.time()})

                elif path == "/sources":
                    records = ctrl.registry.list()
                    self._json([{"id": r.id, "kind": r.kind,
                                 "added_at": r.added_at} for r in records])

                elif path == "/sources/kinds":
                    self._json(ctrl.registry.kinds())

                elif path.startswith("/sources/") and not path.endswith("/sync") \
                        and not path.endswith("/verify"):
                    sid = path.split("/")[2]
                    try:
                        r = ctrl.registry.get(sid)
                        self._json({"id": r.id, "kind": r.kind,
                                    "config": r.config, "added_at": r.added_at})
                    except Exception as exc:
                        self._json({"error": str(exc)}, 404)

                elif path == "/jobs":
                    if ctrl.m2m is None:
                        self._json({"error": "M2M not configured"}, 503)
                        return
                    jobs = ctrl.m2m.handle("jobs.list", {})
                    self._json(jobs)

                elif path.startswith("/jobs/"):
                    jid = path.split("/")[2]
                    if ctrl.m2m is None:
                        self._json({"error": "M2M not configured"}, 503)
                        return
                    try:
                        job = ctrl.m2m.handle("jobs.get", {"id": jid})
                        self._json(job)
                    except RpcError as exc:
                        self._json({"error": exc.message}, 404)

                else:
                    self._json({"error": "Not found"}, 404)

            def do_POST(self):
                if not self._auth():
                    return
                path = urlparse(self.path).path.rstrip("/")
                body = self._read_body()

                if path == "/rpc":
                    if ctrl.m2m is None:
                        self._json({"error": "M2M not configured"}, 503)
                        return
                    method = body.get("method", "")
                    params = body.get("params") or {}
                    try:
                        result = ctrl.m2m.handle(method, params)
                        self._json({"jsonrpc": "2.0", "result": result, "id": body.get("id")})
                    except RpcError as exc:
                        self._json({"jsonrpc": "2.0", "error": exc.to_dict(),
                                    "id": body.get("id")})
                    except Exception as exc:
                        self._json({"jsonrpc": "2.0",
                                    "error": {"code": -32603, "message": str(exc)},
                                    "id": body.get("id")})

                elif path.endswith("/sync"):
                    sid = path.split("/")[2]
                    try:
                        rows = ctrl.registry.sync(sid)
                        self._json({"rows": rows, "count": len(rows)})
                    except Exception as exc:
                        self._json({"error": str(exc)}, 400)

                elif path.endswith("/verify"):
                    sid = path.split("/")[2]
                    try:
                        result = ctrl.registry.verify(sid)
                        self._json(result)
                    except Exception as exc:
                        self._json({"error": str(exc)}, 400)

                elif "/act/" in path:
                    parts = path.split("/")
                    # /sources/{id}/act/{action}
                    sid = parts[2]
                    action = parts[4] if len(parts) > 4 else ""
                    try:
                        result = ctrl.registry.act(sid, action, payload=body)
                        self._json(result)
                    except Exception as exc:
                        self._json({"error": str(exc)}, 400)

                elif path == "/sources":
                    # Register a new source: POST /sources {kind, id?, config}
                    kind = body.get("kind", "")
                    sid = body.get("id")
                    config = body.get("config", {})
                    try:
                        record = ctrl.registry.add(kind, source_id=sid, config=config)
                        self._json({"id": record.id, "kind": record.kind}, 201)
                    except Exception as exc:
                        self._json({"error": str(exc)}, 400)

                else:
                    self._json({"error": "Not found"}, 404)

            def _auth(self) -> bool:
                if ctrl.auth_fn is None:
                    return True
                auth = self.headers.get("Authorization", "")
                token = auth.removeprefix("Bearer ").strip()
                if not ctrl.auth_fn(token):
                    self._json({"error": "Unauthorized"}, 401)
                    return False
                return True

            def _read_body(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", 0))
                if length == 0:
                    return {}
                try:
                    return json.loads(self.rfile.read(length))
                except Exception:
                    return {}

            def _json(self, data: Any, status: int = 200) -> None:
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        return _BoundHandler
