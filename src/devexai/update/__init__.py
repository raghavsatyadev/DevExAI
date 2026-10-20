"""Self-update from our own server, gated by the company's licence key. See client.py."""

from __future__ import annotations

import logging
import threading
from typing import Callable

from .. import __version__, home
from ..config import UpdateSettings
from . import client, install
from .manifest import UpdateError

log = logging.getLogger(__name__)


def check_once(settings: UpdateSettings) -> str:
    """Check now and stage a newer version if this is an installed copy. Returns what happened."""
    if not settings.url:
        return "Updates are off: set [update] url in settings.toml."
    if not settings.licence:
        return "Updates need the licence key: set DEVEXAI_LICENCE_KEY in .env."
    root = home.install_root()
    if not install.running_installed(root):
        rel = client.latest(settings.url, settings.licence)
        return f"Version {rel.version} is out (this copy is not installed, so it cannot update itself)." \
            if rel else f"Up to date ({__version__})."
    rel = client.update(settings.url, settings.licence, root)
    return f"Version {rel.version} is ready; restart DevExAI to use it." if rel else f"Up to date ({__version__})."


def start_checks(settings: UpdateSettings, stop: threading.Event, notify: Callable[[str], None]) -> None:
    """Check in the background at start and then every check_hours; tell `notify` when one is ready."""
    if not (settings.url and settings.licence):
        return

    def loop() -> None:
        wait = 60.0  # let the bot settle first
        while not stop.wait(wait):
            try:
                said = check_once(settings)
            except UpdateError as e:
                log.warning("update check failed: %s", e)
            except Exception:
                log.exception("update check failed")
            else:
                log.info("update check: %s", said)
                if not said.startswith("Up to date"):
                    notify(said)
            wait = max(settings.check_hours, 1) * 3600

    threading.Thread(target=loop, name="devexai-update", daemon=True).start()


__all__ = ["UpdateError", "check_once", "start_checks"]
