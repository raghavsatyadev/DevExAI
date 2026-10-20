"""The installed layout (see home.py): versioned app folders, current.txt and a launcher.

An update is unpacked into its own app-<version> folder and current.txt is switched to it. The
running program is never touched, so the new version starts the next time DevExAI is started,
and the previous folder stays for a rollback (edit current.txt back).
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

from .manifest import UpdateError

EXE = "devexai.exe" if os.name == "nt" else "devexai"
CURRENT = "current.txt"
LAUNCHER = "devexai.cmd" if os.name == "nt" else "devexai"
_CMD = '@echo off\r\nset /p DEVEXAI_APP=<"%~dp0current.txt"\r\n"%~dp0%DEVEXAI_APP%\\devexai.exe" %*\r\n'
_SH = '#!/bin/sh\nd=$(dirname "$0")\nexec "$d/$(cat "$d/current.txt")/devexai" "$@"\n'


def app_dir(version: str) -> str:
    return f"app-{version}"


def current(root: Path) -> str | None:
    try:
        return (root / CURRENT).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def set_current(root: Path, folder: str) -> None:
    tmp = root / (CURRENT + ".tmp")
    tmp.write_text(folder, encoding="utf-8")
    os.replace(tmp, root / CURRENT)


def running_installed(root: Path) -> bool:
    """True when this process is an installed copy, so it may update itself."""
    if not getattr(sys, "frozen", False):
        return False
    here = Path(sys.executable).resolve().parent
    return here.parent == root.resolve() and here.name.startswith("app-")


def write_launcher(root: Path) -> Path:
    path = root / LAUNCHER
    path.write_text(_CMD if os.name == "nt" else _SH, encoding="utf-8", newline="")
    if os.name != "nt":
        path.chmod(0o755)
    return path


def install(src: Path, root: Path, version: str) -> Path:
    """Copy an unpacked build (the folder holding devexai.exe) into root and make it current."""
    if not (src / EXE).is_file():
        raise UpdateError(f"{src} does not hold {EXE}")
    root.mkdir(parents=True, exist_ok=True)
    dest = root / app_dir(version)
    if src.resolve() != dest.resolve():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    set_current(root, dest.name)
    return write_launcher(root)


def _safe_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or ":" in name or not name.strip("/"):
            raise UpdateError(f"the update zip holds an unsafe path: {info.filename!r}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise UpdateError(f"the update zip holds a link: {info.filename!r}")
    return zf.infolist()


def stage(zip_path: Path, root: Path, version: str) -> Path:
    """Unpack a verified zip into app-<version> and make it current. Returns the folder."""
    dest = root / app_dir(version)
    partial = root / (dest.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = _safe_members(zf)
            total = sum(i.file_size for i in members)
            if total > 4 << 30:
                raise UpdateError("the update zip unpacks to more than 4 GB")
            zf.extractall(partial, members)
    except (zipfile.BadZipFile, UpdateError) as e:
        shutil.rmtree(partial, ignore_errors=True)
        if isinstance(e, UpdateError):
            raise
        raise UpdateError("the update is not a valid zip") from None
    inner = partial / "devexai" if (partial / "devexai" / EXE).is_file() else partial
    if not (inner / EXE).is_file():
        shutil.rmtree(partial, ignore_errors=True)
        raise UpdateError(f"the update zip does not hold {EXE}")
    if dest.exists():
        shutil.rmtree(dest)
    os.replace(inner, dest)
    shutil.rmtree(partial, ignore_errors=True)
    set_current(root, dest.name)
    return dest


def prune(root: Path, keep: set[str]) -> None:
    """Delete app folders other than `keep` (the new current one and the one running now)."""
    for path in root.glob("app-*"):
        if path.is_dir() and path.name not in keep:
            shutil.rmtree(path, ignore_errors=True)
