"""SourceAdapter protocol and base implementation."""
from __future__ import annotations

import dataclasses
import time
from typing import Any, Protocol, runtime_checkable


# ── Exceptions ────────────────────────────────────────────────────────────────

class SourceError(Exception):
    """Base exception for all source errors."""

class SourceAuthError(SourceError):
    """Authentication or permission failure."""

class SourceUnavailableError(SourceError):
    """Source is temporarily unavailable."""

class SourceActDeniedError(SourceError):
    """Requested action is not permitted on this source."""


# ── Data model ────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class SourceRecord:
    """Runtime record for a registered source instance.

    id:       unique identifier within the registry
    kind:     adapter kind string (matches SourceRegistry key)
    config:   adapter-specific configuration dict (validated against adapter.config_schema)
    state:    mutable runtime state dict managed by the adapter
    added_at: unix timestamp when first registered
    """
    id: str
    kind: str
    config: dict[str, Any]
    state: dict[str, Any] = dataclasses.field(default_factory=dict)
    added_at: float = dataclasses.field(default_factory=time.time)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


# ── Protocol ──────────────────────────────────────────────────────────────────

@runtime_checkable
class SourceAdapter(Protocol):
    """Contract every source adapter must satisfy.

    Adapters are stateless objects — all runtime state lives in SourceRecord.state.
    Each method receives the full record and a config dict (top-level app config,
    not the source-specific config — use record.config for that).

    config_schema: JSON Schema dict describing valid record.config contents.
                   Empty dict means no validation enforced.
    actions:       list of action names this adapter supports via act().
                   Empty list means no actions.
    """

    config_schema: dict[str, Any]
    actions: list[str]

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        """Check source connectivity. Return status dict with at least {'ok': bool}."""
        ...

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Observe the source and return a list of row dicts."""
        ...

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Perform a named action on the source. Raise SourceActDeniedError if not supported."""
        ...


# ── Base implementation ───────────────────────────────────────────────────────

class BaseSourceAdapter:
    """Convenience base class. Override only the methods you need."""

    config_schema: dict[str, Any] = {}
    actions: list[str] = []

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action not in self.actions:
            raise SourceActDeniedError(f"Action '{action}' not supported by {type(self).__name__}")
        return {}
