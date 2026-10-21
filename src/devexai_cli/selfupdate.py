"""devexai keeps itself current from the DevExAI server it is connected to.

The server lists the developer builds it carries at /get/version.json ({"version", "files": {platform:
{"name", "sha256"}}}). After a command devexai looks there at most once a day and says when a newer one is
out; `devexai update` downloads it, checks its SHA-256 and installs it: on Windows by running the new
setup, elsewhere by replacing the program file.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .net import STATE, DevexError, fetch, fetch_json, sha256

DAY = 24 * 3600
MAX_PROGRAM = 200_000_000
DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def platform_tag() -> str:
    arch = "x64" if platform.machine().lower() in ("amd64", "x86_64") else platform.machine().lower()
    return f"{'windows' if os.name == 'nt' else sys.platform}-{arch}"


def version_tuple(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in str(text).split("."))
    except ValueError:
        return (0,)


def newer(server: str, home: Path) -> dict | None:
    """{"version", "name", "sha256"} of a newer build for this computer, or None."""
    info = fetch_json(f"{server}/get/version.json", home)
    entry = (info.get("files") or {}).get(platform_tag())
    if not isinstance(entry, dict) or version_tuple(info.get("version", "")) <= version_tuple(__version__):
        return None
    return {"version": str(info["version"]), "name": str(entry.get("name", "")), "sha256": str(entry.get("sha256", ""))}


def notice(server: str, home: Path) -> str | None:
    """A one-line hint when a newer devexai is out; looks at most once a day and never fails a command."""
    stamp = home / STATE / "update-check"
    try:
        if stamp.is_file() and time.time() - stamp.stat().st_mtime < DAY:
            return None
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        found = newer(server, home)
    except (DevexError, OSError):
        return None
    return f"devexai {found['version']} is out (you have {__version__}). Get it with: devexai update" if found else None


def update(server: str, home: Path, out=print) -> bool:
    found = newer(server, home)
    if not found:
        out(f"devexai {__version__} is the newest.")
        return False
    if not getattr(sys, "frozen", False):
        raise DevexError(f"this devexai runs from Python source; download {server}/get/devexai.pyz instead")
    data = fetch(f"{server}/get/{found['name']}", home, limit=MAX_PROGRAM)
    if sha256(data) != found["sha256"]:
        raise DevexError("the download does not match the server's checksum; nothing changed")
    if os.name == "nt":  # a running exe cannot replace itself: the setup does it once we have exited
        setup = Path(tempfile.gettempdir()) / f"DevExAI-User-Setup-{found['version']}.exe"
        setup.write_bytes(data)
        # /SERVER: a silent setup shows no page to type it in, and this file has no "downloaded from" mark
        subprocess.Popen([str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/SERVER={server}"],
                         creationflags=DETACHED, close_fds=True)
        out(f"Installing devexai {found['version']}; the setup finishes in its own window.")
        return True
    exe = Path(sys.executable)
    new = exe.with_name(exe.name + ".new")
    new.write_bytes(data)
    new.chmod(0o755)
    os.replace(new, exe)
    out(f"Updated devexai to {found['version']}.")
    return True
