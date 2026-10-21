import struct
import sys
from pathlib import Path

from devexai import proc
from devexai.update import shortcut

ROOT = Path(__file__).resolve().parents[1]


def test_worker_runs_as_module_from_source(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert proc.worker_command("devexai.gate.fetch_worker", "--fetch-worker")[1:] == \
        ["-I", "-m", "devexai.gate.fetch_worker"]


def test_tray_build_runs_workers_with_the_console_exe(monkeypatch, tmp_path):
    (tmp_path / "devexai.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "devexaiw.exe"))
    assert proc.worker_command("m", "--fetch-worker") == [str(tmp_path / "devexai.exe"), "--fetch-worker"]


def test_console_build_runs_workers_with_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "devexai.exe"))
    assert proc.worker_command("m", "--fetch-worker") == [str(tmp_path / "devexai.exe"), "--fetch-worker"]


def test_no_shortcut_without_an_installed_tray_exe(tmp_path):
    assert shortcut.write(tmp_path) is None  # no current.txt
    (tmp_path / "current.txt").write_text("app-0.1.0", encoding="utf-8")
    assert shortcut.write(tmp_path) is None  # no app-0.1.0/devexaiw.exe


def test_icon_has_tray_and_large_sizes():
    data = (ROOT / "assets" / "logo" / "devexai.ico").read_bytes()
    _, kind, count = struct.unpack_from("<HHH", data)
    sides = {struct.unpack_from("<B", data, 6 + 16 * i)[0] or 256 for i in range(count)}
    assert kind == 1 and {16, 32, 256} <= sides
