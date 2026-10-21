import ast
import datetime
import io
import ipaddress
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from test_blog import raw
from test_web import make_server

from devexai.web import Dashboard
from devexai_cli import cli

import devexai
import devexai_cli
from devexai import __main__ as entry
from devexai import instance
from devexai.config import WebSettings
from devexai.web import get_routes

CLI = Path(devexai_cli.__file__).parent


@pytest.fixture
def web(tmp_path):
    server = make_server(tmp_path)
    yield server
    server.shutdown()
    server.server_close()


def test_developer_command_has_no_admin_code():
    for py in CLI.glob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
            assert not any(n == "devexai" or n.startswith("devexai.") for n in names), py.name


def test_versions_match():
    assert devexai.__version__ == devexai_cli.__version__


def test_one_bot_per_data_folder(tmp_path):
    first = instance.acquire(tmp_path / instance.LOCK)
    assert first is not None
    assert instance.acquire(tmp_path / instance.LOCK) is None
    instance.release(first)
    again = instance.acquire(tmp_path / instance.LOCK)
    assert again is not None
    instance.release(again)


@pytest.mark.parametrize(("argv", "tool"), [
    (["install", "lint"], True), (["install", "lint", "--global"], True), (["list"], True),
    (["uninstall", "lint"], True), (["connect", "https://x:8765"], True),
    (["install"], False), (["install", "--help"], False), (["update"], False), (["start", "admin"], False), ([], False),
])
def test_tool_commands_go_to_the_developer_command(argv, tool):
    assert entry.tool_command(argv) is tool


def test_get_page_and_version(web):
    resp, data = raw(web, "GET", "/get")
    assert resp.status == 200 and b"devexai.pyz" in data and b"Get DevExAI for developers" in data
    resp, data = raw(web, "GET", "/get/version.json")
    assert resp.status == 200 and json.loads(data)["version"] == devexai.__version__
    assert raw(web, "GET", "/get/ca.pem")[0].status == 404  # no TLS, no authority to hand out
    assert raw(web, "GET", "/get/../settings.toml")[0].status == 404


def test_pyz_runs_only_the_developer_command(web):
    resp, data = raw(web, "GET", "/get/devexai.pyz")
    assert resp.status == 200 and data.startswith(b"#!/usr/bin/env python3\n")
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "__main__.py" in names and "devexai_cli/cli.py" in names
    assert all(n == "__main__.py" or n.startswith("devexai_cli/") for n in names)


def test_install_script_quotes_the_server(web):
    resp, data = raw(web, "GET", "/get/install.sh")
    port = web.server_address[1]
    assert resp.status == 200 and f"server=http://127.0.0.1:{port}\n".encode() in data
    assert "server='http://x/a b'" in get_routes.install_sh("http://x/a b")


def _cert(subject, issuer, key, sign_key, ca):
    now = datetime.datetime.now(datetime.UTC)
    b = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now)
         .not_valid_after(now + datetime.timedelta(days=1))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if not ca:
        b = b.add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                            critical=False)
    return b.sign(sign_key, hashes.SHA256())


def _pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def _chain(folder, name="Test CA"):
    """A CA and a server certificate for 127.0.0.1 it signed: chain.pem (server, CA) and key.pem."""
    ca_key, key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    ca = _cert(ca_name, ca_name, ca_key, ca_key, True)
    leaf = _cert(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "devexai")]), ca_name, key, ca_key, False)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "chain.pem").write_bytes(_pem(leaf) + _pem(ca))
    (folder / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                       serialization.NoEncryption()))
    return WebSettings(port=0, tls_cert=str(folder / "chain.pem"), tls_key=str(folder / "key.pem")), _pem(ca), _pem(leaf)


def test_authority_is_the_ca_in_the_chain(tmp_path):
    web, ca, leaf = _chain(tmp_path)
    assert get_routes.authority_pem(web) == ca
    (tmp_path / "chain.pem").write_bytes(leaf)
    assert get_routes.authority_pem(web) is None


@pytest.fixture
def tls_web(tmp_path):
    plain = make_server(tmp_path)
    plain.shutdown()
    plain.server_close()
    web, ca, _ = _chain(tmp_path / "tls")
    server = Dashboard(plain.bot, web)
    server.start()
    yield server, ca
    server.shutdown()
    server.server_close()


def test_connect_trusts_the_company_ca(tls_web, tmp_path, capsys):
    server, ca = tls_web
    url = f"https://127.0.0.1:{server.server_address[1]}"
    home = tmp_path / "dev"
    assert cli.main(["list", "--server", url], home=home) == 1  # not trusted yet
    assert "devexai connect" in capsys.readouterr().err
    assert cli.main(["connect", url, "--no-system"], home=home) == 0
    assert (home / ".devex" / "ca.pem").read_bytes() == ca
    assert cli.main(["list"], home=home) == 0


def test_connect_refuses_a_ca_that_did_not_sign_the_server(tls_web, tmp_path, monkeypatch):
    server, _ = tls_web
    _, other, _ = _chain(tmp_path / "other", "Other CA")
    monkeypatch.setattr("devexai_cli.connect.authority", lambda s, h: other)
    home = tmp_path / "dev"
    assert cli.main(["connect", f"https://127.0.0.1:{server.server_address[1]}", "--no-system"], home=home) == 1
    assert not (home / ".devex" / "ca.pem").exists() and not (home / ".devex" / "server.txt").exists()


def test_pyz_runs(web, tmp_path):
    path = tmp_path / "devexai.pyz"
    path.write_bytes(raw(web, "GET", "/get/devexai.pyz")[1])
    done = subprocess.run([sys.executable, "-I", str(path), "--version"], capture_output=True, text=True,
                          cwd=tmp_path)
    assert done.returncode == 0 and done.stdout.strip() == f"devexai {devexai.__version__}"
