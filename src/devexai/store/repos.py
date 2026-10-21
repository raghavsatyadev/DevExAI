"""Read/write access to ideas, the audit log, project summaries and small bot state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..stages import WAITING_ON_MAINTAINER, InvalidTransition, Stage, check_move
from .db import Database, now


@dataclass
class Idea:
    id: int
    poster: str
    text: str
    channel: str
    thread_ref: str | None
    stage: Stage
    maintainer: str | None
    topic: str | None
    title: str | None
    gate: dict[str, Any] | None
    plan: dict[str, Any] | None
    blog_url: str | None
    live: str | None  # poster chose to build it live in public: "yes", "no", or not answered
    stop_reason: str | None
    waiting_since: str | None
    created_at: str
    updated_at: str

    @property
    def label(self) -> str:
        return f"#{self.id}" + (f" {self.title}" if self.title else "")


def _row_to_idea(row) -> Idea:
    return Idea(
        id=row["id"], poster=row["poster"], text=row["text"], channel=row["channel"],
        thread_ref=row["thread_ref"], stage=Stage(row["stage"]), maintainer=row["maintainer"],
        topic=row["topic"], title=row["title"],
        gate=json.loads(row["gate_json"]) if row["gate_json"] else None,
        plan=json.loads(row["plan_json"]) if row["plan_json"] else None,
        blog_url=row["blog_url"], live=row["live"], stop_reason=row["stop_reason"],
        waiting_since=row["waiting_since"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


_UPDATABLE = {"thread_ref", "maintainer", "topic", "title", "gate", "plan", "blog_url", "live", "stop_reason"}


class IdeaRepo:
    def __init__(self, db: Database):
        self.db = db

    def create(self, poster: str, text: str, channel: str) -> Idea:
        ts = now()
        with self.db.connect() as c:
            cur = c.execute(
                "INSERT INTO ideas (poster, text, channel, stage, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (poster, text, channel, Stage.RECEIVED.value, ts, ts),
            )
            idea_id = cur.lastrowid
        return self.get(idea_id)

    def get(self, idea_id: int) -> Idea:
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        if row is None:
            raise KeyError(f"no idea #{idea_id}")
        return _row_to_idea(row)

    def delete(self, idea_id: int) -> None:
        """Remove the idea and its history. The caller records the deletion itself."""
        with self.db.connect() as c:
            c.execute("DELETE FROM audit WHERE idea_id = ?", (idea_id,))
            c.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))

    def find_by_thread(self, thread_ref: str) -> Idea | None:
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM ideas WHERE thread_ref = ?", (thread_ref,)).fetchone()
        return _row_to_idea(row) if row else None

    def list(self, limit: int = 50) -> list[Idea]:
        with self.db.connect() as c:
            rows = c.execute("SELECT * FROM ideas ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_idea(r) for r in rows]

    def waiting_on_maintainer(self) -> list[Idea]:
        marks = ",".join("?" for _ in WAITING_ON_MAINTAINER)
        with self.db.connect() as c:
            rows = c.execute(
                f"SELECT * FROM ideas WHERE stage IN ({marks})", [s.value for s in WAITING_ON_MAINTAINER]
            ).fetchall()
        return [_row_to_idea(r) for r in rows]

    def update(self, idea_id: int, **fields: Any) -> Idea:
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"cannot update {sorted(unknown)}")
        cols, vals = [], []
        for key, value in fields.items():
            if key in ("gate", "plan"):
                key, value = f"{key}_json", None if value is None else json.dumps(value)
            cols.append(f"{key} = ?")
            vals.append(value)
        cols.append("updated_at = ?")
        vals.append(now())
        with self.db.connect() as c:
            c.execute(f"UPDATE ideas SET {', '.join(cols)} WHERE id = ?", (*vals, idea_id))
        return self.get(idea_id)

    def move(self, idea_id: int, dst: Stage, *, expect: Stage | None = None) -> Idea:
        """Move to a new stage, validated against the state machine and done atomically."""
        with self.db.connect() as c:
            row = c.execute("SELECT stage FROM ideas WHERE id = ?", (idea_id,)).fetchone()
            if row is None:
                raise KeyError(f"no idea #{idea_id}")
            src = Stage(row["stage"])
            if expect is not None and src is not expect:
                raise InvalidTransition(f"idea #{idea_id} is {src}, expected {expect}")
            check_move(src, dst)
            ts = now()
            waiting = ts if dst in WAITING_ON_MAINTAINER else None
            c.execute(
                "UPDATE ideas SET stage = ?, waiting_since = ?, updated_at = ? WHERE id = ?",
                (dst.value, waiting, ts, idea_id),
            )
        return self.get(idea_id)

    def reset_wait(self, idea_id: int) -> None:
        with self.db.connect() as c:
            c.execute("UPDATE ideas SET waiting_since = ? WHERE id = ?", (now(), idea_id))


class AuditLog:
    def __init__(self, db: Database):
        self.db = db

    def add(self, idea_id: int | None, actor: str, action: str, detail: str = "") -> None:
        with self.db.connect() as c:
            c.execute(
                "INSERT INTO audit (idea_id, at, actor, action, detail) VALUES (?, ?, ?, ?, ?)",
                (idea_id, now(), actor, action, detail),
            )

    def for_idea(self, idea_id: int) -> list[dict[str, str]]:
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT at, actor, action, detail FROM audit WHERE idea_id = ? ORDER BY id", (idea_id,)
            ).fetchall()
        return [dict(r) for r in rows]


@dataclass(frozen=True)
class Project:
    name: str
    summary: str
    updated_by: str
    updated_at: str


class ProjectRepo:
    """Project summaries: maintainers write them, the bot only reads them."""

    def __init__(self, db: Database):
        self.db = db

    def list(self) -> list[Project]:
        with self.db.connect() as c:
            rows = c.execute("SELECT * FROM projects ORDER BY name").fetchall()
        return [Project(**dict(r)) for r in rows]

    def get(self, name: str) -> Project | None:
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        return Project(**dict(row)) if row else None

    def upsert(self, name: str, summary: str, by: str) -> bool:
        """Returns True if the project was new."""
        existed = self.get(name) is not None
        with self.db.connect() as c:
            c.execute(
                "INSERT INTO projects (name, summary, updated_by, updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(name) DO UPDATE SET summary = excluded.summary,"
                " updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                (name, summary, by, now()),
            )
        return not existed

    def remove(self, name: str) -> bool:
        with self.db.connect() as c:
            return c.execute("DELETE FROM projects WHERE name = ?", (name,)).rowcount > 0


class Meta:
    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: str = "") -> str:
        with self.db.connect() as c:
            row = c.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        with self.db.connect() as c:
            c.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
