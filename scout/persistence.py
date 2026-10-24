"""Tiny SQLite persistence layer for reproducible local audit records."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: str | Path = "scout.db"):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE IF NOT EXISTS records (
            kind TEXT NOT NULL, record_id TEXT NOT NULL, payload TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(kind, record_id))""")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
            actor TEXT NOT NULL, record_id TEXT, details TEXT NOT NULL, created_at TEXT NOT NULL)""")
        self.connection.commit()

    def put(self, kind: str, record_id: str, payload: dict[str, Any], *, action: str = "upsert",
            actor: str = "system") -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute("INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?)",
                               (kind, record_id, json.dumps(payload), now))
        self.audit(action, actor, record_id, payload)
        self.connection.commit()

    def get(self, kind: str, record_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT payload FROM records WHERE kind=? AND record_id=?",
                                      (kind, record_id)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list(self, kind: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute("SELECT payload FROM records WHERE kind=? ORDER BY updated_at DESC", (kind,))
        return tuple(json.loads(row["payload"]) for row in rows)

    def audit(self, action: str, actor: str, record_id: str | None, details: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO audit(action,actor,record_id,details,created_at) VALUES(?,?,?,?,?)",
                                (action, actor, record_id, json.dumps(details), datetime.now(timezone.utc).isoformat()))

    def audit_history(self, record_id: str | None = None) -> tuple[dict[str, Any], ...]:
        if record_id is None:
            rows = self.connection.execute("SELECT * FROM audit ORDER BY id DESC")
        else:
            rows = self.connection.execute("SELECT * FROM audit WHERE record_id=? ORDER BY id DESC", (record_id,))
        return tuple(dict(row) for row in rows)

    def close(self) -> None:
        self.connection.close()
