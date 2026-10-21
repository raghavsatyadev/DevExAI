"""The public blog: the index, posts, and a published tool's files (one file, or all of them as a zip).

No sign-in. A tool's files are served only for an idea that is published and whose post this is: the idea
number is taken from the post's name and the name must be the one the bot gave that idea's post, so a
hand-placed post file cannot expose an unpublished build. Files come from the idea's build record, never
from a path on disk, and a requested file name must match one of them exactly.
"""

from __future__ import annotations

import io
import re
import zipfile
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import unquote

from ..builder.build import file_map
from ..flow import post
from ..stages import Stage
from . import blog, pages

if TYPE_CHECKING:
    from .server import _Handler

_ROUTE = re.compile(r"/blog/([^/]+?)(?:/(files\.zip|files/(.+)))?")


def published_files(h: _Handler, name: str) -> dict[str, str]:
    if not blog.NAME.fullmatch(name):
        return {}
    try:
        idea = h.server.bot.store.ideas.get(int(name.split("-", 1)[0]))
    except KeyError:
        return {}
    if idea.stage is not Stage.PUBLISHED or post.filename(idea) != name:
        return {}
    return file_map(idea.build)


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
    m = _ROUTE.fullmatch(path)
    name = m.group(1) if m else ""
    if m and not m.group(2):
        page = blog.post_page(folder, name, published_files(h, name), h.server.base_url)
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
