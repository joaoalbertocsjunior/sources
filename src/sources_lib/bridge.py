"""Bridge — stateless source-to-source connector. Syncs A, acts on B."""
from __future__ import annotations

from typing import Any, Callable

from .adapter import SourceRecord
from .registry import SourceRegistry


class Bridge:
    """Sync source A and act on source B for each row.

    source_a:  source ID to sync from
    source_b:  source ID to act on
    action:    action name to call on source_b
    mapping:   optional callable(row) -> payload or dict of key renames.
               If None, each row dict is passed as the payload directly.
               If a dict, it renames keys: {new_key: old_key}.
    filter_fn: optional callable(row) -> bool — only pass rows where True.
    """

    def __init__(
        self,
        source_a: str,
        source_b: str,
        action: str,
        mapping: dict[str, str] | Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        filter_fn: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.source_a = source_a
        self.source_b = source_b
        self.action = action
        self.mapping = mapping
        self.filter_fn = filter_fn

    def run(self, registry: SourceRegistry,
            app_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run the bridge. Returns list of act() results."""
        rows = registry.sync(self.source_a, app_config=app_config)
        results = []
        for row in rows:
            if self.filter_fn is not None and not self.filter_fn(row):
                continue
            payload = self._map(row)
            result = registry.act(self.source_b, self.action, payload=payload,
                                  app_config=app_config)
            results.append(result)
        return results

    def _map(self, row: dict[str, Any]) -> dict[str, Any]:
        if self.mapping is None:
            return dict(row)
        if callable(self.mapping):
            return self.mapping(row)
        # dict mapping: {new_key: old_key}
        return {new: row[old] for new, old in self.mapping.items() if old in row}
