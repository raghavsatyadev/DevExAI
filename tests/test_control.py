"""devexai stop admin, status and autostart."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from devexai import control, instance
from devexai.__main__ import _main
from devexai.update import shortcut

SRC = Path(__file__).resolve().parents[1] / "src"
# a stand-in bot: holds the lock and, with "watch", quits on a stop request like the real one
BOT = """
import sys, threading, time
from pathlib import Path
from devexai import instance
data = Path(sys.argv[1])
lock = instance.acquire(data / instance.LOCK)
instance.started(data)
done = threading.Event()
if sys.argv[2] == "watch":
    instance.watch_stop(data, threading.Event(), done.set)
print("ready", flush=True)
done.wait(120)
instance.stopped(data)
"""


def bot(data: Path, mode: str) -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-c", BOT, str(data), mode], stdout=subprocess.PIPE, text=True,
                            env={**os.environ, "PYTHONPATH": str(SRC)})
    assert proc.stdout.readline().strip() == "ready"
    return proc


def test_stop_asks_the_bot_to_quit(tmp_path):
    proc = bot(tmp_path, "watch")
    try:
        assert instance.running(tmp_path) and instance.pid(tmp_path)  # the venv launcher may start a child
        start = time.monotonic()
        assert instance.request_stop(tmp_path)
        assert time.monotonic() - start < 10 and proc.wait(10) == 0  # quit by itself, not killed
        assert not instance.running(tmp_path) and not (tmp_path / instance.PID).exists()
    finally:
        proc.kill()


def test_stop_ends_a_bot_that_does_not_listen(tmp_path):
    proc = bot(tmp_path, "deaf")
    try:
        assert instance.request_stop(tmp_path, wait=1)
        assert proc.wait(10) != 0
    finally:
        proc.kill()


def test_a_stale_stop_request_does_not_stop_the_next_bot(tmp_path):
    (tmp_path / instance.STOP).write_text("stop", encoding="utf-8")
    instance.started(tmp_path)
    assert not (tmp_path / instance.STOP).exists()


def test_status_and_stop_when_not_running(tmp_path, capsys):
    control.status(tmp_path, "https://localhost:8765/")
    out = capsys.readouterr().out
    assert "Running:   no" in out and "https://localhost:8765/" in out and "devexai start admin" in out
    control.stop(tmp_path)
    assert "not running" in capsys.readouterr().out


@pytest.mark.skipif(os.name != "nt", reason="Startup folder is Windows")
def test_autostart_off_and_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    link = shortcut.startup_link()
    assert tmp_path in link.parents
    link.parent.mkdir(parents=True)
    link.write_bytes(b"")
    control.autostart(None)
    assert "sign-in: yes" in capsys.readouterr().out
    control.autostart("off")
    assert not link.exists()
    assert shortcut.refresh(tmp_path) is None and not link.exists()  # not installed: nothing written


@pytest.mark.parametrize("argv", [["stop"], ["stop", "on"], ["autostart", "admin"]])
def test_commands_need_the_right_word(argv, tmp_path):
    with pytest.raises(SystemExit) as e:
        _main([*argv, "--home", str(tmp_path)])
    assert e.value.code == 2
