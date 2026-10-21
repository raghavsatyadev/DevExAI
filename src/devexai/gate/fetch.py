"""Finds links in an idea and fetches them through fetch_worker in a separate, secret-free process."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass

from ..config import FetchSettings
from ..proc import NO_WINDOW, worker_command

_URL = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
# The worker gets only what Python and Windows sockets need; nothing from .env.
_ENV_KEEP = ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH")  # no proxies: they would bypass the IP check


@dataclass(frozen=True)
class Page:
    url: str
    ok: bool
    text: str = ""
    error: str = ""
    truncated: bool = False


def find_links(text: str, limit: int) -> list[str]:
    seen: list[str] = []
    for match in _URL.finditer(text):
        url = match.group(0).rstrip(".,;:!?)]}>")
        if url not in seen:
            seen.append(url)
    return seen[:limit]


def _worker_env() -> dict[str, str]:
    return {k: os.environ[k] for k in _ENV_KEEP if k in os.environ}


def fetch_pages(urls: list[str], settings: FetchSettings) -> list[Page]:
    if not urls:
        return []
    job = {
        "urls": urls, "max_bytes": settings.max_bytes,
        "timeout": settings.timeout_seconds, "max_chars": settings.max_chars_per_page,
    }
    overall = settings.timeout_seconds * len(urls) * 3 + 10  # connect + redirects + read, per link
    # a packaged build has no python -m; the exe runs the worker itself (see __main__.py)
    cmd = worker_command("devexai.gate.fetch_worker", "--fetch-worker")
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(job), capture_output=True, env=_worker_env(),
            encoding="utf-8", errors="replace", timeout=overall, creationflags=NO_WINDOW,
        )
        pages = json.loads(proc.stdout)["pages"]
    except subprocess.TimeoutExpired:
        return [Page(u, False, error="fetch timed out") for u in urls]
    except (json.JSONDecodeError, KeyError, OSError):
        err = "fetch worker failed"
        return [Page(u, False, error=err) for u in urls]
    return [
        Page(p["url"], p["ok"], p.get("text", ""), p.get("error", ""), p.get("truncated", False))
        for p in pages
    ]
