"""Tests for A2ASourceAdapter — all network calls are mocked."""
from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from sources_lib.adapters.a2a import A2ASourceAdapter
from sources_lib.adapter import SourceRecord, SourceUnavailableError, SourceError, SourceActDeniedError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(data: dict):
    m = MagicMock()
    m.read.return_value = json.dumps(data).encode()
    m.__enter__ = lambda s: s
    m.__exit__ = MagicMock(return_value=False)
    return m


def _record(config: dict | None = None) -> SourceRecord:
    return SourceRecord(id="test-src", kind="a2a", config=config or {})


AGENT_CARD = {
    "name": "TestAgent",
    "version": "1.0",
    "description": "A test agent",
    "supportedInterfaces": [{"protocolVersion": "1.0"}],
    "skills": [],
}

AGENT_CARD_WITH_SKILLS = {
    "name": "SkillAgent",
    "version": "2.0",
    "description": "Agent with skills",
    "supportedInterfaces": [{"protocolVersion": "1.0"}],
    "skills": [
        {"id": "s1", "name": "Skill One", "description": "Does one", "tags": ["foo"]},
        {"id": "s2", "name": "Skill Two", "description": "Does two", "tags": ["bar"]},
    ],
}


# ── verify ─────────────────────────────────────────────────────────────────────

def test_verify_success():
    adapter = A2ASourceAdapter()
    record = _record({"url": "http://agent.local"})

    with patch("urllib.request.urlopen", return_value=_mock_response(AGENT_CARD)):
        result = adapter.verify(record, {})

    assert result["reachable"] is True
    assert result["url"] == "http://agent.local"
    assert result["name"] == "TestAgent"
    assert result["version"] == "1.0"
    assert result["protocol"] == "1.0"


def test_verify_no_url_raises():
    adapter = A2ASourceAdapter()
    record = _record({})
    with pytest.raises(SourceUnavailableError):
        adapter.verify(record, {})


def test_verify_network_error():
    adapter = A2ASourceAdapter()
    record = _record({"url": "http://agent.local"})

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(SourceUnavailableError):
            adapter.verify(record, {})


# ── sync ───────────────────────────────────────────────────────────────────────

def test_sync_returns_skills():
    adapter = A2ASourceAdapter()
    record = _record({"url": "http://agent.local"})

    with patch("urllib.request.urlopen", return_value=_mock_response(AGENT_CARD_WITH_SKILLS)):
        rows = adapter.sync(record, {})

    assert len(rows) == 2
    assert rows[0]["skill_id"] == "s1"
    assert rows[0]["skill_name"] == "Skill One"
    assert rows[0]["source_id"] == "test-src"
    assert rows[1]["skill_id"] == "s2"
    assert rows[1]["tags"] == ["bar"]


def test_sync_no_skills_returns_one_row():
    adapter = A2ASourceAdapter()
    record = _record({"url": "http://agent.local"})

    with patch("urllib.request.urlopen", return_value=_mock_response(AGENT_CARD)):
        rows = adapter.sync(record, {})

    assert len(rows) == 1
    assert rows[0]["skill_id"] == ""
    assert rows[0]["description"] == "A test agent"
    assert rows[0]["source_id"] == "test-src"


# ── act ────────────────────────────────────────────────────────────────────────

def test_act_send_message():
    adapter = A2ASourceAdapter()
    record = _record({"url": "http://agent.local"})
    rpc_response = {"jsonrpc": "2.0", "id": "x", "result": {"task": {}}}

    with patch("urllib.request.urlopen", return_value=_mock_response(rpc_response)):
        result = adapter.act(record, {}, "send_message", {"command": "help"})

    assert "result" in result
    assert result["result"] == {"task": {}}
    assert result["error"] is None
    assert "message_id" in result


def test_act_unsupported_action():
    adapter = A2ASourceAdapter()
    record = _record({"url": "http://agent.local"})
    with pytest.raises(SourceActDeniedError):
        adapter.act(record, {}, "ping", {})


def test_act_no_url_raises():
    adapter = A2ASourceAdapter()
    record = _record({})
    with pytest.raises(SourceActDeniedError):
        adapter.act(record, {}, "send_message", {"command": "hi"})


# ── supported_actions ──────────────────────────────────────────────────────────

def test_supported_actions():
    adapter = A2ASourceAdapter()
    record = _record({"url": "http://agent.local"})
    assert adapter.supported_actions(record, {}) == ["send_message"]
