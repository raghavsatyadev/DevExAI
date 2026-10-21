"""The company blog, served by the dashboard at /blog until a real blog site exists.

Anyone who can reach the dashboard can read it, without signing in: posts are for every colleague.
Posts are the Markdown files in [blog] dir. Only a small subset is turned into HTML (headings, paragraphs,
"- " and "1. " lists, **bold**, `code`, fenced code, backslash escapes); everything else is shown as text.
A post file may also have been edited by hand, and a tool's README is model output, so every piece of
text is escaped before it is sent. A published tool's files are shown with copy and download buttons.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Iterator
from html import escape, unescape
from itertools import count
from pathlib import Path
from urllib.parse import quote

from .theme import CSS

NAME = re.compile(r"\d{4,}-[a-z0-9-]{1,60}\.md")  # post.filename(): idea number + ASCII slug
MAX_POST_BYTES = 512 * 1024
MAX_POSTS = 500

# Copy buttons. The page policy allows only this exact script (by its hash), so no inline handlers.
SCRIPT = """
document.addEventListener("click", function (e) {
  var b = e.target.closest("[data-copy]");
  if (!b) return;
  var src = b.dataset.copy ? document.getElementById(b.dataset.copy) : b;
  var text = src ? src.textContent : "";
  function done() {
    b.classList.add("copied");
    if (b.tagName === "BUTTON") b.textContent = "Copied";
    setTimeout(function () {
      b.classList.remove("copied");
      if (b.tagName === "BUTTON") b.textContent = "Copy";
    }, 1500);
  }
  function fallback() {
    var t = document.createElement("textarea");
    t.value = text;
    t.style.position = "fixed";
    t.style.opacity = "0";
    document.body.appendChild(t);
    t.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (err) {}
    t.remove();
    if (ok) done();
  }
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, fallback);
  else fallback();
});
"""
SCRIPT_HASH = "'sha256-" + base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode() + "'"

_CSS = """
.code{position:relative}.code pre{padding-right:96px}
.code button.copy{position:absolute;top:6px;right:6px;min-height:32px;padding:4px 14px}
code{font:13px/1.4 var(--mono);background:var(--surface-container);padding:1px 6px;border-radius:6px;cursor:copy}
code.copied,button.copied{background:var(--success-container);color:var(--on-success-container)}
a.btn{display:inline-flex;align-items:center;font:600 14px/20px var(--font);min-height:40px;padding:10px 22px;
border-radius:999px;background:var(--primary);color:var(--on-primary);text-decoration:none}
a.btn.tonal{background:var(--secondary-container);color:var(--on-secondary-container)}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0}
details.file>summary{font:14px/1.5 var(--mono)}
"""


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
            f'<style>{CSS}{_CSS}</style></head><body><header><a class="brand" href="/blog"><span class="mark" '
            f'aria-hidden="true"></span>DevExAI blog</a><span class="grow"></span><nav><a href="/blog">All posts</a>'
            f'<a href="/">Dashboard</a></nav></header><main>{body}</main><script>{SCRIPT}</script></body></html>')


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


def tool_slug(name: str) -> str:
    """The folder name a downloaded tool unpacks into: the post name without number and .md."""
    return re.sub(r"^\d+-", "", name.removesuffix(".md"))


def _tool_cards(name: str, files: dict[str, str], origin: str, ids: Iterator[int]) -> str:
    slug, base = tool_slug(name), f"/blog/{name}"
    zip_url = f"{origin}{base}/files.zip"
    # --ssl-no-revoke: Windows curl also asks the CA for revocation lists, which a company's own CA often
    # does not publish; the certificate itself is still checked.
    win = (f"curl.exe --ssl-no-revoke -fLo {slug}.zip {zip_url}; "
           f"if ($?) {{ mkdir {slug} -Force > $null; tar -xf {slug}.zip -C {slug}; del {slug}.zip }}")
    nix = f"curl -fLo {slug}.zip {zip_url} && unzip -d {slug} {slug}.zip && rm {slug}.zip"
    get = (f'<div class="card" id="get"><h2>Get it</h2>'
           f'<div class="row"><a class="btn" href="{base}/files.zip" download>Download all files (.zip)</a></div>'
           f'<p>Or download and unpack it into a <code data-copy="" title="Click to copy">{slug}</code> folder '
           f'with one command.</p><p><b>Windows (PowerShell)</b></p>{code_block(win, ids)}'
           f'<p><b>macOS or Linux</b></p>{code_block(nix, ids)}'
           f'<p class="muted">These work on computers that trust this site\'s certificate.</p>')
    if readme := next((files[p] for p in files if p.lower() == "readme.md"), None):
        get += f'<h2>How to set it up</h2><p class="muted">From the tool\'s README.md.</p>{to_html(readme, ids)}'
    rows = []
    for path, content in files.items():
        n = next(ids)
        size = len(content.encode("utf-8"))
        rows.append(f'<details class="file"><summary>{escape(path)} <span class="muted">({size:,} bytes)</span>'
                    f'</summary><div class="row"><a class="btn tonal" href="{base}/files/{quote(path)}" download>'
                    f'Download</a><button type="button" class="tonal" data-copy="f{n}">Copy</button></div>'
                    f'<pre id="f{n}">{escape(content, quote=False)}</pre></details>')
    return get + f'</div><div class="card" id="files"><h2>Files</h2>{"".join(rows)}</div>'


def post_page(folder: Path, name: str, files: dict[str, str] | None = None, origin: str = "") -> str | None:
    """The post as HTML, or None when there is no such post. `files`: the published tool's files, if any."""
    if (post := _read(folder, name)) is None:
        return None
    front, body = post
    title = front.get("title") or name  # plain text, for the browser tab
    if m := re.match(r"\s*# ([^\n]*)\n?", body):  # the post's own heading keeps characters the front matter drops
        heading, body = inline(m.group(1)), body[m.end():]
    else:
        heading = escape(title)
    ids = count(1)
    if not files:
        return _page(title, f'<article class="card"><h1>{heading}</h1>{to_html(body, ids)}</article>')
    body = re.sub(r"(?ms)^## Files\n.*?(?=^## |\Z)", "", body)  # the Files card below replaces the list
    links = (f'<div class="row"><a class="btn" href="/blog/{name}/files.zip" download>Download all files (.zip)</a>'
             f'<a class="btn tonal" href="#get">How to get it</a><a class="btn tonal" href="#files">See the files</a></div>')
    article = f'<article class="card"><h1>{heading}</h1>{links}{to_html(body, ids)}</article>'
    return _page(title, article + _tool_cards(name, files, origin, ids))
