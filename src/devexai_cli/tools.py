"""Install a tool into a project or the home folder, and remove it again.

The command shows every change and asks first; it never runs anything from the tool and never edits
settings files. Uninstall removes exactly what install wrote (files edited since are kept) and puts back
any file it replaced.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

from .files import current_hash, installable, load_receipt, made_dirs, owners, read_zip, receipt_path, target
from .net import STATE, DevexError, fetch, find, plain, sha256, tools


def plan_install(root: Path, name: str, files: dict[str, bytes], force: bool) -> list[tuple[str, str]]:
    """[(action, file)] with action new | same | replace | update | remove."""
    old = (load_receipt(root, name) or {}).get("files", {})
    others = owners(root, name)
    steps, blocked = [], []
    for rel, content in files.items():
        have = current_hash(target(root, rel))
        if have is None:
            steps.append(("new", rel))
        elif have == sha256(content):
            steps.append(("same", rel))
        elif rel in old and old[rel] == have:
            steps.append(("update", rel))  # ours, unedited: no backup needed
        else:
            if rel.lower() in others:
                blocked.append(f"{rel} belongs to {others[rel.lower()]}")
            elif not force:
                blocked.append(f"{rel} already exists and is not from {name}")
            steps.append(("replace", rel))
    steps += [("remove", rel) for rel in old if rel not in files]
    if blocked:
        raise DevexError("not installing, to keep your files:\n  " + "\n  ".join(blocked)
                         + ("\nAdd --force to replace them (the old ones are kept to put back on uninstall)."
                            if not any("belongs to" in b for b in blocked) else ""))
    return steps


def confirm(question: str, yes: bool) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        raise DevexError("nothing changed. Run it in a terminal to answer, or add --yes")
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def install(server: str, wanted: str, root: Path, *, home: Path, yes: bool, force: bool, scope: str = "",
            out=print) -> bool:
    tool = find(tools(server, home), wanted)
    name = re.sub(r"[^a-z0-9-]", "", tool["name"].lower())[:60] or f"tool-{tool.get('id')}"
    files = installable(read_zip(fetch(f"{server}/blog/{urllib.parse.quote(tool['post'])}/files.zip", home)))
    manual = plain(tool.get("install", "")).strip()
    if not files:
        out(f"{name} has nothing to install automatically (no .claude/, .gemini/ or .codex/ files).")
        if manual:
            out(f"Its own steps:\n{manual}")
        return False
    steps = plan_install(root, name, files, force)
    out(f"Install {name} (#{tool.get('id')}) into {root}:")
    for action, rel in steps:
        out(f"  {action:<8} {rel}")
    if all(a == "same" for a, _ in steps):
        out("Already installed; nothing to change.")
        return False
    if not confirm("Go ahead?", yes):
        out("Nothing changed.")
        return False
    receipt = load_receipt(root, name) or {"files": {}, "backups": {}, "dirs": []}
    state = root / STATE
    for action, rel in steps:
        path = target(root, rel)
        if action == "remove":
            if current_hash(path) == receipt["files"].get(rel):
                path.unlink()
            receipt["files"].pop(rel, None)
            continue
        if action == "same":
            continue
        if action == "replace" and rel not in receipt["backups"]:
            backup = f"backup/{name}/{rel}"
            target(state, backup).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target(state, backup))
            receipt["backups"][rel] = backup
        receipt["dirs"] += [d for d in made_dirs(root, rel) if d not in receipt["dirs"]]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[rel])
        receipt["files"][rel] = sha256(files[rel])
    receipt.update(tool=name, id=tool.get("id"), title=plain(tool.get("title", "")), server=server)
    state.mkdir(exist_ok=True)
    receipt_path(root, name).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    out(f"Installed {name}. Remove it with: devexai uninstall {name}{scope}")
    if manual:
        out(f"Steps devexai does not do for you (from the tool's README):\n{manual}")
    return True


def uninstall(wanted: str, root: Path, *, yes: bool, out=print) -> bool:
    name = wanted.strip().lower()
    receipt = load_receipt(root, name)
    if receipt is None:
        known = sorted(p.stem for p in (root / STATE).glob("*.json"))
        raise DevexError(f"{name} is not installed in {root}" + (f" (installed: {', '.join(known)})" if known else ""))
    files, backups = receipt.get("files", {}), receipt.get("backups", {})
    out(f"Uninstall {name} from {root}:")
    for rel, digest in files.items():
        have = current_hash(target(root, rel))
        action = "restore" if rel in backups else "remove" if have == digest else "keep" if have else "gone"
        out(f"  {action:<8} {rel}" + ("  (edited since install)" if action == "keep" else ""))
    if not confirm("Go ahead?", yes):
        out("Nothing changed.")
        return False
    state = root / STATE
    for rel, digest in files.items():
        path = target(root, rel)
        if rel in backups and target(state, backups[rel]).is_file():
            shutil.copy2(target(state, backups[rel]), path)
        elif current_hash(path) == digest:
            path.unlink()
    for rel in sorted(receipt.get("dirs", []), key=lambda d: d.count("/"), reverse=True):
        folder = target(root, rel)
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    shutil.rmtree(state / "backup" / name, ignore_errors=True)
    receipt_path(root, name).unlink()
    for leftover in (state / "backup", state):
        if leftover.is_dir() and not any(leftover.iterdir()):
            leftover.rmdir()
    out(f"Removed {name}.")
    return True
