"""devex: install a DevExAI tool into a project or into your home folder, and remove it again.

    python devex.py list --server https://devexai.example:8765
    python devex.py install <tool> --project        files go under this folder (commit them for the team)
    python devex.py install <tool> --global         files go under your home folder, for every project
    python devex.py uninstall <tool> --project | --global

One idea is one tool. <tool> is the name the blog shows (or the idea number). Only the tool's files under
.claude/, .gemini/ and .codex/ are installed, at the same path under the project or home folder. The
command shows every change and asks first; it never runs anything from the tool and never edits settings
files. What it wrote is recorded in .devex/<tool>.json there, so uninstall removes exactly that (files you
edited since are kept) and puts back any file it replaced.

One file, Python standard library only: the DevExAI server hands it out at /blog/devex.py.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ASSISTANT_DIRS = (".claude", ".gemini", ".codex")
STATE = ".devex"
MAX_FILES, MAX_TOTAL_BYTES, MAX_DEPTH = 40, 1_000_000, 6  # as the server's builder allows
MAX_DOWNLOAD = 4_000_000
_PART = re.compile(r"[A-Za-z0-9._-]{1,80}")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")  # colour and cursor codes, removed whole
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # keeps tab and newline; drops terminal escapes


class DevexError(Exception):
    """Something the person can fix; printed without a traceback."""


def plain(text: object) -> str:
    """Server text is shown in a terminal: no control characters, so no escape sequences."""
    return _CONTROL.sub("", _ANSI.sub("", str(text)))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- the server -------------------------------------------------------------------------------------

def config_file(home: Path) -> Path:
    return home / STATE / "server.txt"


def server_url(given: str | None, home: Path) -> str:
    """--server, else DEVEX_SERVER, else the one saved last time. A given one is saved for next time."""
    url = given or os.environ.get("DEVEX_SERVER", "")
    if not url and config_file(home).is_file():
        url = config_file(home).read_text(encoding="utf-8").strip()
    if not url:
        raise DevexError("which DevExAI server? Add --server https://<server>:<port> (remembered after)")
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise DevexError(f"not a web address: {url}")
    url = url.rstrip("/")
    if given:
        config_file(home).parent.mkdir(parents=True, exist_ok=True)
        config_file(home).write_text(url + "\n", encoding="utf-8")
    return url


def fetch(url: str, limit: int = MAX_DOWNLOAD) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - http(s) only, checked above
            data = resp.read(limit + 1)
    except urllib.error.HTTPError as e:
        raise DevexError(f"the server answered {e.code} for {url}") from None
    except (urllib.error.URLError, OSError) as e:
        raise DevexError(f"could not reach {url}: {getattr(e, 'reason', e)}") from None
    if len(data) > limit:
        raise DevexError(f"{url} is bigger than {limit} bytes")
    return data


def tools(server: str) -> list[dict]:
    try:
        listed = json.loads(fetch(f"{server}/blog/tools.json")).get("tools", [])
    except (ValueError, AttributeError):
        raise DevexError("the server's tool list is not readable") from None
    return [t for t in listed if isinstance(t, dict) and isinstance(t.get("name"), str)
            and isinstance(t.get("post"), str)]


def find(listed: list[dict], wanted: str) -> dict:
    wanted = wanted.strip().lower().lstrip("#")
    hits = [t for t in listed if wanted in (t["name"], t["post"].removesuffix(".md"), str(t.get("id")))]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise DevexError(f"no published tool called {wanted!r}. See: devex list")
    raise DevexError(f"{wanted!r} could be: " + ", ".join(f"#{t.get('id')} {t['name']}" for t in hits)
                     + ". Use the number.")


# ---- the tool's files -------------------------------------------------------------------------------

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


# ---- what is installed here -------------------------------------------------------------------------

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
    for rel in [*data.get("files", {}), *data.get("backups", {}), *data.get("dirs", [])]:
        if safe_path(rel).split("/")[0] not in ASSISTANT_DIRS:
            raise DevexError(f"{path} names {plain(rel)!r}, outside {', '.join(ASSISTANT_DIRS)}; not touching it")
    return data


def owners(root: Path, skip: str) -> dict[str, str]:
    """{file: tool} for files other devex installs here own."""
    out: dict[str, str] = {}
    for path in sorted((root / STATE).glob("*.json")):
        if path.stem != skip and (data := load_receipt(root, path.stem)):
            out.update({rel.lower(): path.stem for rel in data.get("files", {})})
    return out


def current_hash(path: Path) -> str | None:
    return sha256(path.read_bytes()) if path.is_file() else None


# ---- install and uninstall --------------------------------------------------------------------------

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


def made_dirs(root: Path, rel: str) -> list[str]:
    """The folders on the way to rel that do not exist yet, outermost first (so uninstall can remove them)."""
    parts, out = rel.split("/")[:-1], []
    for i in range(1, len(parts) + 1):
        if not root.joinpath(*parts[:i]).exists():
            out.append("/".join(parts[:i]))
    return out


def install(server: str, wanted: str, root: Path, *, yes: bool, force: bool, scope: str = "--project",
            out=print) -> bool:
    tool = find(tools(server), wanted)
    name = re.sub(r"[^a-z0-9-]", "", tool["name"].lower())[:60] or f"tool-{tool.get('id')}"
    files = installable(read_zip(fetch(f"{server}/blog/{urllib.parse.quote(tool['post'])}/files.zip")))
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
    out(f"Installed {name}. Remove it with: devex uninstall {name} {scope}")
    if manual:
        out(f"Steps devex does not do for you (from the tool's README):\n{manual}")
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


def main(argv: list[str] | None = None, home: Path | None = None) -> int:
    home = home or Path.home()
    parser = argparse.ArgumentParser(prog="devex", description="Install DevExAI tools.")
    parser.add_argument("--server", help="the DevExAI server, e.g. https://devexai.example:8765 (remembered)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="published tools")
    for cmd in ("install", "uninstall"):
        p = sub.add_parser(cmd, help=f"{cmd} a tool")
        p.add_argument("tool")
        where = p.add_mutually_exclusive_group(required=True)
        where.add_argument("--project", action="store_true", help="this project only (the current folder)")
        where.add_argument("--global", dest="glob", action="store_true", help="your whole machine")
        p.add_argument("--dir", type=Path, help="the project folder, if not the current one")
        p.add_argument("--yes", "-y", action="store_true", help="do not ask")
        if cmd == "install":
            p.add_argument("--force", action="store_true", help="replace files that are not from this tool")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            for t in tools(server_url(args.server, home)):
                print(f"#{t.get('id')}  {plain(t['name'])}  {plain(t.get('title', ''))}")
            return 0
        root = home if args.glob else (args.dir or Path.cwd()).resolve()
        if args.command == "install":
            install(server_url(args.server, home), args.tool, root, yes=args.yes, force=args.force,
                    scope="--global" if args.glob else "--project")
        else:
            uninstall(args.tool, root, yes=args.yes)
        return 0
    except DevexError as e:
        print(f"devex: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
