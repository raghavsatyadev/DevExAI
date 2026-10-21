"""Cleans a blog post's HTML before the dashboard serves it.

Posts are served on the dashboard's own address, next to its sign-in cookie, and a post file may have
been edited by hand. The page policy already stops scripts; this also stops what it does not cover:
forms, frames, <meta> refreshes, <style>, event and style attributes, and links that are not web links.
Only the tags a post needs survive, with plain class names; everything else becomes text.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

TAGS = {"article", "section", "h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "b", "em", "i", "code",
        "pre", "br", "hr", "a", "blockquote", "div", "span", "table", "thead", "tbody", "tr", "th", "td"}
VOID = {"br", "hr"}
DROP = {"script", "style", "template", "iframe", "object", "embed", "noscript", "textarea", "title", "svg", "math",
        "select", "head"}  # these go with everything inside them
_CLASS = re.compile(r"[a-z][a-z0-9-]{0,30}")
_HREF = re.compile(r"(?i)(https?://|/(?!/)|#)[^\s\"'<>`\\]*")


def _attrs(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    out = []
    for key, value in attrs:
        value = value or ""
        if key == "class":
            if names := [c for c in value.split() if _CLASS.fullmatch(c)]:
                out.append(f'class="{" ".join(names)}"')
        elif key == "href" and tag == "a" and _HREF.fullmatch(value.strip()):
            out.append(f'href="{escape(value.strip())}"')
        elif key == "data-copy" and tag == "code" and not value:  # click-to-copy inline code
            out.append('data-copy="" title="Click to copy"')
    return "".join(" " + a for a in out)


class _Cleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []
        self.dropping = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP:
            self.dropping += 1
        elif not self.dropping and tag in TAGS:
            self.out.append(f"<{tag}{_attrs(tag, attrs)}>")
            if tag not in VOID:
                self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if not self.dropping and tag in VOID:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in DROP:
            self.dropping = max(0, self.dropping - 1)
        elif not self.dropping and tag in self.open:
            while self.open:  # close what was left open inside it too
                last = self.open.pop()
                self.out.append(f"</{last}>")
                if last == tag:
                    break

    def handle_data(self, data):
        if not self.dropping:
            self.out.append(escape(data, quote=False))


def clean(html: str) -> str:
    parser = _Cleaner()
    parser.feed(html)
    parser.close()
    return "".join(parser.out) + "".join(f"</{t}>" for t in reversed(parser.open))
