"""The company blog, served by the dashboard at /blog until a real blog site exists.

Anyone who can reach the dashboard can read it, without signing in: posts are for every colleague.
Posts are the Markdown files in [blog] dir. Only the small subset that post.render writes is turned into
HTML (headings, paragraphs, "- " lists, **bold**, backslash escapes); everything else is shown as text.
A post file may also have been edited by hand, so every piece of text is escaped before it is sent.
"""

from __future__ import annotations

import json
import re
from html import escape, unescape
from pathlib import Path

from .theme import CSS

NAME = re.compile(r"\d{4,}-[a-z0-9-]{1,60}\.md")  # post.filename(): idea number + ASCII slug
MAX_POST_BYTES = 512 * 1024
MAX_POSTS = 500


def _text(raw: str) -> str:
    return escape(unescape(raw), quote=False)


def inline(s: str) -> str:
    """Backslash escapes and **bold**; all other characters are plain text."""
    out, buf, bold, i = [], [], False, 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            buf.append(s[i + 1])
            i += 2
        elif s.startswith("**", i):
            out += [_text("".join(buf)), "</strong>" if bold else "<strong>"]
            buf, bold, i = [], not bold, i + 2
        else:
            buf.append(s[i])
            i += 1
    out.append(_text("".join(buf)))
    return "".join(out) + ("</strong>" if bold else "")


def split_front(text: str) -> tuple[dict[str, str], str]:
    """The `---` block at the top (one `key: value` per line, values JSON or plain) and the body."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---" or "---" not in (x.strip() for x in lines[1:]):
        return {}, text
    end = next(i for i, x in enumerate(lines[1:], 1) if x.strip() == "---")
    front = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            try:
                front[key.strip()] = str(json.loads(value))
            except ValueError:
                front[key.strip()] = value.strip()
    return front, "\n".join(lines[end + 1:])


def to_html(body: str) -> str:
    html, para, items = [], [], []

    def flush() -> None:
        if para:
            html.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para.clear()
        if items:
            html.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            items.clear()

    for line in body.split("\n"):
        line = line.rstrip()
        if m := re.match(r"(#{1,3}) (.*)", line):
            flush()
            level = len(m.group(1)) + 1  # the page title is the only <h1>
            html.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
        elif line.startswith("- "):
            if para:
                flush()
            items.append(line[2:])
        elif not line:
            flush()
        else:
            if items:
                flush()
            para.append(line)
    flush()
    return "\n".join(html)


def _read(folder: Path, name: str) -> tuple[dict[str, str], str] | None:
    if not NAME.fullmatch(name):
        return None
    path = folder / name
    try:
        if path.resolve().parent != folder.resolve() or not path.is_file() or path.stat().st_size > MAX_POST_BYTES:
            return None
        return split_front(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} - DevExAI</title>'
            f'<style>{CSS}</style></head><body><header><a class="brand" href="/blog"><span class="mark" '
            f'aria-hidden="true"></span>DevExAI blog</a><span class="grow"></span><nav><a href="/blog">All posts</a>'
            f'<a href="/">Dashboard</a></nav></header><main>{body}</main></body></html>')


def index_page(folder: Path) -> str:
    names = sorted((p.name for p in folder.glob("*.md") if NAME.fullmatch(p.name)), reverse=True) \
        if folder.is_dir() else []
    rows = []
    for name in names[:MAX_POSTS]:
        if (post := _read(folder, name)) is None:
            continue
        front = post[0]
        by = f" · idea by @{escape(front['idea_by'])}" if front.get("idea_by") else ""
        rows.append(f'<li><a href="/blog/{name}">{escape(front.get("title") or name)}</a>'
                    f'<span class="muted"> {escape(front.get("date", ""))}{by}</span></li>')
    body = "<ul>" + "".join(rows) + "</ul>" if rows else "<p class=muted>No tools published yet.</p>"
    return _page("Blog", f'<div class="card"><h1>Published tools</h1>{body}</div>')


def post_page(folder: Path, name: str) -> str | None:
    """The post as HTML, or None when there is no such post."""
    if (post := _read(folder, name)) is None:
        return None
    front, body = post
    title = front.get("title") or name  # plain text, for the browser tab
    if m := re.match(r"\s*# ([^\n]*)\n?", body):  # the post's own heading keeps characters the front matter drops
        heading, body = inline(m.group(1)), body[m.end():]
    else:
        heading = escape(title)
    return _page(title, f'<article class="card"><h1>{heading}</h1>{to_html(body)}</article>')
