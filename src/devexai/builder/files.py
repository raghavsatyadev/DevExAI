"""The built tool's files. They are model output, so every name is checked before anything touches the disk."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

MAX_FILES = 40
MAX_FILE_BYTES = 200_000
MAX_TOTAL_BYTES = 1_000_000
MAX_DEPTH = 6

_PART = re.compile(r"[A-Za-z0-9._-]{1,80}")  # no colons (Windows streams), spaces, quotes or slashes
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}


class BadFiles(ValueError):
    """The builder's answer cannot be saved as it is."""


def _safe_path(raw: Any) -> str:
    path = str(raw or "").replace("\\", "/").strip()
    parts = path.split("/")
    ok = path and not path.startswith("/") and len(parts) <= MAX_DEPTH and all(
        _PART.fullmatch(p) and p not in (".", "..") and not p.endswith(".")
        and p.split(".")[0].lower() not in _RESERVED for p in parts)
    if not ok:
        raise BadFiles(f"unsafe file name {path[:120]!r}")
    return path


def clean(files: Any) -> dict[str, str]:
    """{path: content} from the builder's list, or BadFiles. Paths are relative with forward slashes."""
    if not isinstance(files, list) or not files:
        raise BadFiles("the builder returned no files")
    if len(files) > MAX_FILES:
        raise BadFiles(f"the builder returned {len(files)} files; at most {MAX_FILES} are allowed")
    out: dict[str, str] = {}
    folded: set[str] = set()
    total = 0
    for item in files:
        if not isinstance(item, dict):
            raise BadFiles("the builder returned a file without a name")
        path = _safe_path(item.get("path"))
        # Windows ignores case, and a name cannot be both a file and a folder.
        key = path.lower()
        if key in folded or any(k.startswith(key + "/") or key.startswith(k + "/") for k in folded):
            raise BadFiles(f"{path} clashes with another file")
        folded.add(key)
        content = str(item.get("content", ""))
        size = len(content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise BadFiles(f"{path} is too big ({size} bytes)")
        total += size
        out[path] = content
    if total > MAX_TOTAL_BYTES:
        raise BadFiles(f"the files are too big together ({total} bytes)")
    return out


def as_list(files: dict[str, str]) -> list[dict[str, str]]:
    return [{"path": p, "content": c} for p, c in files.items()]


def save(folder: Path, files: dict[str, str]) -> None:
    """Replace `folder` with exactly these files (written beside it first, so no stale file stays)."""
    folder = folder.resolve()
    folder.parent.mkdir(parents=True, exist_ok=True)
    new, old = folder.with_name(folder.name + ".new"), folder.with_name(folder.name + ".old")
    for leftover in (new, old):
        shutil.rmtree(leftover, ignore_errors=True)
    try:
        for path, content in files.items():
            target = new.joinpath(*path.split("/")).resolve()
            if not target.is_relative_to(new):  # cannot happen after clean(); checked anyway
                raise BadFiles(f"{path} is outside the build folder")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        if folder.exists():
            folder.rename(old)
        try:
            new.rename(folder)
        except OSError:
            if old.exists():
                old.rename(folder)  # keep the last good build
            raise
    except OSError as e:
        raise BadFiles(f"could not save the files: {e}") from None
    finally:
        shutil.rmtree(new, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)


def remove(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
