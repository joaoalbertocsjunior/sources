"""EventEmitter — simple callback-based event system. No singletons."""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable


class EventEmitter:
    """Thread-safe event emitter.

    Usage::

        emitter = EventEmitter()
        emitter.on("source.synced", lambda event, **kw: print(event, kw))
        emitter.emit("source.synced", source_id="logs", row_count=42)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event: str, handler: Callable[..., Any]) -> None:
        with self._lock:
            self._handlers[event].append(handler)

    def off(self, event: str, handler: Callable[..., Any]) -> None:
        with self._lock:
            handlers = self._handlers.get(event, [])
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    def emit(self, event: str, **kwargs: Any) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        for handler in handlers:
            try:
                handler(event, **kwargs)
            except Exception:
                pass  # handlers must not crash the emitter

    def events(self) -> list[str]:
        with self._lock:
            return [e for e, h in self._handlers.items() if h]
