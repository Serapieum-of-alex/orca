from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from pydantic import TypeAdapter

from orca.core.events import Event
from orca.persistence.base import Persistence, RunRecord


DEFAULT_DB_DIR = Path(os.getenv("ORCA_DB_DIR", ".orca"))
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "orca.db"


class SQLitePersistence(Persistence):
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init(self) -> None:
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                node TEXT,
                type TEXT NOT NULL,
                time TEXT NOT NULL,
                data_json TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def create_run(self, run_id: str, metadata: Dict[str, Any]) -> None:
        self.init()
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO runs(run_id, status, metadata_json) VALUES (?, ?, ?)",
            (run_id, "running", json.dumps(metadata)),
        )
        self.conn.commit()

    def update_run_status(self, run_id: str, status: str) -> None:
        c = self.conn.cursor()
        c.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))
        self.conn.commit()

    def list_runs(self) -> Iterable[RunRecord]:
        c = self.conn.cursor()
        rows = c.execute("SELECT run_id, status FROM runs ORDER BY created_at DESC").fetchall()
        for r in rows:
            yield RunRecord(run_id=r["run_id"], status=r["status"])

    def save_checkpoint(self, run_id: str, node: str, state_json: str) -> None:
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO checkpoints(run_id, node, state_json) VALUES (?, ?, ?)",
            (run_id, node, state_json),
        )
        self.conn.commit()

    def load_latest_checkpoint(self, run_id: str) -> Optional[tuple[str, str]]:
        c = self.conn.cursor()
        row = c.execute(
            "SELECT node, state_json FROM checkpoints WHERE run_id = ? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if row:
            return row["node"], row["state_json"]  # type: ignore[return-value]
        return None

    def add_event(self, event: Event) -> None:
        c = self.conn.cursor()
        data_json = json.dumps(event.data)
        c.execute(
            "INSERT INTO events(run_id, node, type, time, data_json) VALUES (?, ?, ?, ?, ?)",
            (event.run_id, event.node, event.type, event.time.isoformat(), data_json),
        )
        self.conn.commit()

    def get_events(self, run_id: str) -> Iterable[Event]:
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT node, type, time, data_json FROM events WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        adapter = TypeAdapter(Event)
        for r in rows:
            yield adapter.validate_python(
                {
                    "run_id": run_id,
                    "node": r["node"],
                    "type": r["type"],
                    "time": r["time"],
                    "data": json.loads(r["data_json"]),
                }
            )


__all__ = ["SQLitePersistence", "DEFAULT_DB_PATH"]
