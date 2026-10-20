"""Where DevExAI keeps its files.

Installed (the packaged build), the program lives in versioned folders and the company's data
lives apart from it, so an update never touches settings, the database or the blog:

    %LOCALAPPDATA%\\DevExAI\\            (Linux: ~/.local/share/devexai/)
        app-0.1.0\\devexai.exe           one folder per version; the two newest are kept
        current.txt                      name of the folder to run
        devexai.cmd                      launcher that runs the current version
        data\\                            settings.toml, .env, data\\devexai.db, data\\blog\\, ...

From a source checkout the data home is the working folder, as before.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SETTINGS, EXAMPLE = "settings.toml", "settings.example.toml"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "DevExAI"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "devexai"


def data_home(explicit: Path | None = None) -> Path:
    if explicit:
        return explicit
    if env := os.environ.get("DEVEXAI_HOME"):
        return Path(env)
    return install_root() / "data" if frozen() else Path.cwd()


def bundled(name: str) -> Path:
    """A file shipped with the program: inside the packaged build, or at the repository root."""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parents[2]
    return Path(base) / name


def prepare(home: Path) -> bool:
    """Create the data home; on first run copy the example settings. True if this is a first run."""
    home.mkdir(parents=True, exist_ok=True)
    target = home / SETTINGS
    if target.exists():
        return False
    shutil.copyfile(bundled(EXAMPLE), target)
    return True
