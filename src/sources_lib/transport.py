"""Transport protocol and LocalTransport implementation.

Transport is the data I/O layer: read rows from a source, write rows to a sink.
LocalTransport handles JSON files, CSV files, and SQLite databases.
"""
from __future__ import annotations

import csv
import io
import json
import os
import pathlib
import shutil
import sqlite3
import tempfile
import uuid
from typing import Any, Protocol, runtime_checkable


class TransportError(Exception):
    """Data transport failure."""


@runtime_checkable
class Transport(Protocol):
    """Contract for a data transport backend."""

    def read(self, connect: str, table: str | None = None,
             limit: int | None = None) -> list[dict[str, Any]]:
        """Read rows from *connect* (DSN or path)."""
        ...

    def write(self, connect: str, rows: list[dict[str, Any]],
              table: str | None = None) -> int:
        """Append *rows* to *connect*. Returns number of rows written."""
        ...

    def verify(self, connect: str) -> bool:
        """Return True if *connect* is reachable/readable."""
        ...


class LocalTransport:
    """Transport for local JSON, CSV, and SQLite files.

    connect format:
      - JSON file:   /path/to/file.json  or  file:///path/to/file.json
      - CSV file:    /path/to/file.csv
      - SQLite:      sqlite:///path/to/db.sqlite
    """

    def __init__(self, max_rows: int = 100_000, max_bytes: int = 50 * 1024 * 1024) -> None:
        self.max_rows = max_rows
        self.max_bytes = max_bytes

    def read(self, connect: str, table: str | None = None,
             limit: int | None = None) -> list[dict[str, Any]]:
        path, fmt = self._resolve(connect)
        if fmt == "json":
            return self._read_json(path, limit)
        if fmt == "csv":
            return self._read_csv(path, limit)
        if fmt == "sqlite":
            return self._read_sqlite(path, table, limit)
        raise TransportError(f"Unsupported format for: {connect}")

    def write(self, connect: str, rows: list[dict[str, Any]],
              table: str | None = None) -> int:
        if not rows:
            return 0
        path, fmt = self._resolve(connect)
        if fmt == "csv":
            return self._write_csv(path, rows)
        if fmt == "sqlite":
            return self._write_sqlite(path, rows, table or "data")
        raise TransportError(f"write not supported for format: {fmt}")

    def verify(self, connect: str) -> bool:
        try:
            path, fmt = self._resolve(connect)
            if fmt == "sqlite":
                conn = sqlite3.connect(str(path))
                conn.close()
                return True
            return pathlib.Path(path).exists()
        except Exception:
            return False

    # ── internals ─────────────────────────────────────────────────────────────

    def _resolve(self, connect: str) -> tuple[str, str]:
        if connect.startswith("sqlite:///"):
            return connect[len("sqlite:///"):], "sqlite"
        if connect.startswith("file:///"):
            path = connect[len("file:///"):]
        else:
            path = connect
        if path.endswith(".csv"):
            return path, "csv"
        return path, "json"

    def _read_json(self, path: str, limit: int | None) -> list[dict[str, Any]]:
        try:
            raw = pathlib.Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        data = json.loads(raw)
        rows = data if isinstance(data, list) else [data]
        return rows[:limit] if limit else rows[:self.max_rows]

    def _read_csv(self, path: str, limit: int | None) -> list[dict[str, Any]]:
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        cap = limit or self.max_rows
        for row in reader:
            rows.append(dict(row))
            if len(rows) >= cap:
                break
        return rows

    def _read_sqlite(self, path: str, table: str | None, limit: int | None) -> list[dict[str, Any]]:
        if not pathlib.Path(path).exists():
            return []
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            tbl = self._safe_table(table or "data")
            cap = limit or self.max_rows
            cur = conn.execute(f"SELECT * FROM {tbl} LIMIT ?", (cap,))
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def _write_csv(self, path: str, rows: list[dict[str, Any]]) -> int:
        p = pathlib.Path(path)
        exists = p.exists()
        fieldnames = list(rows[0].keys())
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                         dir=p.parent, delete=False, suffix=".tmp") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            else:
                # append mode: re-read existing, write all
                existing = self._read_csv(path, None)
                writer.writeheader()
                writer.writerows(existing)
            writer.writerows(rows)
            tmp = f.name
        shutil.move(tmp, path)
        return len(rows)

    def _write_sqlite(self, path: str, rows: list[dict[str, Any]], table: str) -> int:
        tbl = self._safe_table(table)
        conn = sqlite3.connect(path)
        try:
            cols = list(rows[0].keys())
            col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
            conn.execute(f'CREATE TABLE IF NOT EXISTS "{tbl}" ({col_defs})')
            placeholders = ", ".join("?" for _ in cols)
            conn.executemany(
                f'INSERT INTO "{tbl}" VALUES ({placeholders})',
                [[str(r.get(c, "")) for c in cols] for r in rows],
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    @staticmethod
    def _safe_table(name: str) -> str:
        import re
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        return safe or "data"
