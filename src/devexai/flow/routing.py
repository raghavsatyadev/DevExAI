"""Who looks after an idea: topic match, then round-robin; reassign when a maintainer stays silent."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from ..config import Maintainer
from ..store import Meta


class Router:
    def __init__(self, maintainers: Callable[[], tuple[Maintainer, ...]], meta: Meta, timeout_hours: float):
        self._maintainers = maintainers  # read on every call: admins change the list in the dashboard
        self.meta = meta
        self.timeout = timedelta(hours=timeout_hours)

    @property
    def maintainers(self) -> tuple[Maintainer, ...]:
        return self._maintainers()

    def is_maintainer(self, user: str) -> bool:
        return any(m.name == user for m in self.maintainers)

    def pick(self, topic: str | None, exclude: str | None = None) -> str:
        """Maintainers for the topic (else everyone), in turn. Never returns `exclude` if anyone else exists."""
        everyone = self.maintainers
        pool = [m.name for m in everyone if topic and topic in m.topics]
        key = f"rr:{topic}" if pool else "rr:*"
        pool = pool or [m.name for m in everyone]
        if exclude and len(pool) == 1 and pool[0] == exclude:
            pool = [m.name for m in everyone]  # widen before giving up
            key = "rr:*"
        choices = [n for n in pool if n != exclude] or pool
        turn = int(self.meta.get(key, "0"))
        self.meta.set(key, str(turn + 1))
        return choices[turn % len(choices)]

    def overdue(self, waiting_since: str | None, now: datetime) -> bool:
        if not waiting_since:
            return False
        return now - datetime.fromisoformat(waiting_since) >= self.timeout
