"""Built-in generic source adapters."""
from .file import FileAdapter
from .shell import ShellAdapter
from .env import EnvAdapter
from .webhook import WebhookAdapter
from .database import DatabaseAdapter
from .http_poll import HttpPollAdapter
from .a2a import A2ASourceAdapter
from .directory import DirectoryAdapter

__all__ = [
    "FileAdapter",
    "ShellAdapter",
    "EnvAdapter",
    "WebhookAdapter",
    "DatabaseAdapter",
    "HttpPollAdapter",
    "A2ASourceAdapter",
    "DirectoryAdapter",
]

try:
    from .ai import AIExecutorAdapter
    __all__ += ["AIExecutorAdapter"]
except ImportError:
    pass

try:
    from .mcp import MCPSourceAdapter
    __all__ += ["MCPSourceAdapter"]
except ImportError:
    pass
