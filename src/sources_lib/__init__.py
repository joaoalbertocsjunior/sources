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
from .events import EventEmitter
from .schema import validate_schema, SchemaError
from .transport import Transport, LocalTransport, TransportError

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
    "EventEmitter",
    "validate_schema",
    "SchemaError",
    "Transport",
    "LocalTransport",
    "TransportError",
]
