"""Directory adapter — list direct children of a local directory as metadata rows."""
from __future__ import annotations

import pathlib
from typing import Any

from ..adapter import BaseSourceAdapter, SourceRecord, SourceError, SourceUnavailableError, SourceActDeniedError


class DirectoryAdapter(BaseSourceAdapter):
    """List direct children of a local directory as metadata rows."""

    config_schema = {
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string"},
            "skip_hidden": {"type": "boolean"},
            "max_files": {"type": "integer"},
        },
    }
    actions = ["list"]

    def __init__(self, max_files: int = 1000) -> None:
        self.max_files = max_files

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        path_str = record.config.get("path") or config.get("path")
        if not path_str:
            raise SourceUnavailableError("directory path required in config")
        path = pathlib.Path(path_str)
        if path.is_symlink():
            raise SourceUnavailableError("symlink directory targets are not supported")
        if not path.exists():
            raise SourceUnavailableError(f"directory does not exist: {path}")
        if not path.is_dir():
            raise SourceUnavailableError(f"path is not a directory: {path}")
        return {"reachable": True, "path": str(path.resolve()), "is_dir": True}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        path_str = record.config.get("path") or config.get("path")
        if not path_str:
            raise SourceError("directory path required")
        path = pathlib.Path(path_str)
        if path.is_symlink():
            raise SourceError("symlink directory targets are not supported")
        if not path.is_dir():
            raise SourceError(f"not a directory: {path}")
        skip_hidden = record.config.get("skip_hidden", config.get("skip_hidden", False))
        max_files = int(record.config.get("max_files", config.get("max_files", self.max_files)))
        # Never exceed instance cap
        max_files = min(max_files, self.max_files)
        rows = []
        for entry in path.iterdir():
            if len(rows) >= max_files:
                break
            # Skip symlinks silently
            if entry.is_symlink():
                continue
            # Skip hidden entries if requested
            if skip_hidden and entry.name.startswith("."):
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            rows.append({
                "name": entry.name,
                "path": str(entry.resolve()),
                "kind": "dir" if entry.is_dir() else "file",
                "size": st.st_size if entry.is_file() else 0,
                "mtime": st.st_mtime,
                "source_id": record.id,
            })
        rows.sort(key=lambda r: r["name"])
        return rows[:max_files]

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action != "list":
            raise SourceActDeniedError(f"Unsupported action: {action}")
        rows = self.sync(record, config)
        return {"rows": rows, "count": len(rows)}

    def supported_actions(self, record: SourceRecord, config: dict[str, Any]) -> list[str]:
        return ["list"]
