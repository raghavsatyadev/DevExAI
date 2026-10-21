"""Talking to the DevExAI server: which one, trusting its certificate, and fetching from it.

The server and its certificate authority (the company's own, when the dashboard uses one) are kept in
~/.devex/: server.txt and ca.pem. Every request trusts the system's certificates plus that ca.pem.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STATE = ".devex"
MAX_DOWNLOAD = 4_000_000
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")  # colour and cursor codes, removed whole
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # keeps tab and newline; drops terminal escapes


class DevexError(Exception):
    """Something the person can fix; printed without a traceback."""


def plain(text: object) -> str:
    """Server text is shown in a terminal: no control characters, so no escape sequences."""
    return _CONTROL.sub("", _ANSI.sub("", str(text)))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_file(home: Path) -> Path:
    return home / STATE / "server.txt"


def ca_file(home: Path) -> Path:
    return home / STATE / "ca.pem"


def check_url(url: str) -> str:
    if urllib.parse.urlsplit(url).scheme not in ("http", "https") or not urllib.parse.urlsplit(url).hostname:
        raise DevexError(f"not a web address: {plain(url)!r}. It looks like https://<server>:8765")
    return url.strip().rstrip("/")


def save_server(url: str, home: Path) -> str:
    url = check_url(url)
    config_file(home).parent.mkdir(parents=True, exist_ok=True)
    config_file(home).write_text(url + "\n", encoding="utf-8")
    return url


def server_url(given: str | None, home: Path) -> str:
    """--server, else DEVEX_SERVER, else the saved one. A given one is saved for next time."""
    if given:
        return save_server(given, home)
    url = os.environ.get("DEVEX_SERVER", "")
    if not url and config_file(home).is_file():
        url = config_file(home).read_text(encoding="utf-8").strip()
    if not url:
        raise DevexError("which DevExAI server? Run: devexai connect https://<server>:<port> "
                         "(the blog's address, without /blog)")
    return check_url(url)


def context(home: Path) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # Python 3.13+ also demands strict RFC 5280 fields (e.g. Authority Key Identifier) that company CAs made
    # with older tools often lack; the chain, the names and the dates are still checked.
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    if ca_file(home).is_file():
        ctx.load_verify_locations(cafile=str(ca_file(home)))
    return ctx


def fetch(url: str, home: Path, limit: int = MAX_DOWNLOAD, ctx: ssl.SSLContext | None = None) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30, context=ctx or context(home)) as resp:  # noqa: S310
            data = resp.read(limit + 1)
    except urllib.error.HTTPError as e:
        raise DevexError(f"the server answered {e.code} for {url}") from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ssl.SSLCertVerificationError):
            server = url.split("/", 3)[:3]
            raise DevexError(f"this computer does not trust {url}'s certificate yet. Run: devexai connect "
                             f"{'/'.join(server)}") from None
        raise DevexError(f"could not reach {url}: {reason}") from None
    if len(data) > limit:
        raise DevexError(f"{url} is bigger than {limit} bytes")
    return data


def fetch_json(url: str, home: Path) -> dict:
    try:
        data = json.loads(fetch(url, home))
    except ValueError:
        raise DevexError(f"{url} is not readable") from None
    if not isinstance(data, dict):
        raise DevexError(f"{url} is not readable")
    return data


def tools(server: str, home: Path) -> list[dict]:
    listed = fetch_json(f"{server}/blog/tools.json", home).get("tools", [])
    return [t for t in listed if isinstance(t, dict) and isinstance(t.get("name"), str)
            and isinstance(t.get("post"), str)] if isinstance(listed, list) else []


def find(listed: list[dict], wanted: str) -> dict:
    wanted = wanted.strip().lower().lstrip("#")
    hits = [t for t in listed if wanted in (t["name"], t["post"].removesuffix(".md"), str(t.get("id")))]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise DevexError(f"no published tool called {wanted!r}. See: devexai list")
    raise DevexError(f"{wanted!r} could be: " + ", ".join(f"#{t.get('id')} {t['name']}" for t in hits)
                     + ". Use the number.")
