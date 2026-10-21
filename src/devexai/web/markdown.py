"""The small Markdown subset the blog renders: a tool's README.md, and posts from before posts were HTML.

Headings, paragraphs, "- " and "1. " lists, **bold**, `code`, fenced code and backslash escapes become HTML;
everything else is shown as text. The text is model output, so every piece of it is escaped.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from html import escape, unescape
from itertools import count


def _text(raw: str) -> str:
    return escape(unescape(raw), quote=False)


def inline(s: str) -> str:
    """Backslash escapes, **bold** and `code` (click to copy); all other characters are plain text."""
    out, buf, bold, i = [], [], False, 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            buf.append(s[i + 1])
            i += 2
        elif s[i] == "`" and (end := s.find("`", i + 1)) > i + 1:
            code = escape(s[i + 1:end], quote=False)
            out += [_text("".join(buf)), f'<code data-copy="" title="Click to copy">{code}</code>']
            buf, i = [], end + 1
        elif s.startswith("**", i):
            out += [_text("".join(buf)), "</strong>" if bold else "<strong>"]
            buf, bold, i = [], not bold, i + 2
        else:
            buf.append(s[i])
            i += 1
    out.append(_text("".join(buf)))
    return "".join(out) + ("</strong>" if bold else "")


def code_block(text: str, ids: Iterator[int]) -> str:
    """Code shown as written (escaped only), with a Copy button."""
    n = next(ids)
    return (f'<div class="code"><pre id="c{n}">{escape(text, quote=False)}</pre>'
            f'<button type="button" class="tonal copy" data-copy="c{n}">Copy</button></div>')


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


def to_html(body: str, ids: Iterator[int] | None = None) -> str:
    ids = ids or count(1)
    html, para, items, fence = [], [], [], None
    kind = "ul"

    def flush() -> None:
        if para:
            html.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para.clear()
        if items:
            html.append(f"<{kind}>" + "".join(f"<li>{'<br>'.join(inline(x) for x in item)}</li>"
                                              for item in items) + f"</{kind}>")
            items.clear()

    for line in body.replace("\r\n", "\n").split("\n"):
        if fence is not None:
            if line.strip().startswith("```"):
                html.append(code_block("\n".join(fence), ids))
                fence = None
            else:
                fence.append(line)
            continue
        line = line.rstrip()
        if line.lstrip().startswith("```"):
            flush()
            fence = []
        elif m := re.match(r"(#{1,3}) (.*)", line):
            flush()
            level = len(m.group(1)) + 1  # the page title is the only <h1>
            html.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
        elif m := re.match(r"(- |\d{1,3}\. )(.*)", line):
            new = "ul" if m.group(1) == "- " else "ol"
            if para or (items and new != kind):
                flush()
            kind = new
            items.append([m.group(2)])
        elif items and line.startswith("  ") and line.strip():  # a list item's next line
            items[-1].append(line.strip())
        elif not line:
            flush()
        else:
            if items:
                flush()
            para.append(line)
    if fence is not None:
        html.append(code_block("\n".join(fence), ids))
    flush()
    return "\n".join(html)
