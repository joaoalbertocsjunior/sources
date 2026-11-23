"""Built-in generic source adapters."""
from .file import FileAdapter
from .shell import ShellAdapter
from .env import EnvAdapter
from .webhook import WebhookAdapter
from .database import DatabaseAdapter
from .http_poll import HttpPollAdapter

__all__ = [
    "FileAdapter",
    "ShellAdapter",
    "EnvAdapter",
    "WebhookAdapter",
    "DatabaseAdapter",
    "HttpPollAdapter",
]
