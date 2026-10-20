"""Signed release manifests.

Our server answers GET <url>/<platform>/latest.json with an envelope:
    {"manifest": base64(JSON bytes), "signature": base64(Ed25519 signature of those bytes)}
The JSON says which version is out and where its zip is:
    {"version": "0.2.0", "platform": "windows-x64", "url": "https://...zip", "sha256": "...", "size": 123}
The signature is checked against keys.RELEASE_KEYS before anything in it is trusted.
"""

from __future__ import annotations

import base64
import binascii
import json
import platform
import re
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import keys

MAX_SIZE = 1 << 30
_VERSION = re.compile(r"\d{1,6}(\.\d{1,6}){0,3}")
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class UpdateError(Exception):
    """The update could not be checked, fetched or trusted. The message is fit for a log."""


@dataclass(frozen=True)
class Release:
    version: str
    platform: str
    url: str
    sha256: str
    size: int


def platform_tag() -> str:
    osname = "windows" if sys.platform == "win32" else sys.platform.rstrip("0123456789")
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower())
    return f"{osname}-{arch}"


def parse_version(text: str) -> tuple[int, ...]:
    if not isinstance(text, str) or not _VERSION.fullmatch(text):
        raise UpdateError(f"not a version number: {text!r}")
    return tuple(int(p) for p in text.split("."))


def check_url(url: str) -> str:
    """https only; plain http is allowed for this machine alone (local testing)."""
    parts = urlsplit(url)
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in _LOOPBACK):
        return url
    raise UpdateError(f"refusing a non-https update address: {url}")


def sign(manifest: dict, private_key: Ed25519PrivateKey) -> dict:
    body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return {"manifest": base64.b64encode(body).decode(),
            "signature": base64.b64encode(private_key.sign(body)).decode()}


def _signed_by_us(body: bytes, signature: bytes, trusted: tuple[str, ...]) -> bool:
    for key in trusted:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key)).verify(signature, body)
            return True
        except (InvalidSignature, ValueError):
            continue
    return False


def verify(envelope: object, trusted: tuple[str, ...] | None = None) -> Release:
    trusted = keys.RELEASE_KEYS if trusted is None else trusted
    try:
        body = base64.b64decode(envelope["manifest"], validate=True)
        signature = base64.b64decode(envelope["signature"], validate=True)
    except (TypeError, KeyError, binascii.Error):
        raise UpdateError("the update manifest is malformed") from None
    if not _signed_by_us(body, signature, trusted):
        raise UpdateError("the update manifest is not signed by a DevExAI release key")
    try:
        data = json.loads(body)
        rel = Release(str(data["version"]), str(data["platform"]), str(data["url"]),
                      str(data["sha256"]).lower(), int(data["size"]))
    except (ValueError, KeyError, TypeError):
        raise UpdateError("the signed manifest is missing fields") from None
    parse_version(rel.version)
    check_url(rel.url)
    if not re.fullmatch(r"[0-9a-f]{64}", rel.sha256) or not 0 < rel.size <= MAX_SIZE:
        raise UpdateError("the signed manifest has a bad hash or size")
    return rel
