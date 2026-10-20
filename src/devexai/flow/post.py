"""Step 7: the blog post for a released tool, written as a Markdown file (README section 4).

Titles and plan text come from models that read untrusted pages, so every field is escaped before it
goes into the file: the post will be rendered on a website. The filename is built only from the idea
number and a short ASCII slug, and the file is never overwritten.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from ..store import Idea

_MD_INLINE = re.compile(r"([\\`*_{}\[\]|~])")
_MD_LINE_START = re.compile(r"^(\d*)([#+.)=-])")  # headings, list markers ("- x", "1. x")
_AUTOLINK = re.compile(r"(?i)(?<=\w)(:)(?=//)|(?<=\bwww)(\.)")  # GitHub-style bare-URL links


class PostExists(Exception):
    """A post file for this idea is already there; it is never overwritten."""


def md(text: object) -> str:
    """Plain text safe for Markdown: no HTML, no links, no formatting from the source."""
    lines = (" ".join(line.split()) for line in str(text or "").splitlines())
    out = (_AUTOLINK.sub(lambda m: "\\" + m.group(0), _MD_INLINE.sub(r"\\\1", escape(line, quote=False)))
           for line in lines if line)
    return "\n".join(_MD_LINE_START.sub(r"\1\\\2", line) for line in out)


def _front(value: object) -> str:
    """A YAML scalar (JSON is valid YAML) with no angle brackets for a site template to trip on."""
    return json.dumps(re.sub(r"[<>\r\n]", " ", str(value or "")), ensure_ascii=False)


def slug(title: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:60].strip("-")
    return s or "tool"


def filename(idea: Idea) -> str:
    return f"{idea.id:04d}-{slug(idea.title)}.md"


def render(idea: Idea, *, maintainer: str, note: str = "", today: str | None = None) -> str:
    plan = idea.plan or {}
    title = idea.title or f"Tool #{idea.id}"
    date = today or datetime.now(UTC).date().isoformat()
    front = "\n".join(f"{k}: {v}" for k, v in (
        ("title", _front(title)), ("date", date), ("idea", idea.id), ("idea_by", _front(idea.poster)),
        ("maintainer", _front(maintainer)), ("topic", _front(idea.topic)),
    ))
    parts = [f"---\n{front}\n---", f"# {md(title)}",
             f"**Idea by @{md(idea.poster)}.** Built and reviewed with @{md(maintainer)}."]
    if plan.get("summary"):
        parts += ["## What it does", md(plan["summary"])]
    for heading, key in (("## Works with", "assistants"), ("## What you get", "deliverables")):
        if items := [md(x) for x in plan.get(key) or [] if str(x).strip()]:
            parts += [heading, "\n".join(f"- {x}" for x in items)]
    parts += ["## Install", md(note) if note else
              f"Install steps are coming with the install command. Until then, ask @{md(maintainer)}."]
    return "\n\n".join(parts) + "\n"


def write(idea: Idea, folder: Path, *, maintainer: str, note: str = "") -> Path:
    """Write the post into `folder` and return its path. Refuses to overwrite an existing file."""
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = (folder / filename(idea)).resolve()
    if path.parent != folder:  # cannot happen with the slug rules; checked anyway
        raise ValueError(f"post path {path} is outside {folder}")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as f:
            f.write(render(idea, maintainer=maintainer, note=note))
    except FileExistsError:
        raise PostExists(path.name) from None
    return path
