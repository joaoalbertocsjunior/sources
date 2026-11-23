"""A2A source adapter — remote A2A agents as sources. Stdlib only, no extra deps."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

from ..adapter import BaseSourceAdapter, SourceRecord, SourceActDeniedError, SourceError, SourceUnavailableError


class A2ASourceAdapter(BaseSourceAdapter):
    """Make remote A2A (Agent-to-Agent protocol 1.0) agents discoverable and callable as sources."""

    config_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "token": {"type": "string"},
        },
    }
    actions = ["send_message"]

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def _agent_card(self, url: str) -> dict:
        card_url = url.rstrip("/") + "/.well-known/agent-card.json"
        req = urllib.request.Request(card_url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            raise SourceUnavailableError(f"Cannot reach A2A agent at {url}: {e}")

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        url = record.config.get("url") or config.get("url")
        if not url:
            raise SourceUnavailableError("A2A agent url required in config")
        card = self._agent_card(url)
        return {
            "reachable": True,
            "url": url,
            "name": card.get("name", ""),
            "version": card.get("version", ""),
            "protocol": card.get("supportedInterfaces", [{}])[0].get("protocolVersion", ""),
        }

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        url = record.config.get("url") or config.get("url")
        if not url:
            raise SourceError("A2A agent url required")
        card = self._agent_card(url)
        skills = card.get("skills", [])
        if skills:
            return [
                {
                    "source_id": record.id,
                    "url": url,
                    "name": card.get("name", ""),
                    "skill_id": s.get("id", ""),
                    "skill_name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "tags": s.get("tags", []),
                }
                for s in skills
            ]
        return [
            {
                "source_id": record.id,
                "url": url,
                "name": card.get("name", ""),
                "skill_id": "",
                "skill_name": "",
                "description": card.get("description", ""),
                "tags": [],
            }
        ]

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action != "send_message":
            raise SourceActDeniedError(f"Unsupported action: {action}")
        url = record.config.get("url") or config.get("url")
        if not url:
            raise SourceActDeniedError("A2A agent url required")
        token = record.config.get("token") or config.get("token") or ""

        rpc_url = url.rstrip("/") + "/rpc"
        message_id = payload.get("message_id") or str(uuid.uuid4())
        command = payload.get("command", "")
        params = payload.get("params", {})
        body = json.dumps({
            "jsonrpc": "2.0", "id": message_id, "method": "SendMessage",
            "params": {
                "message": {
                    "messageId": message_id, "role": "ROLE_USER",
                    "parts": [{"data": {"command": command, "params": params}, "mediaType": "application/json"}]
                },
                "configuration": {"returnImmediately": True}
            }
        }).encode()

        headers = {"Content-Type": "application/json", "A2A-Version": "1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(rpc_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                response = json.loads(resp.read())
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            raise SourceError(str(e))

        return {
            "message_id": message_id,
            "result": response.get("result"),
            "error": response.get("error"),
        }

    def supported_actions(self, record: SourceRecord, config: dict[str, Any]) -> list[str]:
        return ["send_message"]
