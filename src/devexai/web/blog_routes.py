"""The public blog: the index, posts, and a published tool's files (one file, or all of them as a zip).

No sign-in. A tool's files are served only for an idea that is published and whose post this is: the idea
number is taken from the post's name and the name must be the one the bot gave that idea's post, so a
hand-placed post file cannot expose an unpublished build. Files come from the idea's build record, never
from a path on disk, and a requested file name must match one of them exactly.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import unquote

from devexai_cli.files import installable

from ..builder.build import file_map
from ..flow import post
from ..stages import Stage
from . import blog, pages

if TYPE_CHECKING:
    from .server import _Handler

_ROUTE = re.compile(r"/blog/([^/]+?)(?:/(files\.zip|files/(.+)))?")


def published_idea(h: _Handler, name: str):
    """The published idea whose post this is, or None."""
    if not blog.NAME.fullmatch(name):
        return None
    try:
        idea = h.server.bot.store.ideas.get(int(name.split("-", 1)[0]))
    except KeyError:
        return None
    if idea.stage is not Stage.PUBLISHED or post.filename(idea) != name:
        return None
    return idea


def published_files(h: _Handler, name: str) -> dict[str, str]:
    idea = published_idea(h, name)
    return file_map(idea.build) if idea else {}


def by_hand_steps(idea, files: dict[str, str]) -> str | None:
    """None when `devexai install` can add the tool (it has .claude/, .gemini/ or .codex/ files, the same
    test the command uses); otherwise the tool's own install steps from its build record."""
    if installable(dict.fromkeys(files, b"")):
        return None
    return str((idea.build or {}).get("install") or "")


def tool_name(idea, blog_dir) -> str:
    """The name `devexai install` knows a published tool by; empty when there is nothing to install."""
    name = post.filename(idea)
    if idea.stage is Stage.PUBLISHED and (blog_dir / name).is_file() and file_map(idea.build):
        return blog.tool_slug(name)
    return ""


def tool_list(h: _Handler) -> list[dict]:
    """Published tools for `devexai list` / `devexai install`: one idea, one tool, one name."""
    out = []
    for idea in h.server.bot.store.ideas.in_stage(Stage.PUBLISHED):
        name = post.filename(idea)
        if slug := tool_name(idea, h.server.bot.settings.blog.dir):
            out.append({"id": idea.id, "name": slug, "post": name, "title": idea.title or "",
                        "install": (idea.build or {}).get("install", "")})
    return out


def zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def blog_get(h: _Handler, path: str, base_csp: str) -> None:
    folder = h.server.bot.settings.blog.dir
    html = {"Content-Security-Policy": f"{base_csp}; script-src {blog.SCRIPT_HASH}"}
    if path in ("/blog", "/blog/"):
        return h._send(HTTPStatus.OK, blog.index_page(folder), html)
    if path == "/blog/tools.json":
        return h._send_bytes(HTTPStatus.OK, json.dumps({"tools": tool_list(h)}).encode(), "application/json", {})
    if path == "/blog/devex.py":  # the old install script: the developer command replaced it
        return h._redirect("/get")
    m = _ROUTE.fullmatch(path)
    name = m.group(1) if m else ""
    if blog.OLD_NAME.fullmatch(name):  # links in chat from before posts were HTML
        return h._redirect(f"/blog/{name[:-3]}.html" + path[len("/blog/") + len(name):])
    if m and not m.group(2):
        idea = published_idea(h, name)
        files = file_map(idea.build) if idea else {}
        page = blog.post_page(folder, name, files, h.server.base_url, by_hand_steps(idea, files) if files else None)
        if page:
            return h._send(HTTPStatus.OK, page, html)
    elif m and (files := published_files(h, name)):
        if m.group(2) == "files.zip":
            return h._send_bytes(HTTPStatus.OK, zip_bytes(files), "application/zip",
                                 {"Content-Disposition": f'attachment; filename="{blog.tool_slug(name)}.zip"'})
        want = unquote(m.group(3))
        if want in files:
            filename = want.rsplit("/", 1)[-1]  # builder file names are [A-Za-z0-9._-] only
            return h._send_bytes(HTTPStatus.OK, files[want].encode("utf-8"), "text/plain; charset=utf-8",
                                 {"Content-Disposition": f'attachment; filename="{filename}"'})
    h._send(HTTPStatus.NOT_FOUND, pages.message_page("Not found", "No such post or file."))
