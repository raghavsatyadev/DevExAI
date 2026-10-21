"""Starting helper processes (claude, the fetch worker) without flashing windows.

The tray build (devexaiw.exe) has no console, so Windows would give every console child its own
new console window; CREATE_NO_WINDOW runs them hidden. The flag is harmless from a terminal too.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # 0 off Windows
CONSOLE_EXE, TRAY_EXE = "devexai.exe", "devexaiw.exe"


def worker_command(module: str, flag: str) -> list[str]:
    """How to run one of our helper modules: `python -I -m module`, or the packaged exe with a flag.

    A packaged build runs the console exe even from the tray one: a windowed exe has no stdout to
    answer on.
    """
    if not getattr(sys, "frozen", False):
        return [sys.executable, "-I", "-m", module]
    exe = Path(sys.executable)
    if exe.name.lower() == TRAY_EXE and (exe.parent / CONSOLE_EXE).is_file():
        exe = exe.parent / CONSOLE_EXE
    return [str(exe), flag]
