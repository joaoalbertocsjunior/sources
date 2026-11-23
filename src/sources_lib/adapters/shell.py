from __future__ import annotations
import shlex, subprocess, time
from typing import Any
from ..adapter import BaseSourceAdapter, SourceRecord, SourceActDeniedError, SourceUnavailableError


class ShellAdapter(BaseSourceAdapter):
    """Observe the stdout of a shell command."""

    config_schema = {
        "type": "object",
        "required": ["command"],
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer"},
            "shell": {"type": "boolean"},
        },
    }
    actions = ["run"]

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        cmd = record.config["command"].split()[0]
        import shutil
        found = shutil.which(cmd)
        return {"ok": found is not None, "command": cmd}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        return [self._run(record)]

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "run":
            return self._run(record)
        raise SourceActDeniedError(f"Unsupported action: {action}")

    def _run(self, record: SourceRecord) -> dict[str, Any]:
        cmd = record.config["command"]
        timeout = record.config.get("timeout", 30)
        use_shell = record.config.get("shell", False)
        args = cmd if use_shell else shlex.split(cmd)
        try:
            result = subprocess.run(args, capture_output=True, text=True,
                                    timeout=timeout, shell=use_shell)
            return {"stdout": result.stdout, "stderr": result.stderr,
                    "returncode": result.returncode, "observed_at": time.time()}
        except subprocess.TimeoutExpired as exc:
            raise SourceUnavailableError(f"Command timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise SourceUnavailableError(f"Command not found: {cmd}") from exc
