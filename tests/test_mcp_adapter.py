"""Tests for MCPSourceAdapter — mcp SDK calls are mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sources.adapter import SourceRecord, SourceUnavailableError, SourceActDeniedError, SourceError
from sources.adapters.mcp import MCPSourceAdapter


def _record(config=None):
    return SourceRecord(id="mcp-1", kind="mcp", config=config or {})


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def test_verify_unavailable_without_mcp():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", False):
        with pytest.raises(SourceUnavailableError):
            adapter.verify(_record(), {})


def test_verify_no_url_raises():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", True):
        with pytest.raises(SourceUnavailableError, match="url"):
            adapter.verify(_record(config={}), {})


def test_verify_url_from_record_config():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", True):
        result = adapter.verify(_record(config={"url": "http://localhost:8000"}), {})
    assert result == {"reachable": True, "url": "http://localhost:8000"}


def test_verify_url_from_top_config():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", True):
        result = adapter.verify(_record(), {"url": "http://localhost:9000"})
    assert result == {"reachable": True, "url": "http://localhost:9000"}


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

def test_sync_unavailable_without_mcp():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", False):
        with pytest.raises(SourceUnavailableError):
            adapter.sync(_record(config={"url": "http://localhost:8000"}), {})


def test_sync_raises_source_error_on_failure():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", True), \
         patch.object(adapter, "_list_tools", side_effect=RuntimeError("conn refused")):
        import asyncio

        async def _raise():
            raise RuntimeError("conn refused")

        with patch("sources.adapters.mcp.asyncio") as mock_asyncio:
            mock_asyncio.run.side_effect = RuntimeError("conn refused")
            with pytest.raises(SourceError):
                adapter.sync(_record(config={"url": "http://localhost:8000"}), {})


# ---------------------------------------------------------------------------
# act
# ---------------------------------------------------------------------------

def test_act_unsupported_action():
    adapter = MCPSourceAdapter()
    with pytest.raises(SourceActDeniedError):
        adapter.act(_record(), {}, "ping", {})


def test_act_no_tool_name():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", True):
        with pytest.raises(SourceActDeniedError, match="tool name required"):
            adapter.act(_record(config={"url": "http://localhost:8000"}), {}, "call_tool", {})


def test_act_unavailable_without_mcp():
    adapter = MCPSourceAdapter()
    with patch("sources.adapters.mcp._MCP_AVAILABLE", False):
        with pytest.raises(SourceUnavailableError):
            adapter.act(_record(), {}, "call_tool", {"tool": "my_tool"})


def test_act_call_tool_success():
    adapter = MCPSourceAdapter()

    with patch("sources.adapters.mcp._MCP_AVAILABLE", True), \
         patch("sources.adapters.mcp.asyncio") as mock_asyncio:
        mock_asyncio.run.return_value = {"output": "tool result"}
        result = adapter.act(
            _record(config={"url": "http://localhost:8000"}),
            {},
            "call_tool",
            {"tool": "my_tool", "arguments": {"key": "value"}},
        )

    assert result["tool"] == "my_tool"
    assert result["result"] == {"output": "tool result"}


def test_act_call_tool_raises_source_error_on_failure():
    adapter = MCPSourceAdapter()

    with patch("sources.adapters.mcp._MCP_AVAILABLE", True), \
         patch("sources.adapters.mcp.asyncio") as mock_asyncio:
        mock_asyncio.run.side_effect = RuntimeError("tool failed")
        with pytest.raises(SourceError):
            adapter.act(
                _record(config={"url": "http://localhost:8000"}),
                {},
                "call_tool",
                {"tool": "my_tool"},
            )


# ---------------------------------------------------------------------------
# supported_actions
# ---------------------------------------------------------------------------

def test_supported_actions():
    adapter = MCPSourceAdapter()
    assert adapter.supported_actions(_record(), {}) == ["call_tool"]
