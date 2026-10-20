"""Talks to our update server: fetch the signed manifest, download and check the zip, stage it.

The licence key goes in an Authorization header, only to the update server's own host, and is
never followed across redirects or written to a log. Proxies set for the machine are used, as a
company network may need them; the signature and hash make that safe.
"""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .. import __version__
from . import install
from .manifest import Release, UpdateError, check_url, parse_version, platform_tag, verify

log = logging.getLogger(__name__)
TIMEOUT = 30
CHUNK = 1 << 16


class _HttpsRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _origin(url: str) -> tuple[str, str, int | None]:
    p = urlsplit(url)
    return p.scheme, (p.hostname or ""), p.port


def _open(url: str, server: str, licence: str):
    req = urllib.request.Request(check_url(url), headers={"User-Agent": f"DevExAI/{__version__}"})
    if licence and _origin(url) == _origin(server):
        req.add_unredirected_header("Authorization", f"Bearer {licence}")  # dropped on any redirect
    try:
        return urllib.request.build_opener(_HttpsRedirects).open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise UpdateError("the update server refused the licence key") from None
        raise UpdateError(f"the update server answered {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError(f"cannot reach the update server: {getattr(e, 'reason', e)}") from None


def latest(server: str, licence: str, current: str = __version__, plat: str | None = None) -> Release | None:
    """The newer release for this platform, or None when we are up to date."""
    plat = plat or platform_tag()
    with _open(f"{server.rstrip('/')}/{plat}/latest.json", server, licence) as resp:
        raw = resp.read(256_001)
    if len(raw) > 256_000:
        raise UpdateError("the update manifest is too large")
    try:
        rel = verify(json.loads(raw))
    except (ValueError, UnicodeDecodeError):
        raise UpdateError("the update manifest is not JSON") from None
    if rel.platform != plat:
        raise UpdateError(f"the manifest is for {rel.platform}, not {plat}")
    return rel if parse_version(rel.version) > parse_version(current) else None


def download(rel: Release, server: str, licence: str, folder: Path) -> Path:
    """Download the zip into folder, checking size and sha256 as it streams."""
    path = folder / f"devexai-{rel.version}.zip"
    digest, got = hashlib.sha256(), 0
    with _open(rel.url, server, licence) as resp, open(path, "wb") as out:
        while chunk := resp.read(CHUNK):
            got += len(chunk)
            if got > rel.size:
                raise UpdateError("the download is larger than the manifest says")
            digest.update(chunk)
            out.write(chunk)
    if got != rel.size or digest.hexdigest() != rel.sha256:
        raise UpdateError("the download does not match the signed manifest")
    return path


def update(server: str, licence: str, root: Path, current: str = __version__) -> Release | None:
    """Check, download and stage. Returns the staged release, or None when up to date."""
    rel = latest(server, licence, current)
    if rel is None:
        return None
    if install.current(root) == install.app_dir(rel.version):
        return rel  # already staged; it runs on the next start
    with tempfile.TemporaryDirectory(dir=root, prefix="download-") as tmp:
        zip_path = download(rel, server, licence, Path(tmp))
        install.stage(zip_path, root, rel.version)
    install.prune(root, {install.app_dir(rel.version), install.app_dir(current)})
    log.info("update %s staged; it runs on the next start", rel.version)
    return rel
