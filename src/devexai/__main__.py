"""Command line.

    devexai                 run the bot and dashboard (first run: creates settings, opens the setup page)
    devexai install         copy this unpacked build into the per-user install folder
    devexai update          check our server now and stage a newer version
    devexai --chat slack    run connected to Slack (tokens in .env); the dashboard's Slack page sets this too
    devexai --replay        AI steps answer from recorded replies in llm-replies/ (tests without spending tokens)
    devexai --version
"""

import argparse
import os
import sys
from pathlib import Path

from . import __version__, home


def _install() -> None:
    from .update import install

    if not home.frozen():
        sys.exit("install works from the packaged build only; from source, use `uv run devexai`.")
    root = home.install_root()
    launcher = install.install(Path(sys.executable).resolve().parent, root, __version__)
    data = home.data_home()
    first = home.prepare(data)
    print(f"Installed DevExAI {__version__} in {root}\nStart it with: {launcher}\nSettings and data: {data}"
          + ("\nOn first start your browser opens the page that creates the admin account." if first else ""))


def _update(settings_path: Path, env_path: Path) -> None:
    from .config import load_dotenv, load_settings
    from .update import UpdateError, check_once

    load_dotenv(env_path)
    try:
        print(check_once(load_settings(settings_path).update))
    except UpdateError as e:
        sys.exit(f"Update failed: {e}")


def main(argv: list[str] | None = None) -> None:
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
    args = parser.parse_args(argv)
    if args.command == "install":
        return _install()
    data = home.data_home(args.home)
    first = home.prepare(data) if (home.frozen() or args.home) else False
    os.chdir(data)  # every relative path in settings (db, blog, log) is under the data home
    if not args.settings.is_file():
        parser.error(f"{args.settings} not found; copy settings.example.toml to settings.toml")
    if args.command == "update":
        return _update(args.settings, args.env)
    if first:
        print(f"First run: created {data / home.SETTINGS}. Edit it to change maintainers, network and updates.")
    from .app import run

    run(args.settings, args.env, adapter="none" if args.headless else args.chat,
        open_browser=home.frozen() and not args.no_browser, replay=args.replay)


if __name__ == "__main__":
    main()
