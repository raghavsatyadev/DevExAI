"""`devexai connect <server>`: remember the server and trust the company certificate authority it uses.

A dashboard on the company network usually has a certificate from the company's own authority, which a new
computer does not trust. The server hands that authority out at /get/ca.pem. Like the first SSH connection
to a host, that first download cannot be checked yet; connect then proves the server's own certificate is
signed by it before keeping it. On Windows the authority is also added to this user's trusted roots (Windows
asks first and names it), so the browser trusts the dashboard and blog too.
"""

from __future__ import annotations

import hashlib
import os
import re
import ssl
import subprocess
from pathlib import Path

from .net import DevexError, ca_file, check_url, context, fetch, save_server

_PEM = re.compile(rb"-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\r?\n?")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def unchecked() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def authority(server: str, home: Path) -> bytes | None:
    """The server's certificate authority (PEM), or None when it has none to hand out."""
    try:
        data = fetch(f"{server}/get/ca.pem", home, limit=20_000, ctx=unchecked())
    except DevexError as e:
        if "answered 404" in str(e):
            return None
        raise
    if not _PEM.fullmatch(data):
        raise DevexError(f"{server}/get/ca.pem is not one certificate")
    return data


def fingerprint(pem: bytes, algo: str = "sha256") -> str:
    der = ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))
    return hashlib.new(algo, der).hexdigest().upper()


def trust_in_windows(pem_path: Path, out) -> None:
    thumb = fingerprint(pem_path.read_bytes(), "sha1")
    have = subprocess.run(["certutil", "-user", "-verifystore", "Root", thumb], capture_output=True,
                          creationflags=NO_WINDOW)
    if have.returncode == 0:
        return
    out("Windows will now ask whether to trust the DevExAI certificate authority: check the name and click Yes.")
    done = subprocess.run(["certutil", "-user", "-addstore", "Root", str(pem_path)], capture_output=True,
                          creationflags=NO_WINDOW)
    if done.returncode != 0:
        out("Not added to Windows (declined?). devexai still works; the browser will warn on the dashboard.")


def connect(url: str, home: Path, *, system: bool = True, out=print) -> str:
    server = check_url(url)
    pem = authority(server, home) if server.startswith("https:") else None
    if pem:
        path = ca_file(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_bytes() if path.is_file() else None
        path.write_bytes(pem)
        try:  # the server's own certificate must chain to what it handed out
            fetch(f"{server}/blog/tools.json", home, ctx=context(home))
        except DevexError:
            if old is None:
                path.unlink()
            else:
                path.write_bytes(old)
            raise DevexError(f"{server} handed out a certificate authority that did not sign its own "
                             "certificate; not trusting it") from None
        out(f"Trusting the certificate authority of {server} (SHA-256 {fingerprint(pem)[:23]}...).")
        if system and os.name == "nt":
            trust_in_windows(path, out)
    else:
        fetch(f"{server}/blog/tools.json", home)  # reachable and trusted as it is
    save_server(server, home)
    out(f"Connected to {server}. Install a tool with: devexai install <tool>")
    return server
