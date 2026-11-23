from __future__ import annotations
import time
from typing import Any
from ..adapter import BaseSourceAdapter, SourceRecord, SourceUnavailableError


class DatabaseAdapter(BaseSourceAdapter):
    """Read rows from a SQLite database (or any DB-API 2.0 driver).

    For non-SQLite databases, provide a 'driver' key and ensure the driver
    package is installed (e.g. psycopg2 for PostgreSQL).
    """

    config_schema = {
        "type": "object",
        "required": ["connect"],
        "properties": {
            "connect": {"type": "string"},
            "query": {"type": "string"},
            "table": {"type": "string"},
            "limit": {"type": "integer"},
            "driver": {"type": "string"},
        },
    }
    actions = ["query"]

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        try:
            conn = self._connect(record)
            conn.close()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        return self._fetch(record, record.config.get("query"))

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "query":
            return {"rows": self._fetch(record, payload.get("query"))}
        raise __import__("sources_lib").SourceActDeniedError(f"Unsupported: {action}")

    def _connect(self, record: SourceRecord):
        driver = record.config.get("driver", "sqlite3")
        connect = record.config["connect"]
        if driver == "sqlite3":
            import sqlite3
            return sqlite3.connect(connect)
        mod = __import__(driver)
        return mod.connect(connect)

    def _fetch(self, record: SourceRecord, query: str | None) -> list[dict[str, Any]]:
        limit = record.config.get("limit", 1000)
        table = record.config.get("table", "data")
        q = query or f"SELECT * FROM {table} LIMIT {limit}"
        try:
            conn = self._connect(record)
            conn.row_factory = getattr(__import__("sqlite3"), "Row", None)
            cur = conn.execute(q)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()
            return [{**r, "observed_at": time.time()} for r in rows]
        except Exception as exc:
            raise SourceUnavailableError(str(exc)) from exc
