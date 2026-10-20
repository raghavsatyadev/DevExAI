"""Maintainers and admins, with their dashboard passwords. Admins manage this list in the dashboard.

On the very first start the list is copied from settings.toml [[maintainers]]; after that the
database is the source of truth.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass

from ..config import Maintainer
from .db import Database, now

ADMIN, MAINTAINER = "admin", "maintainer"
ROLES = (ADMIN, MAINTAINER)
MIN_PASSWORD = 10
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}")
EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s.]{2,}")
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


class PeopleError(ValueError):
    """A change that is not allowed, with a message fit to show the admin."""


@dataclass(frozen=True)
class Person:
    name: str
    email: str | None
    role: str
    topics: tuple[str, ...]
    active: bool
    has_password: bool
    created_at: str

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN

    def as_maintainer(self) -> Maintainer:
        return Maintainer(self.name, self.topics)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _matches(password: str, stored: str | None) -> bool:
    try:
        kind, salt, digest = (stored or "").split("$")
    except ValueError:
        kind = salt = digest = ""
    if kind != "scrypt":  # still spend the time, so timing does not reveal unknown emails
        hashlib.scrypt(password.encode(), salt=b"0" * 16, **_SCRYPT)
        return False
    got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    return hmac.compare_digest(got.hex(), digest)


def clean_topics(text: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    items = text.replace(",", " ").split() if isinstance(text, str) else text
    return tuple(dict.fromkeys(t.strip().lower() for t in items if t.strip()))[:20]


class PeopleRepo:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _row(row) -> Person:
        return Person(name=row["name"], email=row["email"], role=row["role"],
                      topics=tuple(json.loads(row["topics"])), active=bool(row["active"]),
                      has_password=bool(row["pw_hash"]), created_at=row["created_at"])

    def list(self, *, include_inactive: bool = False) -> list[Person]:
        where = "" if include_inactive else " WHERE active = 1"
        with self.db.connect() as c:
            rows = c.execute(f"SELECT * FROM people{where} ORDER BY role = 'admin' DESC, created_at, name").fetchall()
        return [self._row(r) for r in rows]

    def maintainers(self) -> tuple[Maintainer, ...]:
        return tuple(p.as_maintainer() for p in self.list())

    def get(self, name: str) -> Person | None:
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()
        return self._row(row) if row else None

    def seed(self, maintainers: tuple[Maintainer, ...]) -> None:
        """First start only: copy settings.toml maintainers. The first one, or any marked admin, is admin."""
        with self.db.connect() as c:
            if c.execute("SELECT COUNT(*) FROM people").fetchone()[0]:
                return
            any_admin = any(m.admin for m in maintainers)
            for i, m in enumerate(maintainers):
                role = ADMIN if m.admin or (i == 0 and not any_admin) else MAINTAINER
                c.execute("INSERT INTO people (name, email, role, topics, created_at) VALUES (?, ?, ?, ?, ?)",
                          (m.name, (m.email or "").lower() or None, role, json.dumps(list(m.topics)), now()))

    def add(self, name: str, email: str, role: str, topics: tuple[str, ...]) -> Person:
        name, email = name.strip(), email.strip().lower()
        if not NAME.fullmatch(name):
            raise PeopleError("A name is 1-40 letters, digits, dots, dashes or underscores, as in chat.")
        self._check(email, role)
        if self.get(name):
            raise PeopleError(f"{name} already exists.")
        with self.db.connect() as c:
            c.execute("INSERT INTO people (name, email, role, topics, created_at) VALUES (?, ?, ?, ?, ?)",
                      (name, email or None, role, json.dumps(list(topics)), now()))
        return self.get(name)

    def update(self, name: str, *, email: str | None = None, role: str | None = None,
               topics: tuple[str, ...] | None = None, active: bool | None = None) -> Person:
        person = self.get(name)
        if person is None:
            raise PeopleError(f"No one called {name}.")
        email = person.email or "" if email is None else email.strip().lower()
        role = role or person.role
        active = person.active if active is None else active
        self._check(email, role, exclude=name)
        if person.is_admin and person.active and (role != ADMIN or not active) and self._admins(exclude=name) == 0:
            raise PeopleError("There must always be at least one active admin.")
        with self.db.connect() as c:
            c.execute("UPDATE people SET email = ?, role = ?, topics = ?, active = ? WHERE name = ?",
                      (email or None, role, json.dumps(list(person.topics if topics is None else topics)),
                       int(active), name))
        return self.get(name)

    def set_password(self, name: str, password: str) -> None:
        if len(password) < MIN_PASSWORD:
            raise PeopleError(f"Use a password of at least {MIN_PASSWORD} characters.")
        person = self.get(name)
        if person is None or not person.email:
            raise PeopleError("Give this person an email address first; it is their sign-in name.")
        with self.db.connect() as c:
            c.execute("UPDATE people SET pw_hash = ? WHERE name = ?", (hash_password(password), name))

    def check_login(self, email: str, password: str) -> Person | None:
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM people WHERE email = ? AND active = 1",
                            (email.strip().lower(),)).fetchone()
        if not _matches(password, row["pw_hash"] if row else None):
            return None
        return self._row(row)

    def anyone_can_sign_in(self) -> bool:
        with self.db.connect() as c:
            return bool(c.execute("SELECT 1 FROM people WHERE role = 'admin' AND active = 1 "
                                  "AND pw_hash IS NOT NULL").fetchone())

    def _admins(self, exclude: str = "") -> int:
        with self.db.connect() as c:
            return c.execute("SELECT COUNT(*) FROM people WHERE role = 'admin' AND active = 1 AND name != ?",
                             (exclude,)).fetchone()[0]

    def _check(self, email: str, role: str, exclude: str = "") -> None:
        if role not in ROLES:
            raise PeopleError(f"Role must be one of {', '.join(ROLES)}.")
        if email and not EMAIL.fullmatch(email):
            raise PeopleError(f"{email} does not look like an email address.")
        if email:
            with self.db.connect() as c:
                if c.execute("SELECT 1 FROM people WHERE email = ? AND name != ?", (email, exclude)).fetchone():
                    raise PeopleError(f"{email} is already used by someone else.")
