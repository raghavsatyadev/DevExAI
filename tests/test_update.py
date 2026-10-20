import base64
import hashlib
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from devexai import home
from devexai.chat.headless import HeadlessChat
from devexai.update import client, install, keys
from devexai.update.manifest import UpdateError, sign, verify

PLAT = "windows-x64"
KEY = Ed25519PrivateKey.generate()
PUB = base64.b64encode(KEY.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)).decode()


@pytest.fixture(autouse=True)
def trust_test_key(monkeypatch):
    monkeypatch.setattr(keys, "RELEASE_KEYS", (PUB,))


def make_zip(path, files=None):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in (files or {f"devexai/{install.EXE}": b"exe", "devexai/_internal/x.dll": b"x"}).items():
            zf.writestr(name, data)
    return path.read_bytes()


class FakeServer:
    """Serves /<platform>/latest.json and /files/<name>; records Authorization headers."""

    def __init__(self, licence="lic-123"):
        self.files: dict[str, bytes] = {}
        self.auth: list[str | None] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                outer.auth.append(self.headers.get("Authorization"))
                if self.headers.get("Authorization") != f"Bearer {licence}":
                    self.send_response(401)
                    self.end_headers()
                    return
                body = outer.files.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.end_headers()
                self.wfile.write(body or b"")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def release(self, version, data, *, sha=None, size=None, key=KEY, platform=PLAT):
        name = f"/files/devexai-{version}.zip"
        self.files[name] = data
        manifest = {"version": version, "platform": platform, "url": self.url + name,
                    "sha256": sha or hashlib.sha256(data).hexdigest(), "size": size or len(data)}
        self.files[f"/{PLAT}/latest.json"] = json.dumps(sign(manifest, key)).encode()


@pytest.fixture
def server():
    s = FakeServer()
    yield s
    s.httpd.shutdown()


def test_signature_must_match():
    env = sign({"version": "1.0", "platform": PLAT, "url": "https://x/a.zip", "sha256": "0" * 64, "size": 1}, KEY)
    assert verify(env).version == "1.0"
    with pytest.raises(UpdateError, match="not signed"):
        verify(sign(json.loads(base64.b64decode(env["manifest"])), Ed25519PrivateKey.generate()))
    tampered = {**env, "manifest": base64.b64encode(base64.b64decode(env["manifest"]).replace(b"1.0", b"9.0")).decode()}
    with pytest.raises(UpdateError, match="not signed"):
        verify(tampered)
    with pytest.raises(UpdateError, match="non-https"):
        verify(sign({"version": "1.0", "platform": PLAT, "url": "http://evil/a.zip", "sha256": "0" * 64,
                     "size": 1}, KEY))


def test_update_stages_new_version_and_keeps_running_one(server, tmp_path):
    root = tmp_path / "DevExAI"
    (root / "app-0.1.0").mkdir(parents=True)
    (root / "app-0.0.9").mkdir()
    install.set_current(root, "app-0.1.0")
    server.release("0.2.0", make_zip(tmp_path / "r.zip"))
    rel = client.update(server.url, "lic-123", root, current="0.1.0")
    assert rel.version == "0.2.0" and install.current(root) == "app-0.2.0"
    assert (root / "app-0.2.0" / install.EXE).read_bytes() == b"exe"
    assert sorted(p.name for p in root.glob("app-*")) == ["app-0.1.0", "app-0.2.0"]
    assert server.auth[0] == "Bearer lic-123"
    assert client.update(server.url, "lic-123", root, current="0.1.0").version == "0.2.0"  # already staged


def test_no_downgrade_or_same_version(server, tmp_path):
    server.release("0.1.0", make_zip(tmp_path / "r.zip"))
    assert client.latest(server.url, "lic-123", current="0.1.0", plat=PLAT) is None
    assert client.latest(server.url, "lic-123", current="0.3.0", plat=PLAT) is None


def test_bad_hash_bad_licence_wrong_platform(server, tmp_path):
    root = tmp_path / "DevExAI"
    root.mkdir()
    server.release("0.2.0", make_zip(tmp_path / "r.zip"), sha="0" * 64)
    with pytest.raises(UpdateError, match="does not match"):
        client.update(server.url, "lic-123", root, current="0.1.0")
    assert install.current(root) is None and not list(root.glob("app-*"))
    with pytest.raises(UpdateError, match="licence"):
        client.latest(server.url, "wrong", current="0.1.0", plat=PLAT)
    server.release("0.2.0", make_zip(tmp_path / "r.zip"), platform="linux-x64")
    with pytest.raises(UpdateError, match="linux-x64"):
        client.latest(server.url, "lic-123", current="0.1.0", plat=PLAT)


def test_zip_with_unsafe_paths_is_refused(tmp_path):
    root = tmp_path / "DevExAI"
    root.mkdir()
    for bad in ("../evil.txt", "/abs.txt", "C:/x.txt", "devexai/../../x"):
        z = tmp_path / "bad.zip"
        make_zip(z, {f"devexai/{install.EXE}": b"exe", bad: b"x"})
        with pytest.raises(UpdateError, match="unsafe"):
            install.stage(z, root, "0.2.0")
    assert not (tmp_path / "evil.txt").exists() and install.current(root) is None
    make_zip(tmp_path / "noexe.zip", {"devexai/readme.txt": b"x"})
    with pytest.raises(UpdateError, match="does not hold"):
        install.stage(tmp_path / "noexe.zip", root, "0.2.0")


def test_install_writes_launcher(tmp_path):
    src = tmp_path / "unzipped"
    src.mkdir()
    (src / install.EXE).write_bytes(b"exe")
    launcher = install.install(src, tmp_path / "DevExAI", "0.1.0")
    assert launcher.is_file() and install.current(tmp_path / "DevExAI") == "app-0.1.0"
    assert "current.txt" in launcher.read_text()


def test_first_run_copies_example_settings(tmp_path):
    assert home.prepare(tmp_path / "data") is True
    assert "[[maintainers]]" in (tmp_path / "data" / "settings.toml").read_text(encoding="utf-8")
    assert home.prepare(tmp_path / "data") is False


def test_headless_chat_logs_and_stops():
    chat = HeadlessChat(first_ref=7)
    assert chat.post("#ai-ideas", "hi") == "t7" and chat.post("#ai-ideas", "re", thread="t7") == "t7"
    threading.Timer(0.1, chat.stop).start()
    chat.run(lambda e: None)
