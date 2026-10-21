"""One bot per data folder: a second start opens the running one's dashboard instead of a second bot.

Two bots on one database would both answer every chat message. The guard is a lock on devexai.lock in the
data folder, held for as long as the bot runs; the operating system drops it when the process ends, even
after a crash, so there is no stale lock to clean up.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import IO, Callable

LOCK, PID, STOP = "devexai.lock", "devexai.pid", "devexai.stop"
_held: list[IO] = []


def acquire(path: Path = Path(LOCK)) -> IO | None:
    """Hold the lock for this process. None when another process holds it."""
    f = open(path, "a+")  # noqa: SIM115 - stays open for as long as we run
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    _held.append(f)
    return f


def release(f: IO | None) -> None:
    if f is None:
        return
    if os.name == "nt":
        import msvcrt

        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    f.close()
    if f in _held:
        _held.remove(f)


def running(data: Path) -> bool:
    """True when a bot holds the lock for this data folder."""
    f = acquire(data / LOCK)
    release(f)
    return f is None


def pid(data: Path) -> int | None:
    try:
        return int((data / PID).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def started(data: Path) -> None:
    """Called by the bot that holds the lock: note its process id; forget a stop request left from before."""
    (data / STOP).unlink(missing_ok=True)
    (data / PID).write_text(str(os.getpid()), encoding="utf-8")


def stopped(data: Path) -> None:
    for name in (PID, STOP):
        (data / name).unlink(missing_ok=True)


def watch_stop(data: Path, done: threading.Event, on_stop: Callable[[], None]) -> None:
    """Call on_stop when `devexai stop admin` leaves a stop file in the data folder."""
    def loop() -> None:
        while not done.wait(1):
            if (data / STOP).exists():
                (data / STOP).unlink(missing_ok=True)
                on_stop()
                return

    threading.Thread(target=loop, name="devexai-stop", daemon=True).start()


def request_stop(data: Path, wait: float = 20) -> bool:
    """Ask the running bot to quit and wait for it. A bot that does not quit in time (the console build waits
    for a line to be typed) is ended. True when no bot runs any more."""
    if not running(data):
        return True
    (data / STOP).write_text("stop", encoding="utf-8")
    if _gone(data, wait):
        return True
    if (number := pid(data)) and number != os.getpid():
        import signal

        try:
            os.kill(number, signal.SIGTERM)  # Windows: TerminateProcess
        except OSError:
            pass
    return _gone(data, 10)


def _gone(data: Path, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not running(data):
            return True
        time.sleep(0.25)
    return not running(data)
