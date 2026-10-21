"""`devexai stop admin`, `devexai status` and `devexai autostart on|off`: the running bot, seen from outside."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import __version__, home, instance

SYSTEMD_UNIT = """[Unit]
Description=DevExAI idea bot
After=network-online.target

[Service]
ExecStart={launcher} --headless
Restart=on-failure

[Install]
WantedBy=default.target
"""


def stop(data: Path) -> None:
    if not instance.running(data):
        print("DevExAI is not running.")
        return
    print("Stopping DevExAI...", flush=True)
    if not instance.request_stop(data):
        sys.exit("DevExAI is still running. Quit it from its icon in the notification area.")
    print("DevExAI stopped.")


def status(data: Path, url: str) -> None:
    up = instance.running(data)
    number = instance.pid(data) if up else None
    print(f"DevExAI {__version__}\n"
          f"Running:   {'yes' + (f' (process {number})' if number else '') if up else 'no'}\n"
          f"Dashboard: {url}\n"
          f"Data:      {data}")
    if os.name == "nt":
        from .update import shortcut

        print(f"Starts at sign-in: {'yes' if shortcut.startup_link().is_file() else 'no'}")
    if not up:
        print("Start it with: devexai start admin")


def autostart(what: str | None) -> None:
    """Start DevExAI (the tray icon, without opening the browser) when this user signs in to Windows."""
    if os.name != "nt":
        launcher = home.install_root() / "devexai"
        sys.exit("On Linux, start DevExAI with systemd: save this as ~/.config/systemd/user/devexai.service,\n"
                 "then run: systemctl --user enable --now devexai && loginctl enable-linger $USER\n\n"
                 + SYSTEMD_UNIT.format(launcher=launcher))
    from .update import shortcut

    link = shortcut.startup_link()
    if what is None:
        print(f"DevExAI starts at sign-in: {'yes' if link.is_file() else 'no'}")
    elif what == "off":
        link.unlink(missing_ok=True)
        print("DevExAI no longer starts at sign-in.")
    elif not home.frozen():
        sys.exit("autostart works for the installed build only.")
    elif shortcut.write(home.install_root(), link) is None:
        sys.exit("DevExAI is not installed for this user; run the DevExAI Admin setup first.")
    else:
        print("DevExAI starts at sign-in, as an icon in the notification area.")
