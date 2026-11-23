from __future__ import annotations
import os, time
from typing import Any
from ..adapter import BaseSourceAdapter, SourceRecord, SourceActDeniedError


class EnvAdapter(BaseSourceAdapter):
    """Observe environment variables by prefix or explicit list."""

    config_schema = {
        "type": "object",
        "properties": {
            "prefix": {"type": "string"},
            "keys": {"type": "array", "items": {"type": "string"}},
            "redact": {"type": "array", "items": {"type": "string"}},
        },
    }
    actions = ["snapshot"]

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        keys = record.config.get("keys", [])
        prefix = record.config.get("prefix", "")
        if keys:
            missing = [k for k in keys if k not in os.environ]
            return {"ok": len(missing) == 0, "missing": missing}
        if prefix:
            found = any(k.startswith(prefix) for k in os.environ)
            return {"ok": found}
        return {"ok": True}

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "snapshot":
            rows = self.sync(record, config)
            return {"rows": rows, "count": len(rows)}
        raise SourceActDeniedError(f"Unsupported: {action}")

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        prefix = record.config.get("prefix", "")
        keys = record.config.get("keys", [])
        redact = set(record.config.get("redact", []))
        if keys:
            pairs = {k: os.environ.get(k, "") for k in keys}
        elif prefix:
            pairs = {k: v for k, v in os.environ.items() if k.startswith(prefix)}
        else:
            pairs = dict(os.environ)
        rows = []
        for k, v in pairs.items():
            rows.append({"key": k, "value": "***" if k in redact else v,
                         "observed_at": time.time()})
        return rows
