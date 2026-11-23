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


import weakref
import logging as _logging

_logger = _logging.getLogger(__name__)


def _make_ref(handler):
    """WeakMethod for bound methods, weakref.ref for plain functions."""
    try:
        return weakref.WeakMethod(handler)
    except TypeError:
        return weakref.ref(handler)


class EventBus:
    """Thread-safe synchronous publish/subscribe bus with weak-reference handlers.

    Unlike EventEmitter, handlers are stored as weak references — subscribers
    do not prevent garbage collection of their owning objects. Dead references
    are pruned lazily on each publish call.

    Usage::

        bus = EventBus()
        bus.subscribe("goal.added", handler)
        bus.publish("goal.added", goal_id="abc")
        bus.unsubscribe("goal.added", handler)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}
        self._lock = threading.Lock()

    def subscribe(self, event: str, handler: Callable[..., Any]) -> None:
        ref = _make_ref(handler)
        with self._lock:
            self._handlers.setdefault(event, []).append(ref)

    def unsubscribe(self, event: str, handler: Callable[..., Any]) -> None:
        with self._lock:
            bucket = self._handlers.get(event, [])
            self._handlers[event] = [r for r in bucket if r() is not None and r() != handler]

    def publish(self, event: str, **payload: Any) -> None:
        with self._lock:
            refs = list(self._handlers.get(event, []))
        dead = []
        for ref in refs:
            fn = ref()
            if fn is None:
                dead.append(ref)
                continue
            try:
                fn(**payload)
            except Exception:
                _logger.exception("EventBus handler raised for event %r", event)
        if dead:
            with self._lock:
                bucket = self._handlers.get(event, [])
                self._handlers[event] = [r for r in bucket if r not in dead]

    def _clear_all(self) -> None:
        with self._lock:
            self._handlers.clear()
