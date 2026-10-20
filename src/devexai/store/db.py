"""SQLite connection and schema. One short-lived connection per operation keeps it thread-safe."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    poster        TEXT NOT NULL,
    text          TEXT NOT NULL,
    channel       TEXT NOT NULL,
    thread_ref    TEXT,
    stage         TEXT NOT NULL,
    maintainer    TEXT,
    topic         TEXT,
    title         TEXT,
    gate_json     TEXT,
    plan_json     TEXT,
    blog_url      TEXT,
    stop_reason   TEXT,
    waiting_since TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER,
    at      TEXT NOT NULL,
    actor   TEXT NOT NULL,
    action  TEXT NOT NULL,
    detail  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS audit_idea ON audit(idea_id);
CREATE TABLE IF NOT EXISTS projects (
    name       TEXT PRIMARY KEY,
    summary    TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS people (
    name       TEXT PRIMARY KEY,
    email      TEXT UNIQUE,
    role       TEXT NOT NULL DEFAULT 'maintainer',
    topics     TEXT NOT NULL DEFAULT '[]',
    pw_hash    TEXT,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# Columns added after the first release: (table, column, definition).
_ADDED_COLUMNS = (("ideas", "live", "TEXT"),)


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, definition in _ADDED_COLUMNS:
        if column not in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # ":memory:" needs one shared connection; files get one per call.
        self._shared = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
        self._lock = threading.RLock()
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            _migrate(conn)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self._shared or sqlite3.connect(self.path, timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                if self._shared is None:
                    conn.close()
