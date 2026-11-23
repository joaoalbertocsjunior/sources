from __future__ import annotations
import json, threading, time
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from ..adapter import BaseSourceAdapter, SourceRecord


class WebhookAdapter(BaseSourceAdapter):
    """Receive incoming HTTP POST payloads as source rows.

    Starts an in-process HTTP listener on first sync().
    Rows accumulate in a bounded deque; sync() drains and returns them.
    """

    config_schema = {
        "type": "object",
        "properties": {
            "port": {"type": "integer"},
            "path": {"type": "string"},
            "max_queue": {"type": "integer"},
            "secret": {"type": "string"},
        },
    }

    def __init__(self) -> None:
        self._servers: dict[str, HTTPServer] = {}
        self._queues: dict[str, deque] = {}
        self._lock = threading.Lock()

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        port = record.config.get("port", 9100)
        return {"ok": True, "port": port,
                "note": "listener starts on first sync()"}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        self._ensure_listener(record)
        with self._lock:
            q = self._queues.get(record.id, deque())
            rows = list(q)
            q.clear()
        return rows

    def _ensure_listener(self, record: SourceRecord) -> None:
        with self._lock:
            if record.id in self._servers:
                return
            port = record.config.get("port", 9100)
            path = record.config.get("path", "/webhook")
            max_q = record.config.get("max_queue", 500)
            q: deque = deque(maxlen=max_q)
            self._queues[record.id] = q

            class _Handler(BaseHTTPRequestHandler):
                def do_POST(self):
                    if self.path != path:
                        self.send_response(404); self.end_headers(); return
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length)
                    try:
                        payload = json.loads(body)
                    except Exception:
                        payload = {"raw": body.decode(errors="replace")}
                    q.append({"payload": payload, "received_at": time.time()})
                    self.send_response(200); self.end_headers()
                def log_message(self, *a): pass

            server = HTTPServer(("127.0.0.1", port), _Handler)
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            self._servers[record.id] = server
