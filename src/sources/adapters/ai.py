"""AI executor adapter — runs LLM inference as a source (requires sources-lib[ai])."""
from __future__ import annotations

from typing import Any

from ..adapter import BaseSourceAdapter, SourceRecord, SourceActDeniedError, SourceUnavailableError, SourceError

try:
    import litellm as _litellm
    _LITELLM_AVAILABLE = True
except ImportError:
    _litellm = None  # type: ignore[assignment]
    _LITELLM_AVAILABLE = False


class AIExecutorAdapter(BaseSourceAdapter):
    """Run LLM inference via litellm as a source."""

    config_schema: dict[str, Any] = {}
    actions = ["complete"]

    def __init__(self, model: str = "gpt-4o-mini", default_prompt: str = "") -> None:
        self.model = model
        self.default_prompt = default_prompt

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        if not _LITELLM_AVAILABLE:
            raise SourceUnavailableError("sources-lib[ai] required: pip install sources-lib[ai]")
        try:
            _litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return {"reachable": True, "model": self.model}
        except Exception as exc:
            raise SourceUnavailableError(str(exc)) from exc

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        if not _LITELLM_AVAILABLE:
            raise SourceUnavailableError("sources-lib[ai] required: pip install sources-lib[ai]")
        prompt = config.get("prompt") or record.config.get("prompt") or self.default_prompt
        if not prompt:
            return []
        try:
            response = _litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.get("max_tokens", 512),
            )
            return [
                {
                    "role": "assistant",
                    "content": response.choices[0].message.content,
                    "model": self.model,
                    "source_id": record.id,
                }
            ]
        except Exception as exc:
            raise SourceError(str(exc)) from exc

    def act(
        self,
        record: SourceRecord,
        config: dict[str, Any],
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if action != "complete":
            raise SourceActDeniedError(f"Unsupported action: {action}")
        if not _LITELLM_AVAILABLE:
            raise SourceUnavailableError("sources-lib[ai] required: pip install sources-lib[ai]")
        messages = payload.get("messages") or [{"role": "user", "content": payload.get("prompt", "")}]
        response = _litellm.completion(
            model=self.model,
            messages=messages,
            max_tokens=payload.get("max_tokens", 512),
        )
        return {"content": response.choices[0].message.content, "model": self.model}

    def supported_actions(self, record: SourceRecord, config: dict[str, Any]) -> list[str]:
        return ["complete"]
