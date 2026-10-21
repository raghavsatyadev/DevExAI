"""The Start menu entry "DevExAI" (Windows), which starts devexaiw.exe: the tray icon, no console.

It points into the current app-<version> folder, so install and every staged update rewrite it.
Written by PowerShell's WScript.Shell, as Python has no stdlib way to make a .lnk file.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ..proc import NO_WINDOW, TRAY_EXE
from .install import current

log = logging.getLogger(__name__)

_PS = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:DX_LNK); "
       "$s.TargetPath = $env:DX_EXE; $s.WorkingDirectory = $env:DX_DIR; $s.IconLocation = $env:DX_EXE + ',0'; "
       "$s.Description = 'DevExAI idea bot (runs in the notification area)'; $s.Save()")


def start_menu_link() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "DevExAI.lnk"


def write(root: Path) -> Path | None:
    """Point the Start menu entry at the current version's devexaiw.exe. None when there is nothing to do."""
    folder = current(root)
    exe = root / folder / TRAY_EXE if folder else None
    if os.name != "nt" or not exe or not exe.is_file():
        return None
    link = start_menu_link()
    link.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "DX_LNK": str(link), "DX_EXE": str(exe), "DX_DIR": str(exe.parent)}
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS], env=env, check=True,
                       capture_output=True, timeout=60, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("Start menu entry not written: %s", e)
        return None
    return link
