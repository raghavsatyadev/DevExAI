"""Fetches linked pages as plain text. Runs in its own process (see fetch.py), never in the bot.

stdin:  {"urls": [...], "max_bytes": int, "timeout": int, "max_chars": int}
stdout: {"pages": [{"url", "ok", "text" | "error"}]}

Only http(s); every DNS answer that is not a public address is dropped, so neither the first
request nor any redirect can reach localhost, the LAN or cloud metadata endpoints.
"""

from __future__ import annotations

import codecs
import ipaddress
import json
import re
import socket
import sys
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

_real_getaddrinfo = socket.getaddrinfo


def _public_only_getaddrinfo(host, *args, **kwargs):
    answers = [a for a in _real_getaddrinfo(host, *args, **kwargs) if _is_public(a[4][0])]
    if not answers:
        raise OSError(f"{host} does not resolve to a public address")
    return answers


def _is_public(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr.split("%", 1)[0]).is_global
    except ValueError:
        return False


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme not in ("http", "https"):
            raise OSError(f"redirect to non-http(s) URL refused: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def fetch_one(opener, url: str, max_bytes: int, timeout: int, max_chars: int) -> dict:
    if urlsplit(url).scheme not in ("http", "https"):
        return {"url": url, "ok": False, "error": "only http(s) links are opened"}
    req = urllib.request.Request(url, headers={"User-Agent": "DevExAI-safety-gate/0.1"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            ctype = resp.headers.get_content_type()
            if not (ctype.startswith("text/") or ctype in ("application/json", "application/xhtml+xml")):
                return {"url": url, "ok": False, "error": f"not a text page ({ctype})"}
            body = resp.read(max_bytes + 1)
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as e:  # report every failure to the gate instead of crashing
        return {"url": url, "ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
    truncated = len(body) > max_bytes
    try:
        codecs.lookup(charset)
    except LookupError:  # a page can declare any charset name
        charset = "utf-8"
    text = body[:max_bytes].decode(charset, errors="replace")
    if "html" in ctype:
        text = html_to_text(text)
    if len(text) > max_chars:
        text, truncated = text[:max_chars], True
    return {"url": url, "ok": True, "text": text, "truncated": truncated}


def make_opener() -> urllib.request.OpenerDirector:
    # An empty ProxyHandler stops urllib reading system (e.g. Windows registry) proxies:
    # a proxy would resolve the host itself and skip the public-address check.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _SafeRedirects)


def main() -> None:
    job = json.loads(sys.stdin.read())
    socket.getaddrinfo = _public_only_getaddrinfo
    opener = make_opener()
    pages = [
        fetch_one(opener, u, int(job["max_bytes"]), int(job["timeout"]), int(job["max_chars"]))
        for u in job["urls"]
    ]
    sys.stdout.write(json.dumps({"pages": pages}))


if __name__ == "__main__":
    main()
