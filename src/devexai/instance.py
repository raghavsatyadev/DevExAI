"""One bot per data folder: a second start opens the running one's dashboard instead of a second bot.

Two bots on one database would both answer every chat message. The guard is a lock on devexai.lock in the
data folder, held for as long as the bot runs; the operating system drops it when the process ends, even
after a crash, so there is no stale lock to clean up.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import IO

LOCK = "devexai.lock"
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
