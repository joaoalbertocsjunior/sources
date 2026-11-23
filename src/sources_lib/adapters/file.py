from __future__ import annotations
import hashlib, os, pathlib, time
from typing import Any
from ..adapter import BaseSourceAdapter, SourceRecord, SourceActDeniedError


class FileAdapter(BaseSourceAdapter):
    """Observe a local file or glob pattern for content changes."""

    config_schema = {
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string"},
            "encoding": {"type": "string"},
            "max_bytes": {"type": "integer"},
        },
    }
    actions = ["read"]

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        path = pathlib.Path(record.config["path"])
        return {"ok": path.exists(), "path": str(path)}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        path = pathlib.Path(record.config["path"])
        enc = record.config.get("encoding", "utf-8")
        max_bytes = record.config.get("max_bytes", 1 * 1024 * 1024)
        if not path.exists():
            return []
        stat = path.stat()
        content = path.read_bytes()[:max_bytes].decode(enc, errors="replace")
        digest = hashlib.sha256(content.encode()).hexdigest()[:16]
        return [{"path": str(path), "content": content,
                 "size": stat.st_size, "mtime": stat.st_mtime,
                 "digest": digest, "observed_at": time.time()}]

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "read":
            rows = self.sync(record, config)
            return rows[0] if rows else {}
        raise SourceActDeniedError(f"Unsupported action: {action}")
