"""In-memory chat adapter for tests."""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field

from .base import Button, Handler


@dataclass
class Posted:
    channel: str
    text: str
    thread: str | None
    buttons: tuple[Button, ...]
    ref: str


@dataclass
class FakeChat:
    posts: list[Posted] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def post(self, channel, text, *, thread=None, buttons=()):
        with self._lock:
            ref = thread or f"t{next(self._ids)}"
            self.posts.append(Posted(channel, text, thread, tuple(buttons), ref))
        return ref

    def mention(self, user: str) -> str:
        return f"@{user}"

    def run(self, handler: Handler) -> None:  # tests drive the bot directly
        raise NotImplementedError

    def in_thread(self, thread: str) -> list[str]:
        return [p.text for p in self.posts if p.ref == thread]

    def texts(self) -> list[str]:
        return [p.text for p in self.posts]
