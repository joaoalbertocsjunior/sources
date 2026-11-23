"""SourceRegistry — manages adapter kinds and source record instances."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from .adapter import BaseSourceAdapter, SourceAdapter, SourceError, SourceRecord
from .schema import SchemaError, validate_schema


class RegistryError(SourceError):
    """Registry-level error (duplicate kind, unknown kind, etc.)."""


class SourceRegistry:
    """Thread-safe registry of adapter kinds and live source records.

    Usage::

        registry = SourceRegistry()
        registry.register_kind("file", FileAdapter())
        record = registry.add("file", source_id="logs", config={"path": "/var/log/app.log"})
        rows = registry.sync(record.id, app_config={})
    """

    def __init__(self) -> None:
        self._kinds: dict[str, SourceAdapter] = {}
        self._records: dict[str, SourceRecord] = {}
        self._lock = threading.Lock()

    # ── Kind management ───────────────────────────────────────────────────────

    def register_kind(self, kind: str, adapter: SourceAdapter) -> None:
        """Register an adapter for *kind*. Raises RegistryError if already registered."""
        with self._lock:
            if kind in self._kinds:
                raise RegistryError(f"Kind '{kind}' is already registered")
            self._kinds[kind] = adapter

    def unregister_kind(self, kind: str) -> None:
        with self._lock:
            self._kinds.pop(kind, None)

    def kinds(self) -> list[str]:
        with self._lock:
            return list(self._kinds)

    def adapter(self, kind: str) -> SourceAdapter:
        with self._lock:
            if kind not in self._kinds:
                raise RegistryError(f"Unknown kind '{kind}'")
            return self._kinds[kind]

    # ── Source record management ───────────────────────────────────────────────

    def add(self, kind: str, source_id: str | None = None,
            config: dict[str, Any] | None = None) -> SourceRecord:
        """Register a new source instance. Validates config against adapter schema."""
        config = config or {}
        with self._lock:
            if kind not in self._kinds:
                raise RegistryError(f"Unknown kind '{kind}'")
            adapter = self._kinds[kind]
            if adapter.config_schema:
                try:
                    validate_schema(config, adapter.config_schema)
                except SchemaError as exc:
                    raise RegistryError(f"Invalid config for kind '{kind}': {exc}") from exc
            sid = source_id or uuid.uuid4().hex[:12]
            if sid in self._records:
                raise RegistryError(f"Source id '{sid}' already registered")
            record = SourceRecord(id=sid, kind=kind, config=config, added_at=time.time())
            self._records[sid] = record
            return record

    def remove(self, source_id: str) -> None:
        with self._lock:
            self._records.pop(source_id, None)

    def get(self, source_id: str) -> SourceRecord:
        with self._lock:
            if source_id not in self._records:
                raise RegistryError(f"Unknown source '{source_id}'")
            return self._records[source_id]

    def list(self) -> list[SourceRecord]:
        with self._lock:
            return list(self._records.values())

    # ── Operations ────────────────────────────────────────────────────────────

    def verify(self, source_id: str, app_config: dict[str, Any] | None = None) -> dict[str, Any]:
        record = self.get(source_id)
        return self.adapter(record.kind).verify(record, app_config or {})

    def sync(self, source_id: str, app_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        record = self.get(source_id)
        return self.adapter(record.kind).sync(record, app_config or {})

    def act(self, source_id: str, action: str,
            payload: dict[str, Any] | None = None,
            app_config: dict[str, Any] | None = None) -> dict[str, Any]:
        record = self.get(source_id)
        return self.adapter(record.kind).act(record, app_config or {}, action, payload or {})
