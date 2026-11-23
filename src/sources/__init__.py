"""sources-lib — agnostic sources adapter, JSON-schema M2M interface, HTTP control."""
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
from .adapters import (
    FileAdapter, ShellAdapter, EnvAdapter,
    WebhookAdapter, DatabaseAdapter, HttpPollAdapter,
)
from .m2m import M2MServer, M2MClient, RpcError, JobModel, TaskResult
from .http import HTTPControlServer

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
    "FileAdapter",
    "ShellAdapter",
    "EnvAdapter",
    "WebhookAdapter",
    "DatabaseAdapter",
    "HttpPollAdapter",
    "M2MServer",
    "M2MClient",
    "RpcError",
    "JobModel",
    "TaskResult",
    "HTTPControlServer",
]

__version__ = "0.1.0"
