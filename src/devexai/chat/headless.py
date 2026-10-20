"""No chat platform: the bot runs for the dashboard alone, e.g. as a background service.

Messages the bot would post go to the log. run() blocks until Ctrl+C or stop().
"""

from __future__ import annotations

import itertools
import logging
import threading

from .base import Button, Handler

log = logging.getLogger(__name__)


class HeadlessChat:
    def __init__(self, first_ref: int = 1):
        self._ids = itertools.count(first_ref)
        self._stop = threading.Event()

    def post(self, channel, text, *, thread=None, buttons: tuple[Button, ...] = ()):
        ref = thread or f"t{next(self._ids)}"
        log.info("chat %s [%s]: %s", channel, ref, text)
        return ref

    def mention(self, user: str) -> str:
        return f"@{user}"

    def run(self, handler: Handler) -> None:
        try:
            while not self._stop.wait(1):  # short waits so Ctrl+C is seen on Windows
                pass
        except KeyboardInterrupt:
            pass

    def stop(self) -> None:
        self._stop.set()
