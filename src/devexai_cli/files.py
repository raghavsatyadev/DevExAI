"""A tool's files, checked again on this computer, and the record of what an install wrote.

Only files under .claude/, .gemini/ and .codex/ are installed, at the same path under the project or
home folder (a status-line script goes under .claude/ too, see statusline.py).
What was written is recorded in .devex/<tool>.json there.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

from .net import STATE, DevexError, plain, sha256

ASSISTANT_DIRS = (".claude", ".gemini", ".codex")
MAX_FILES, MAX_TOTAL_BYTES, MAX_DEPTH = 40, 1_000_000, 6  # as the server's builder allows
_PART = re.compile(r"[A-Za-z0-9._-]{1,80}")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}


def safe_path(name: str) -> str:
    parts = name.split("/")
    ok = name and "\\" not in name and not name.startswith("/") and len(parts) <= MAX_DEPTH and all(
        _PART.fullmatch(p) and p not in (".", "..") and not p.endswith(".")
        and p.split(".")[0].lower() not in _RESERVED for p in parts)
    if not ok:
        raise DevexError(f"the tool has an unsafe file name {plain(name)[:120]!r}; not installing it")
    return name


def read_zip(data: bytes) -> dict[str, bytes]:
    """Every file in the download, checked again here: the names, the count and the size."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise DevexError("the download is not a zip file") from None
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
            raise DevexError("the tool has more files or bytes than DevExAI allows; not installing it")
        out: dict[str, bytes] = {}
        seen: set[str] = set()
        for info in infos:
            name = safe_path(info.filename)
            key = name.lower()  # Windows and macOS ignore case
            if key in seen or any(k.startswith(key + "/") or key.startswith(k + "/") for k in seen):
                raise DevexError(f"the tool has two files called {name}; not installing it")
            seen.add(key)
            out[name] = zf.read(info)
    if sum(len(v) for v in out.values()) > MAX_TOTAL_BYTES:
        raise DevexError("the tool is bigger than DevExAI allows; not installing it")
    return out


def installable(files: dict[str, bytes]) -> dict[str, bytes]:
    return {p: c for p, c in files.items() if p.split("/")[0] in ASSISTANT_DIRS and "/" in p}


def target(root: Path, rel: str) -> Path:
    path = root.joinpath(*rel.split("/"))
    if not path.resolve().is_relative_to(root.resolve()):  # e.g. a folder on the way is a link elsewhere
        raise DevexError(f"{rel} would land outside {root}; not installing it")
    return path


def receipt_path(root: Path, name: str) -> Path:
    return root / STATE / f"{name}.json"


def load_receipt(root: Path, name: str) -> dict | None:
    path = receipt_path(root, name)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise DevexError(f"{path} is damaged; remove it by hand") from None
    # The receipt may sit in a shared repository: only ever act on assistant folders inside root.
    settings = [data["settings"].get("file", "")] if isinstance(data.get("settings"), dict) else []
    for rel in [*data.get("files", {}), *data.get("backups", {}), *data.get("dirs", []), *settings]:
        if safe_path(rel).split("/")[0] not in ASSISTANT_DIRS:
            raise DevexError(f"{path} names {plain(rel)!r}, outside {', '.join(ASSISTANT_DIRS)}; not touching it")
    return data


def owners(root: Path, skip: str) -> dict[str, str]:
    """{file: tool} for files other installs here own."""
    out: dict[str, str] = {}
    for path in sorted((root / STATE).glob("*.json")):
        if path.stem != skip and (data := load_receipt(root, path.stem)):
            out.update({rel.lower(): path.stem for rel in data.get("files", {})})
    return out


def current_hash(path: Path) -> str | None:
    return sha256(path.read_bytes()) if path.is_file() else None


def made_dirs(root: Path, rel: str) -> list[str]:
    """The folders on the way to rel that do not exist yet, outermost first (so uninstall can remove them)."""
    parts, out = rel.split("/")[:-1], []
    for i in range(1, len(parts) + 1):
        if not root.joinpath(*parts[:i]).exists():
            out.append("/".join(parts[:i]))
    return out
