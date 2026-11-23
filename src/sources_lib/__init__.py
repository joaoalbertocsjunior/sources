"""sources-lib — agnostic sources adapter, M2M interface, HTTP control."""
from .adapter import (
    SourceAdapter,
    SourceRecord,
    SourceError,
    SourceAuthError,
    SourceUnavailableError,
    SourceActDeniedError,
    BaseSourceAdapter,
)
from .registry import SourceRegistry
from .bridge import Bridge
from .events import EventEmitter, EventBus
from .schema import validate_schema, SchemaError
from .transport import Transport, LocalTransport, TransportError, HttpAdapter, HttpxTransport, StdlibHttpTransport, make_http_transport

__version__ = "0.1.0"

__all__ = [
    "SourceAdapter",
    "SourceRecord",
    "SourceError",
    "SourceAuthError",
    "SourceUnavailableError",
    "SourceActDeniedError",
    "BaseSourceAdapter",
    "SourceRegistry",
    "Bridge",
    "EventEmitter",
    "validate_schema",
    "SchemaError",
    "Transport",
    "LocalTransport",
    "TransportError",
    "EventBus",
    "HttpAdapter",
    "HttpxTransport",
    "StdlibHttpTransport",
    "make_http_transport",
]
