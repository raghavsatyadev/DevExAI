"""/get: what a developer's computer needs to use DevExAI, served by the dashboard to everyone (no sign-in).

    /get                          the page: Windows setup, the Linux one-liner, the company CA's fingerprint
    /get/DevExAI-User-Setup.exe   the Windows setup of the developer command (devexai_cli, never admin code)
    /get/devexai-linux-x64        the same command for Linux, one file
    /get/install.sh               puts that file in ~/.local/bin and connects it to this server
    /get/devexai.pyz              the same command for any computer with Python 3.11 or later
    /get/ca.pem                   the certificate authority that signed the dashboard's certificate
    /get/version.json             the developer builds here, for `devexai update`

The developer builds are files shipped inside the admin build (dist/user/ when run from source).
"""

from __future__ import annotations

import hashlib
import io
import json
import shlex
import zipfile
from functools import cache
from html import escape
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

from .. import __version__, home
from ..config import WebSettings
from . import blog, pages

if TYPE_CHECKING:
    from .server import _Handler

FILES = {"windows-x64": "DevExAI-User-Setup.exe", "linux-x64": "devexai-linux-x64"}
_PYZ_MAIN = b"import sys\nfrom devexai_cli.cli import main\nsys.exit(main())\n"
_INSTALL_SH = r"""#!/bin/sh
# Installs the DevExAI developer command (devexai) for this user and connects it to the DevExAI server.
set -eu
server=@SERVER@
mkdir -p "$HOME/.devex" "$HOME/.local/bin"
trust=""
if curl -fsSk "$server/get/ca.pem" -o "$HOME/.devex/ca.pem.new"; then
  mv "$HOME/.devex/ca.pem.new" "$HOME/.devex/ca.pem"
  trust="--cacert $HOME/.devex/ca.pem"
else
  rm -f "$HOME/.devex/ca.pem.new"
fi
curl -fsS $trust "$server/get/devexai-linux-x64" -o "$HOME/.local/bin/devexai.new"
chmod 755 "$HOME/.local/bin/devexai.new"
mv "$HOME/.local/bin/devexai.new" "$HOME/.local/bin/devexai"
"$HOME/.local/bin/devexai" connect "$server"
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo "Add ~/.local/bin to your PATH, for example in ~/.profile: export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
echo "Done. Install a tool with: devexai install <tool>"
"""


def user_file(name: str) -> Path:
    return home.bundled(f"user/{name}" if home.frozen() else f"dist/user/{name}")


@cache
def _sha256(path: Path, size: int, mtime: float) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_info() -> dict:
    files = {}
    for tag, name in FILES.items():
        path = user_file(name)
        if path.is_file():
            st = path.stat()
            files[tag] = {"name": name, "sha256": _sha256(path, st.st_size, st.st_mtime)}
    return {"version": __version__, "files": files}


def authority_pem(web: WebSettings) -> bytes | None:
    """The CA certificate in the dashboard's certificate file (server certificate first, then its CA)."""
    if not web.tls:
        return None
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding

    try:
        certs = x509.load_pem_x509_certificates(Path(web.tls_cert).read_bytes())
    except (OSError, ValueError):
        return None
    for cert in certs[1:]:
        try:
            if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
                return cert.public_bytes(Encoding.PEM)
        except x509.ExtensionNotFound:
            continue
    return None


def cli_sources() -> Path:
    if home.frozen():
        return home.bundled("devexai_cli_src")
    import devexai_cli

    return Path(devexai_cli.__file__).parent


@cache
def pyz_bytes(folder: Path) -> bytes:
    """The developer command as one file Python runs: `python3 devexai.pyz install <tool>`."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("__main__.py", _PYZ_MAIN)
        for py in sorted(folder.glob("*.py")):
            zf.write(py, f"devexai_cli/{py.name}")
    return b"#!/usr/bin/env python3\n" + buf.getvalue()


def install_sh(origin: str) -> str:
    return _INSTALL_SH.replace("@SERVER@", shlex.quote(origin))


def get_page(origin: str, web: WebSettings) -> str:
    ids = iter(range(1, 1000))
    info = version_info()["files"]
    win = (f'<div class="row"><a class="btn" href="/get/{FILES["windows-x64"]}" download>'
           f'Download DevExAI for Windows</a></div><p>Run it and click through: it installs the '
           f'<code>devexai</code> command, trusts the company certificate and connects to this server '
           f'(<code>{escape(origin)}</code>). No Python and no admin rights needed.</p>') \
        if "windows-x64" in info else '<p class="muted">The Windows setup is not on this server.</p>'
    nix = (f'<p>In a terminal:</p>{blog.code_block(f"curl -fsSk {origin}/get/install.sh | sh", ids)}'
           if "linux-x64" in info else "")
    fp = ""
    if pem := authority_pem(web):
        from devexai_cli.connect import fingerprint

        fp = (f'<p class="muted">The company certificate authority\'s SHA-256 fingerprint, to check it: '
              f'<code>{fingerprint(pem)}</code> (<a href="/get/ca.pem">ca.pem</a>)</p>')
    pyz = (f'<p>Download <a href="/get/devexai.pyz" download>devexai.pyz</a> (needs Python 3.11 or later), '
           f'then run it with Python wherever a post says <code>devexai</code>:</p>'
           f'{blog.code_block(f"python3 devexai.pyz connect {origin}", ids)}'
           f'{blog.code_block("python3 devexai.pyz install <tool>", ids)}')
    body = (f'<div class="card"><h1>Get DevExAI for developers</h1><p>Once per computer. Afterwards every '
            f'tool on the blog installs with the command shown on its post, like '
            f'<code>devexai install &lt;tool&gt;</code>. Open a new terminal after installing.</p>'
            f'<h2>Windows</h2>{win}<h2>Linux</h2>{nix or "<p class=muted>Use devexai.pyz below.</p>"}'
            f'<h2>macOS, or any computer with Python</h2>{pyz}{fp}</div>')
    return blog._page("Get DevExAI", body)


def get_get(h: _Handler, path: str, base_csp: str) -> None:
    web, origin = h.server.web, h.server.base_url

    def attach(name: str) -> dict[str, str]:
        return {"Content-Disposition": f'attachment; filename="{name}"'}

    if path in ("/get", "/get/"):
        html = {"Content-Security-Policy": f"{base_csp}; script-src {blog.SCRIPT_HASH}"}
        return h._send(HTTPStatus.OK, get_page(origin, web), html)
    if path == "/get/version.json":
        return h._send_bytes(HTTPStatus.OK, json.dumps(version_info()).encode(), "application/json", {})
    if path == "/get/ca.pem" and (pem := authority_pem(web)):
        return h._send_bytes(HTTPStatus.OK, pem, "application/x-pem-file", attach("devexai-ca.pem"))
    if path == "/get/install.sh":
        return h._send_bytes(HTTPStatus.OK, install_sh(origin).encode(), "text/x-shellscript; charset=utf-8", {})
    if path == "/get/devexai.pyz":
        return h._send_bytes(HTTPStatus.OK, pyz_bytes(cli_sources()), "application/octet-stream",
                             attach("devexai.pyz"))
    name = path.removeprefix("/get/")
    if name in FILES.values() and (file := user_file(name)).is_file():
        return h._send_bytes(HTTPStatus.OK, file.read_bytes(), "application/octet-stream", attach(name))
    h._send(HTTPStatus.NOT_FOUND, pages.message_page("Not found", "No such download on this server."))
