from __future__ import annotations
import json, time, urllib.request
from typing import Any
from ..adapter import BaseSourceAdapter, SourceRecord, SourceUnavailableError


class HttpPollAdapter(BaseSourceAdapter):
    """Poll an HTTP/HTTPS endpoint and capture the response body as a row."""

    config_schema = {
        "type": "object",
        "required": ["url"],
        "properties": {
            "url": {"type": "string"},
            "method": {"type": "string"},
            "headers": {"type": "object"},
            "timeout": {"type": "integer"},
            "json_path": {"type": "string"},
        },
    }
    actions = ["fetch"]

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self._fetch(record)
            return {"ok": result["status"] < 400, "status": result["status"]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        return [self._fetch(record)]

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "fetch":
            return self._fetch(record)
        raise __import__("sources_lib").SourceActDeniedError(f"Unsupported: {action}")

    def _fetch(self, record: SourceRecord) -> dict[str, Any]:
        url = record.config["url"]
        timeout = record.config.get("timeout", 10)
        headers = record.config.get("headers", {})
        req = urllib.request.Request(url, method=record.config.get("method", "GET"),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode(errors="replace")
                status = resp.status
        except Exception as exc:
            raise SourceUnavailableError(str(exc)) from exc
        try:
            data = json.loads(body)
        except Exception:
            data = body
        return {"url": url, "status": status, "body": data, "observed_at": time.time()}
