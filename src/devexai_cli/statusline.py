"""Status-line tools: a script plus a settings.example.json whose statusLine runs it.

`devexai install` copies the script under .claude/ and sets statusLine in the assistant's settings file
(settings.local.json in a project, so a machine path is never committed; settings.json with --global).
Only the statusLine key is touched; the old value is kept in the receipt and put back on uninstall.
"""

from __future__ import annotations

import json
from pathlib import Path

from .files import installable, target
from .net import DevexError, plain

EXAMPLE = "settings.example.json"
KEY = "statusLine"
PROJECT_FILE, GLOBAL_FILE = ".claude/settings.local.json", ".claude/settings.json"
INTERPRETERS = {"python", "python3", "py", "node", "bash", "sh", "pwsh"}  # only "<interpreter> <script>"
_ABSENT = object()


def find(files: dict[str, bytes]) -> tuple[str, str, str] | None:
    """(script in the tool, where it goes under .claude/, interpreter) when the tool's settings example
    sets statusLine to a command that runs one of its own files; otherwise None."""
    raw = next((c for p, c in files.items() if p.split("/")[-1] == EXAMPLE), None)
    try:
        entry = json.loads(raw)[KEY] if raw else None
        words = entry["command"].split() if entry and entry.get("type") == "command" else []
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    if len(words) != 2 or words[0] not in INTERPRETERS:
        return None
    base = words[1].strip("\"'").replace("\\", "/").split("/")[-1]
    script = next((p for p in sorted(files, key=lambda p: (p.count("/"), p))
                   if p.split("/")[-1] == base and not p.startswith("tests/")), None)
    if not script:
        return None
    return script, (script if script.startswith(".claude/") else f".claude/{base}"), words[0]


def entry(root: Path, rel: str, interpreter: str) -> dict:
    return {"type": "command", "command": f'{interpreter} "{target(root, rel).as_posix()}"'}


def read(root: Path, rel: str) -> dict | None:
    path = target(root, rel)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError:
        raise DevexError(f"{path} is not valid JSON; fix it first, devexai will not rewrite it") from None
    if not isinstance(data, dict):
        raise DevexError(f"{path} is not a JSON object; not changing it")
    return data


def write(root: Path, rel: str, data: dict) -> None:
    path = target(root, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def plan(root: Path, rel: str, want: dict, old: dict | None, force: bool) -> tuple[str, str | None]:
    """(action, problem): action set | same | replace | update; problem blocks unless --force."""
    have = (read(root, rel) or {}).get(KEY, _ABSENT)
    if have is _ABSENT:
        return "set", None
    if have == want:
        return "same", None
    if old and old.get("file") == rel and have == old.get("after"):
        return "update", None
    return "replace", None if force else f"{rel} already has a {KEY} that is not from this tool"


def apply(root: Path, rel: str, want: dict, old: dict | None) -> dict:
    """Set statusLine; returns the receipt entry (what was there first, kept across updates)."""
    data = read(root, rel)
    first = old if old and old.get("file") == rel else {
        "file": rel, "created": data is None,
        **({"before": data[KEY]} if data and KEY in data else {})}
    data = data or {}
    data[KEY] = want
    write(root, rel, data)
    return {**first, "after": want}


def undo_plan(root: Path, rec: dict) -> str:
    have = (read(root, rec["file"]) or {}).get(KEY, _ABSENT)
    if have != rec.get("after"):
        return "keep" if have is not _ABSENT else "gone"
    return "restore" if "before" in rec else "unset"


def undo(root: Path, rec: dict) -> None:
    if undo_plan(root, rec) not in ("restore", "unset"):
        return
    data = read(root, rec["file"]) or {}
    if "before" in rec:
        data[KEY] = rec["before"]
    else:
        data.pop(KEY, None)
    if not data and rec.get("created"):
        target(root, rec["file"]).unlink()
    else:
        write(root, rec["file"], data)


def describe(want: dict) -> str:
    return plain(want["command"])


def install_set(files: dict[str, bytes]) -> tuple[dict[str, bytes], tuple[str, str, str] | None]:
    """What `devexai install` writes: files under assistant folders, plus a status-line script moved under
    .claude/. The blog uses this too, so the page and the command agree."""
    copy = installable(files)
    found = find(files)
    if found:
        copy[found[1]] = files[found[0]]
    return copy, found
