"""Dashboard sessions and login throttling. Passwords themselves live in store/people.py."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

SESSION_SECONDS = 12 * 3600
MAX_FAILURES = 5          # per address and email
MAX_ADDRESS_FAILURES = 20  # per address, whoever signs in; a success does not reset it
LOCK_SECONDS = 15 * 60


@dataclass
class Session:
    user: str
    csrf: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    expires: float = field(default_factory=lambda: time.time() + SESSION_SECONDS)
    flash: str = ""


class Sessions:
    def __init__(self):
        self._by_id: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, user: str) -> str:
        sid = secrets.token_urlsafe(32)
        with self._lock:
            now = time.time()
            self._by_id = {k: s for k, s in self._by_id.items() if s.expires > now}  # drop stale ones
            self._by_id[sid] = Session(user)
        return sid

    def get(self, sid: str) -> Session | None:
        with self._lock:
            sess = self._by_id.get(sid)
            if sess and sess.expires <= time.time():
                del self._by_id[sid]
                return None
            return sess

    def end(self, sid: str) -> None:
        with self._lock:
            self._by_id.pop(sid, None)

    def end_user(self, user: str) -> None:
        """Sign someone out everywhere, e.g. after a password change or deactivation."""
        with self._lock:
            self._by_id = {k: s for k, s in self._by_id.items() if s.user != user}

    def pop_flash(self, sess: Session) -> str:
        with self._lock:
            text, sess.flash = sess.flash, ""
        return text

    def flash(self, sess: Session, text: str) -> None:
        with self._lock:
            sess.flash = text


class Throttle:
    """Refuse sign-in for LOCK_SECONDS after too many wrong passwords from one address.

    Two counters: one per address and email (cleared when that person signs in), and one per address
    alone that a success never clears, so signing in to your own account cannot reset guessing at others.
    """

    def __init__(self):
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        return [t for t in self._fails.get(key, ()) if now - t < LOCK_SECONDS]

    def blocked(self, address: str, email: str) -> bool:
        now = time.time()
        with self._lock:
            return (len(self._recent(f"{address}|{email}", now)) >= MAX_FAILURES
                    or len(self._recent(address, now)) >= MAX_ADDRESS_FAILURES)

    def failed(self, address: str, email: str) -> None:
        now = time.time()
        with self._lock:
            for key in (address, f"{address}|{email}"):
                self._fails[key] = self._recent(key, now) + [now]

    def succeeded(self, address: str, email: str) -> None:
        with self._lock:
            self._fails.pop(f"{address}|{email}", None)
