"""Terminal chat adapter: play every person in the conversation from one console.

    /as <name>        act as another person (default: the first maintainer)
    >t3 <text>        reply inside thread t3
    /dm <text>        send a direct message to the bot
    /quit             exit
    anything else     message in the ideas channel (commands like /devex-idea work too)
"""

from __future__ import annotations

import itertools
import sys
import threading

from .base import Button, Event, Handler

HELP = __doc__.split("\n", 2)[2]


class ConsoleChat:
    def __init__(self, ideas_channel: str, user: str, out=None, inp=None, first_ref: int = 1):
        self.ideas_channel = ideas_channel
        self.user = user
        if out is None and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles would crash
        self.out = out or sys.stdout
        self.inp = inp or sys.stdin
        self._ids = itertools.count(first_ref)  # continue after refs stored before a restart
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def post(self, channel, text, *, thread=None, buttons: tuple[Button, ...] = ()):
        with self._lock:
            ref = thread or f"t{next(self._ids)}"
            where = f"{channel} [{ref}]" if thread else f"{channel} (new thread {ref})"
            lines = [f"\n--- {where} ---", text]
            if buttons:
                lines.append("  " + "   ".join(f"[{b.label}: {b.command}]" for b in buttons))
            print("\n".join(lines), file=self.out, flush=True)
        return ref

    def mention(self, user: str) -> str:
        return f"@{user}"

    def _prompt(self) -> None:
        print(f"{self.user}> ", end="", file=self.out, flush=True)

    def run(self, handler: Handler) -> None:
        print(HELP, file=self.out)
        self._prompt()
        for raw in self.inp:
            if self._stop.is_set():  # another chat platform took over
                return
            line = raw.strip()
            if not line:
                self._prompt()
                continue
            if line == "/quit":
                return
            if line.startswith("/as "):
                self.user = line[4:].strip().lstrip("@") or self.user
            elif line.startswith(">"):
                ref, _, text = line[1:].partition(" ")
                handler(Event(self.user, text.strip(), self.ideas_channel, thread=ref))
            elif line.startswith("/dm "):
                handler(Event(self.user, line[4:].strip(), f"dm:{self.user}", is_dm=True))
            else:
                handler(Event(self.user, line, self.ideas_channel))
            self._prompt()

    def stop(self) -> None:
        """Stop after the next line typed (a console read cannot be interrupted)."""
        self._stop.set()
