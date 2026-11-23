from __future__ import annotations
import os, time
from typing import Any
from ..adapter import BaseSourceAdapter, SourceRecord


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
