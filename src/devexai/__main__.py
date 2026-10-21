"""Command line.

    devexai                 run the bot and dashboard (first run: creates settings, opens the setup page)
    devexai start admin     start the bot and dashboard in the background and open the dashboard; when
                            they already run, just open the dashboard (never a second bot)
    devexai stop admin      ask the running bot to quit, and wait for it
    devexai status          is it running, its dashboard, its data folder, does it start at sign-in
    devexai autostart on|off
                            start DevExAI (the tray icon) when this user signs in to Windows
    devexai install         copy this unpacked build into the per-user install folder (the setup runs it)
    devexai update          check our server now and stage a newer version
    devexai install <tool>, uninstall <tool>, list, connect <server>
                            the developer commands (devexai_cli), aimed at this machine's dashboard
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
    link = shortcut.refresh(root)
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


TOOL_COMMANDS = ("list", "uninstall", "connect")


def tool_command(argv: list[str]) -> bool:
    """The developer commands: `install` with a tool name, and list / uninstall / connect."""
    return bool(argv) and (argv[0] in TOOL_COMMANDS or
                           (argv[0] == "install" and len(argv) > 1 and not argv[1].startswith("-")))


def background_command(args: argparse.Namespace) -> list[str]:
    """How `start admin` runs the bot without a console: the tray build on Windows, headless elsewhere."""
    passed = [*(["--home", str(args.home)] if args.home else []), *(["--chat", args.chat] if args.chat else []),
              *(["--replay"] if args.replay else []), "--open-dashboard"]
    if home.frozen() and os.name == "nt":
        return [str(Path(sys.executable).with_name("devexaiw.exe")), *passed]
    program = [sys.executable] if home.frozen() else [sys.executable, "-m", "devexai"]
    return [*program, "--tray" if os.name == "nt" else "--headless", *passed]


def _start(args: argparse.Namespace, data: Path) -> None:
    import subprocess
    import webbrowser

    from . import instance
    from .config import load_settings
    from .web.server import dashboard_url

    lock = instance.acquire(data / instance.LOCK)
    if lock is None:  # already running: the dashboard is all that was missing
        url = dashboard_url(load_settings(data / args.settings).web) + "/"
        webbrowser.open(url)
        print(f"DevExAI is already running. Opened {url}")
        return
    instance.release(lock)
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    subprocess.Popen(background_command(args), cwd=data, creationflags=flags, start_new_session=os.name != "nt",
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    print("DevExAI is starting in the background; the dashboard opens in your browser."
          + "\nStop it with: devexai stop admin" + (" (or Quit in its notification-area icon)." if os.name == "nt" else ""))


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
    if tool_command(argv):  # the same commands developers get from DevExAI-User, aimed at this dashboard
        from devexai_cli.cli import main as tool_main

        sys.exit(tool_main(argv))
    parser = argparse.ArgumentParser(prog="devexai", description="DevExAI idea bot")
    parser.add_argument("command", nargs="?", default="run", choices=("run", "start", "stop", "status", "autostart", "install", "update"))
    parser.add_argument("what", nargs="?", choices=("admin", "on", "off"),
                        help="start admin / stop admin: the bot and dashboard; autostart on|off")
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
    parser.add_argument("--open-dashboard", action="store_true", help="open the dashboard once it is up")
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
    if args.command == "autostart":
        if args.what not in (None, "on", "off"):
            parser.error("devexai autostart on, or devexai autostart off")
        from .control import autostart

        return autostart(args.what)
    data = home.data_home(args.home).resolve()
    first = home.prepare(data) if (home.frozen() or args.home) else False
    os.chdir(data)  # every relative path in settings (db, blog, log) is under the data home
    if not args.settings.is_file():
        parser.error(f"{args.settings.resolve()} not found; copy settings.example.toml to settings.toml")
    if args.command == "update":
        return _update(args.settings, args.env)
    if args.command in ("start", "stop"):
        if args.what != "admin":
            parser.error(f"say what to {args.command}: devexai {args.command} admin")
        if args.command == "stop":
            from .control import stop

            return stop(data)
        return _start(args, data)
    if args.command == "status":
        from .config import load_settings
        from .control import status
        from .web.server import dashboard_url

        return status(data, dashboard_url(load_settings(args.settings).web) + "/")
    if first:
        print(f"First run: created {data / home.SETTINGS}. Edit it to change maintainers, network and updates.")
    from . import instance

    if instance.acquire(Path(instance.LOCK)) is None:  # one bot per data folder, whichever way it was started
        from .config import load_settings
        from .web.server import dashboard_url

        url = dashboard_url(load_settings(args.settings).web) + "/"
        if args.open_dashboard or tray_mode:
            import webbrowser

            webbrowser.open(url)
        print(f"DevExAI is already running for {data}; its dashboard is {url}")
        return
    from .app import run

    instance.started(data)
    try:
        run(args.settings, args.env, adapter="none" if args.headless else args.chat,
            open_browser=home.frozen() and not args.no_browser, replay=args.replay, tray=tray_mode,
            open_dashboard=args.open_dashboard)
    finally:
        instance.stopped(data)


if __name__ == "__main__":
    main()
