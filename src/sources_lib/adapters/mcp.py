"""MCP source adapter — exposes an MCP server's tools as a source (requires sources-lib[mcp])."""
from __future__ import annotations

import asyncio
from typing import Any

from ..adapter import BaseSourceAdapter, SourceRecord, SourceActDeniedError, SourceUnavailableError, SourceError

try:
    import mcp as _mcp
    _MCP_AVAILABLE = True
except ImportError:
    _mcp = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False


class MCPSourceAdapter(BaseSourceAdapter):
    """Expose an MCP server's tools as a source."""

    config_schema = {
        "type": "object",
        "required": ["url"],
        "properties": {
            "url": {"type": "string"},
            "timeout": {"type": "integer"},
        },
    }
    actions = ["call_tool"]

    def __init__(self) -> None:
        pass

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        if not _MCP_AVAILABLE:
            raise SourceUnavailableError("sources-lib[mcp] required: pip install sources-lib[mcp]")
        url = record.config.get("url") or config.get("url")
        if not url:
            raise SourceUnavailableError("MCP server url required in config")
        return {"reachable": True, "url": url}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        if not _MCP_AVAILABLE:
            raise SourceUnavailableError("sources-lib[mcp] required: pip install sources-lib[mcp]")
        url = record.config.get("url") or config.get("url")
        try:
            tools = asyncio.run(self._list_tools(url))
            return [
                {
                    "name": t.get("name", "unknown"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema") or t.get("inputSchema", {}),
                    "source_id": record.id,
                }
                for t in tools
            ]
        except Exception as exc:
            raise SourceError(str(exc)) from exc

    async def _list_tools(self, url: str) -> list[dict[str, Any]]:
        """List tools from MCP server via SDK."""
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [
                    {
                        "name": tool.name,
                        "description": getattr(tool, "description", ""),
                        "input_schema": getattr(tool, "inputSchema", {}),
                    }
                    for tool in result.tools
                ]

    def act(
        self,
        record: SourceRecord,
        config: dict[str, Any],
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if action != "call_tool":
            raise SourceActDeniedError(f"Unsupported action: {action}")
        if not _MCP_AVAILABLE:
            raise SourceUnavailableError("sources-lib[mcp] required: pip install sources-lib[mcp]")
        tool_name = payload.get("tool")
        if not tool_name:
            raise SourceActDeniedError("tool name required")
        tool_args = payload.get("arguments", {})
        url = record.config.get("url") or config.get("url")
        try:
            result = asyncio.run(self._call_tool(url, tool_name, tool_args))
            return {"tool": tool_name, "result": result}
        except (SourceActDeniedError, SourceUnavailableError):
            raise
        except Exception as exc:
            raise SourceError(str(exc)) from exc

    async def _call_tool(self, url: str, tool_name: str, tool_args: dict[str, Any]) -> Any:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, tool_args)
                return result

    def supported_actions(self, record: SourceRecord, config: dict[str, Any]) -> list[str]:
        return ["call_tool"]
