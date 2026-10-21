"""The company blog, served by the dashboard at /blog until a real blog site exists.

Anyone who can reach the dashboard can read it, without signing in: posts are for every colleague.
Posts are the HTML files in [blog] dir (flow/post.py writes them). A post file may have been edited by hand,
so it is cleaned (clean.py) before it is served, and a tool's README is model output rendered from a small
Markdown subset (markdown.py). A published tool's files are shown with copy and download buttons.
"""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Iterator
from html import escape
from itertools import count
from pathlib import Path
from urllib.parse import quote

from ..flow.post import read_meta
from .blog_theme import BLOG_CSS
from .clean import clean
from .markdown import code_block, inline, split_front, to_html  # noqa: F401  (used by get_routes and tests)
from .theme import CSS

NAME = re.compile(r"\d{4,}-[a-z0-9-]{1,60}\.html")  # post.filename(): idea number + ASCII slug
OLD_NAME = re.compile(r"\d{4,}-[a-z0-9-]{1,60}\.md")  # posts from before they were HTML
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
SHAPES = '<span class="shape" aria-hidden="true"></span><span class="shape two" aria-hidden="true"></span>'


def _read(folder: Path, name: str) -> tuple[dict[str, str], str] | None:
    """The post's facts and its cleaned HTML, or None."""
    if not NAME.fullmatch(name):
        return None
    path = folder / name
    try:
        if path.resolve().parent != folder.resolve() or not path.is_file() or path.stat().st_size > MAX_POST_BYTES:
            return None
        facts, html = read_meta(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return facts, clean(html)


def _page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} - DevExAI</title>'
            f'<style>{CSS}{BLOG_CSS}</style></head><body><header><a class="brand" href="/blog"><span class="mark" '
            f'aria-hidden="true"></span>DevExAI blog</a><span class="grow"></span><nav><a href="/blog">All posts</a>'
            f'<a href="/get">Get DevExAI</a><a href="/">Dashboard</a></nav></header><main>{body}</main>'
            f'<script>{SCRIPT}</script></body></html>')


def hero(eyebrow: str, title_html: str, rest: str = "") -> str:
    return (f'<section class="blog-hero">{SHAPES}<p class="eyebrow">{eyebrow}</p>'
            f'<h1>{title_html}</h1>{rest}</section>')


def index_page(folder: Path) -> str:
    names = sorted((p.name for p in folder.glob("*.html") if NAME.fullmatch(p.name)), reverse=True) \
        if folder.is_dir() else []
    cards = []
    for name in names[:MAX_POSTS]:
        if (post := _read(folder, name)) is None:
            continue
        facts = post[0]
        topic = f'<span class="chip">{escape(facts["topic"])}</span>' if facts.get("topic") else ""
        by = f" · idea by @{escape(facts['idea_by'])}" if facts.get("idea_by") else ""
        cards.append(f'<a class="post-card" href="/blog/{name}">{topic}<h2>{escape(facts.get("title") or name)}</h2>'
                     f'<p class="muted">{escape(facts.get("date", ""))}{by}</p>'
                     f'<span class="go">Read and install &rarr;</span></a>')
    body = (f'<div class="grid">{"".join(cards)}</div>' if cards else
            '<div class="empty-blog"><b>No tools published yet</b><p class="muted">Ideas show up here once a '
            'maintainer releases the tool.</p></div>')
    lede = ('<p class="lede">Tools built from colleagues\' ideas, reviewed by a maintainer and ready to '
            'install with one command.</p>')
    return _page("Blog", hero("DevExAI blog", "Published tools", lede) + body)


def tool_slug(name: str) -> str:
    """The folder name a downloaded tool unpacks into: the post name without number and extension."""
    return re.sub(r"^\d+-", "", re.sub(r"\.(html|md)$", "", name))


def _section(html: str, cls: str) -> tuple[str, str]:
    """Takes <section class="cls"> out of the post: (its content without the heading, the rest)."""
    m = re.search(rf'<section class="{cls}">(.*?)</section>', html, re.S)
    if not m:
        return "", html
    return re.sub(r"^\s*<h2>.*?</h2>", "", m.group(1), flags=re.S), html[:m.start()] + html[m.end():]


