"""Step 7: the blog post for a released tool, written as an HTML file (README section 4).

Titles and plan text come from models that read untrusted pages, so every field is HTML-escaped before it
goes into the file, and the dashboard cleans the file again when it serves it (web/clean.py), because a post
may also be edited by hand. The filename is built only from the idea number and a short ASCII slug, and the
file is never overwritten.

The file is an <article> fragment with its facts (title, date, people) in a leading comment, and one
<section> per part: what, works-with, gets, files, install. The dashboard wraps it in the blog's page.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from ..store import Idea

META = re.compile(r"\A\s*<!-- devexai-post (\{.*?\}) -->\s*", re.S)
_STEPS = re.compile(r"\s\((\d{1,2})\)\s")  # "Plan: (1) do this; (2) do that"


class PostExists(Exception):
    """A post file for this idea is already there; it is never overwritten."""


def text(value: object) -> str:
    """Plain text safe for HTML: no tags, no links, whitespace folded."""
    return escape(" ".join(str(value or "").split()), quote=False)


def paragraphs(value: object) -> str:
    """Model text as paragraphs; a numbered run like "(1) a; (2) b" becomes a list."""
    out = []
    for block in re.split(r"\n\s*\n", str(value or "")):
        parts = _STEPS.split(" " + block + " ")
        if len(parts) >= 5:  # an intro and at least two steps
            intro, steps = parts[0], parts[2::2]
            out += [f"<p>{text(intro)}</p>"] if intro.strip() else []
            out.append("<ol>" + "".join(f"<li>{text(s.rstrip(' ;'))}</li>" for s in steps) + "</ol>")
        elif block.strip():
            out.append(f"<p>{text(block)}</p>")
    return "".join(out)


def meta_comment(facts: dict) -> str:
    """The facts as JSON inside a comment; nothing in it can end the comment or open a tag."""
    raw = json.dumps(facts, ensure_ascii=False)
    return "<!-- devexai-post " + raw.replace("-", "\\u002d").replace("<", "\\u003c").replace(">", "\\u003e") + " -->"


def read_meta(html: str) -> tuple[dict[str, str], str]:
    """The facts and the article that follows them; no facts when the comment is missing or broken."""
    if m := META.match(html):
        try:
            return {k: str(v) for k, v in json.loads(m.group(1)).items()}, html[m.end():]
        except ValueError:
            pass
    return {}, html


def slug(title: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:60].strip("-")
    return s or "tool"


def filename(idea: Idea) -> str:
    return f"{idea.id:04d}-{slug(idea.title)}.html"


def _list(cls: str, heading: str, items: list) -> str:
    rows = "".join(f"<li>{text(x)}</li>" for x in items if str(x).strip())
    return f'<section class="{cls}"><h2>{heading}</h2><ul>{rows}</ul></section>' if rows else ""


def render(idea: Idea, *, maintainer: str, note: str = "", today: str | None = None) -> str:
    plan = idea.plan or {}
    title = idea.title or f"Tool #{idea.id}"
    facts = {"title": " ".join(title.split()), "date": today or datetime.now(UTC).date().isoformat(),
             "idea": idea.id, "idea_by": idea.poster or "", "maintainer": maintainer or "", "topic": idea.topic or ""}
    parts = [meta_comment(facts), "<article>", f"<h1>{text(title)}</h1>",
             f'<p class="byline">Idea by <strong>@{text(idea.poster)}</strong>. '
             f'Built and reviewed with <strong>@{text(maintainer)}</strong>.</p>']
    if plan.get("summary"):
        parts.append(f'<section class="what"><h2>What it does</h2>{paragraphs(plan["summary"])}</section>')
    parts.append(_list("works", "Works with", plan.get("assistants") or []))
    parts.append(_list("gets", "What you get", [str(x).lstrip("-* ") for x in plan.get("deliverables") or []]))
    parts.append(_list("files", "Files", [f.get("path") for f in (idea.build or {}).get("files") or []]))
    parts.append(f'<section class="install"><h2>Install</h2>' + (paragraphs(note) if note else
                 f"<p>Install steps are coming with the install command. Until then, ask "
                 f"<strong>@{text(maintainer)}</strong>.</p>") + "</section>")
    parts.append("</article>")
    return "\n".join(p for p in parts if p) + "\n"


def write(idea: Idea, folder: Path, *, maintainer: str, note: str = "", today: str | None = None) -> Path:
    """Write the post into `folder` and return its path. Refuses to overwrite an existing file."""
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = (folder / filename(idea)).resolve()
    if path.parent != folder:  # cannot happen with the slug rules; checked anyway
        raise ValueError(f"post path {path} is outside {folder}")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as f:
            f.write(render(idea, maintainer=maintainer, note=note, today=today))
    except FileExistsError:
        raise PostExists(path.name) from None
    return path


def migrate(folder: Path, store) -> list[str]:
    """Posts from before posts were HTML: write each one again as HTML from its idea, keep the old file as
    .md.old, and point the idea's link at the new file. Returns the new file names."""
    from html import unescape

    from ..web.markdown import split_front

    done = []
    for old in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        if not re.fullmatch(r"\d{4,}-[a-z0-9-]{1,60}\.md", old.name):
            continue
        try:
            idea = store.ideas.get(int(old.name.split("-", 1)[0]))
        except KeyError:
            continue
        if (folder / filename(idea)).exists():
            continue
        front, body = split_front(old.read_text(encoding="utf-8", errors="replace"))
        m = re.search(r"(?ms)^## Install\n(.*?)(?=^## |\Z)", body)
        note = unescape(re.sub(r"\\(.)", r"\1", m.group(1))).strip() if m else ""
        if note.startswith("Install steps are coming"):
            note = ""
        path = write(idea, folder, maintainer=front.get("maintainer") or idea.maintainer or "", note=note,
                     today=front.get("date"))
        old.replace(old.with_name(old.name + ".old"))
        if idea.blog_url and idea.blog_url.endswith(old.name):
            store.ideas.update(idea.id, blog_url=idea.blog_url[:-len(old.name)] + path.name)
        done.append(path.name)
    return done
