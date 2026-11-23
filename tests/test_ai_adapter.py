"""Tests for AIExecutorAdapter — all litellm calls are mocked."""
from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

from sources_lib.adapter import SourceRecord, SourceUnavailableError, SourceActDeniedError, SourceError
from sources_lib.adapters.ai import AIExecutorAdapter


def _record(config=None):
    return SourceRecord(id="ai-1", kind="ai", config=config or {})


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def test_verify_unavailable_without_litellm():
    adapter = AIExecutorAdapter()
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", False):
        with pytest.raises(SourceUnavailableError):
            adapter.verify(_record(), {})


def test_verify_success():
    adapter = AIExecutorAdapter(model="gpt-4o-mini")
    fake_response = MagicMock()
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True), \
         patch("sources_lib.adapters.ai._litellm") as mock_litellm:
        mock_litellm.completion.return_value = fake_response
        result = adapter.verify(_record(), {})
    assert result == {"reachable": True, "model": "gpt-4o-mini"}


def test_verify_raises_on_litellm_error():
    adapter = AIExecutorAdapter()
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True), \
         patch("sources_lib.adapters.ai._litellm") as mock_litellm:
        mock_litellm.completion.side_effect = RuntimeError("network error")
        with pytest.raises(SourceUnavailableError, match="network error"):
            adapter.verify(_record(), {})


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

def test_sync_no_prompt_returns_empty():
    adapter = AIExecutorAdapter()
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True):
        result = adapter.sync(_record(), {})
    assert result == []


def test_sync_no_prompt_with_no_default_returns_empty():
    adapter = AIExecutorAdapter(default_prompt="")
    record = _record(config={"prompt": ""})
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True):
        result = adapter.sync(record, {})
    assert result == []


def test_sync_calls_litellm():
    adapter = AIExecutorAdapter(model="gpt-4o-mini")
    record = _record(config={})

    fake_message = MagicMock()
    fake_message.content = "Hello, world!"
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True), \
         patch("sources_lib.adapters.ai._litellm") as mock_litellm:
        mock_litellm.completion.return_value = fake_response
        result = adapter.sync(record, {"prompt": "say hello"})

    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] == "Hello, world!"
    assert result[0]["model"] == "gpt-4o-mini"
    assert result[0]["source_id"] == "ai-1"


def test_sync_uses_record_config_prompt():
    adapter = AIExecutorAdapter(model="gpt-4o-mini")
    record = _record(config={"prompt": "from record"})

    fake_message = MagicMock()
    fake_message.content = "response"
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True), \
         patch("sources_lib.adapters.ai._litellm") as mock_litellm:
        mock_litellm.completion.return_value = fake_response
        result = adapter.sync(record, {})

    assert result[0]["content"] == "response"


def test_sync_raises_source_error_on_exception():
    adapter = AIExecutorAdapter()
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True), \
         patch("sources_lib.adapters.ai._litellm") as mock_litellm:
        mock_litellm.completion.side_effect = RuntimeError("boom")
        with pytest.raises(SourceError):
            adapter.sync(_record(), {"prompt": "hi"})


def test_sync_unavailable_without_litellm():
    adapter = AIExecutorAdapter()
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", False):
        with pytest.raises(SourceUnavailableError):
            adapter.sync(_record(), {"prompt": "hi"})


# ---------------------------------------------------------------------------
# act
# ---------------------------------------------------------------------------

def test_act_complete():
    adapter = AIExecutorAdapter(model="gpt-4o-mini")

    fake_message = MagicMock()
    fake_message.content = "completed text"
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True), \
         patch("sources_lib.adapters.ai._litellm") as mock_litellm:
        mock_litellm.completion.return_value = fake_response
        result = adapter.act(_record(), {}, "complete", {"prompt": "hi"})

    assert result["content"] == "completed text"
    assert result["model"] == "gpt-4o-mini"


def test_act_unsupported_action():
    adapter = AIExecutorAdapter()
    with pytest.raises(SourceActDeniedError):
        adapter.act(_record(), {}, "generate", {})


def test_act_complete_unavailable_without_litellm():
    adapter = AIExecutorAdapter()
    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", False):
        with pytest.raises(SourceUnavailableError):
            adapter.act(_record(), {}, "complete", {"prompt": "hi"})


def test_act_uses_messages_from_payload():
    adapter = AIExecutorAdapter(model="gpt-4o-mini")

    fake_message = MagicMock()
    fake_message.content = "result"
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    messages = [{"role": "user", "content": "custom message"}]

    with patch("sources_lib.adapters.ai._LITELLM_AVAILABLE", True), \
         patch("sources_lib.adapters.ai._litellm") as mock_litellm:
        mock_litellm.completion.return_value = fake_response
        result = adapter.act(_record(), {}, "complete", {"messages": messages})

    mock_litellm.completion.assert_called_once()
    call_kwargs = mock_litellm.completion.call_args
    assert call_kwargs.kwargs.get("messages") == messages or call_kwargs.args[1] == messages


# ---------------------------------------------------------------------------
# supported_actions
# ---------------------------------------------------------------------------

def test_supported_actions():
    adapter = AIExecutorAdapter()
    assert adapter.supported_actions(_record(), {}) == ["complete"]