def _install_panel(slug: str, base: str, origin: str, note: str, ids: Iterator[int]) -> str:
    note = f'<h3>Notes from the maintainer</h3><div class="note">{note}</div>' if note.strip() else ""
    return (f'<div class="panel lift" id="install"><h2>Install it</h2>'
            f'<p><b>This project only</b>: run it in the project folder. The files can be committed so the '
            f'whole team gets them.</p>{code_block(f"devexai install {slug}", ids)}'
            f'<p><b>My whole machine</b>: the files go into your home folder and work in every project.</p>'
            f'{code_block(f"devexai install {slug} --global", ids)}'
            f'<p>It shows every change and asks first. To remove it: <code data-copy="" title="Click to copy">'
            f'devexai uninstall {slug}</code> (add <code>--global</code> if you installed it that way).</p>{note}'
            f'<p class="muted">First time on this computer? <a href="{origin}/get">Get DevExAI for '
            f'developers</a>, once.</p></div>'
            f'<div class="panel"><h2>Just the files</h2><a class="btn big" href="{base}/files.zip" download>'
            f'Download all files (.zip)</a><p class="muted">Or unpack them with one command: '
            f'<a href="#get">see below</a>.</p></div>')


def _files_panels(slug: str, base: str, zip_url: str, files: dict[str, str], ids: Iterator[int]) -> str:
    # --ssl-no-revoke: Windows curl also asks the CA for revocation lists, which a company's own CA often
    # does not publish; the certificate itself is still checked.
    win = (f"curl.exe --ssl-no-revoke -fLo {slug}.zip {zip_url}; "
           f"if ($?) {{ mkdir {slug} -Force > $null; tar -xf {slug}.zip -C {slug}; del {slug}.zip }}")
    nix = f"curl -fLo {slug}.zip {zip_url} && unzip -d {slug} {slug}.zip && rm {slug}.zip"
    out = ""
    if readme := next((files[p] for p in files if p.lower() == "readme.md"), None):
        out += (f'<div class="panel" id="readme"><h2>How to set it up</h2><p class="muted">From the tool\'s '
                f'README.md.</p>{to_html(readme, ids)}</div>')
    out += (f'<div class="panel" id="get"><h2>Get the files</h2><p>Download and unpack them into a '
            f'<code data-copy="" title="Click to copy">{slug}</code> folder with one command.</p>'
            f'<h3>Windows (PowerShell)</h3>{code_block(win, ids)}<h3>macOS or Linux</h3>{code_block(nix, ids)}'
            f'<p class="muted">These work on computers that trust this site\'s certificate.</p></div>')
    rows = []
    for path, content in files.items():
        n = next(ids)
        size = len(content.encode("utf-8"))
        rows.append(f'<details class="file"><summary>{escape(path)} <span class="muted">({size:,} bytes)</span>'
                    f'</summary><div class="row"><a class="btn tonal" href="{base}/files/{quote(path)}" download>'
                    f'Download</a><button type="button" class="tonal" data-copy="f{n}">Copy</button></div>'
                    f'<pre id="f{n}">{escape(content, quote=False)}</pre></details>')
    return out + f'<div class="panel" id="files"><h2>Files</h2>{"".join(rows)}</div>'


def post_page(folder: Path, name: str, files: dict[str, str] | None = None, origin: str = "") -> str | None:
    """The post as a page, or None when there is no such post. `files`: the published tool's files, if any."""
    if (post := _read(folder, name)) is None:
        return None
    facts, html = post
    title = facts.get("title") or name  # plain text, for the browser tab
    html = re.sub(r"</?article>", "", html)
    if m := re.search(r"<h1>(.*?)</h1>", html, re.S):
        heading, html = m.group(1), html[:m.start()] + html[m.end():]
    else:
        heading = escape(title)
    byline = ""
    if m := re.search(r'<p class="byline">.*?</p>', html, re.S):
        byline, html = m.group(0), html[:m.start()] + html[m.end():]
    chips = "".join(f'<span class="chip">{escape(facts[k])}</span>' for k in ("topic", "date") if facts.get(k))
    rest = f'<div class="chips">{chips}</div>' if chips else ""
    ids = count(1)
    if not files:
        page = hero("DevExAI blog", heading, byline + rest) + f'<div class="layout single"><div class="post">{html}</div></div>'
        return _page(title, page)
    slug, base = tool_slug(name), f"/blog/{name}"
    _, html = _section(html, "files")  # the Files panel below replaces the list
    note, html = _section(html, "install")
    links = (f'<div class="row"><a class="btn" href="#install">Install it</a><a class="btn tonal" '
             f'href="{base}/files.zip" download>Download all files (.zip)</a></div>')
    main = f'<div class="post">{html}</div>' + _files_panels(slug, base, f"{origin}{base}/files.zip", files, ids)
    side = _install_panel(slug, base, origin, note, ids)
    return _page(title, hero("DevExAI blog", heading, byline + rest + links)
                 + f'<div class="layout"><div>{main}</div><aside class="side">{side}</aside></div>')
