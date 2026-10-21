"""Command line.

    devexai                 run the bot and dashboard (first run: creates settings, opens the setup page)
    devexai install         copy this unpacked build into the per-user install folder
    devexai update          check our server now and stage a newer version
    devexai --chat slack    run connected to Slack (tokens in .env); the dashboard's Slack page sets this too
    devexai --replay        AI steps answer from recorded replies in llm-replies/ (tests without spending tokens)
    devexai --tray          run with an icon in the Windows notification area instead of console chat;
                            devexaiw.exe (the Start menu entry) does this without a console window
    devexai --version
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__, home


def _install() -> None:
    from .update import install, shortcut

    if not home.frozen():
        sys.exit("install works from the packaged build only; from source, use `uv run devexai`.")
    root = home.install_root()
    launcher = install.install(Path(sys.executable).resolve().parent, root, __version__)
    link = shortcut.write(root)
    data = home.data_home()
    first = home.prepare(data)
    print(f"Installed DevExAI {__version__} in {root}\nStart it with: {launcher}\nSettings and data: {data}"
          + (f"\nOr from the Start menu: DevExAI, which runs as an icon in the notification area ({link})"
             if link else "")
          + ("\nOn first start your browser opens the page that creates the admin account." if first else ""))


def _update(settings_path: Path, env_path: Path) -> None:
    from .config import load_dotenv, load_settings
    from .update import UpdateError, check_once

    load_dotenv(env_path)
    try:
        print(check_once(load_settings(settings_path).update))
    except UpdateError as e:
        sys.exit(f"Update failed: {e}")


def windowed() -> bool:
    """True in devexaiw.exe, the build without a console: nothing printed is seen there."""
    return home.frozen() and Path(sys.executable).name.lower() == "devexaiw.exe"


def main(argv: list[str] | None = None) -> None:
    if not windowed():
        return _main(argv)
    from . import tray

    try:
        _main(argv)
    except SystemExit as e:  # argparse and sys.exit() would print to a console that is not there
        if e.code not in (None, 0):
            tray.show_error("DevExAI", str(e.code))
    except Exception as e:
        logging.exception("DevExAI stopped")
        tray.show_error("DevExAI stopped", f"{type(e).__name__}: {e}")


def _main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--fetch-worker"]:  # the packaged build's stand-in for `python -m ...fetch_worker`
        from .gate import fetch_worker

        return fetch_worker.main()
    parser = argparse.ArgumentParser(prog="devexai", description="DevExAI idea bot")
    parser.add_argument("command", nargs="?", default="run", choices=("run", "install", "update"))
    parser.add_argument("--version", action="version", version=f"DevExAI {__version__}")
    parser.add_argument("--home", type=Path, help="folder holding settings.toml, .env and data/")
    parser.add_argument("--settings", type=Path, default=Path("settings.toml"))
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--headless", action="store_true", help="no console chat; dashboard only")
    parser.add_argument("--chat", choices=("console", "none", "slack"), help="chat platform for this run")
    parser.add_argument("--replay", action="store_true",
                        help="answer AI steps from recorded replies (llm-replies/), spending no tokens")
    parser.add_argument("--no-browser", action="store_true", help="do not open the setup page on first run")
    parser.add_argument("--tray", action="store_true", help="icon in the Windows notification area, no console chat")
    if windowed():  # argparse writes help and errors to stderr, which a windowed exe lacks
        parser.exit = lambda status=0, message=None: sys.exit(message or status or None)
    args = parser.parse_args(argv)
    tray_mode = args.tray or (windowed() and args.command == "run")
    if tray_mode and args.command == "run":
        from . import tray

        if tray.ask_running_to_open():  # already running: show its dashboard instead of a second copy
            return
    if args.command == "install":
        return _install()
    data = home.data_home(args.home)
    first = home.prepare(data) if (home.frozen() or args.home) else False
    os.chdir(data)  # every relative path in settings (db, blog, log) is under the data home
    if not args.settings.is_file():
        parser.error(f"{args.settings.resolve()} not found; copy settings.example.toml to settings.toml")
    if args.command == "update":
        return _update(args.settings, args.env)
    if first:
        print(f"First run: created {data / home.SETTINGS}. Edit it to change maintainers, network and updates.")
    from .app import run

    run(args.settings, args.env, adapter="none" if args.headless else args.chat,
        open_browser=home.frozen() and not args.no_browser, replay=args.replay, tray=tray_mode)


if __name__ == "__main__":
    main()
