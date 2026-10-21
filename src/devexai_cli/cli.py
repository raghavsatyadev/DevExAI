"""The developer command line (see the package docstring)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, connect, selfupdate
from .net import DevexError, plain, server_url, tools
from .tools import install, uninstall


def parser(prog: str = "devexai") -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=prog, description="Install DevExAI tools for your AI coding assistant.")
    p.add_argument("--version", action="version", version=f"devexai {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--server", default=argparse.SUPPRESS,
                        help="the DevExAI server, e.g. https://devexai.example:8765 (remembered)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list", parents=[common], help="the published tools")
    for cmd in ("install", "uninstall"):
        c = sub.add_parser(cmd, parents=[common], help=f"{cmd} a tool")
        c.add_argument("tool")
        where = c.add_mutually_exclusive_group()
        where.add_argument("--project", action="store_true", help="this project only (the default)")
        where.add_argument("--global", dest="glob", action="store_true", help="your home folder: every project")
        c.add_argument("--dir", type=Path, help="the project folder, if not the current one")
        c.add_argument("--yes", "-y", action="store_true", help="do not ask")
        if cmd == "install":
            c.add_argument("--force", action="store_true", help="replace files that are not from this tool")
    c = sub.add_parser("connect", help="remember the DevExAI server and trust its certificate")
    c.add_argument("url", help="the server's address, e.g. https://devexai.example:8765")
    c.add_argument("--no-system", action="store_true", help="do not add its certificate authority to Windows")
    sub.add_parser("update", parents=[common], help="install a newer devexai from the server")
    return p


def main(argv: list[str] | None = None, home: Path | None = None, prog: str = "devexai") -> int:
    home = home or Path.home()
    args = parser(prog).parse_args(argv)
    try:
        if args.command == "connect":
            connect.connect(args.url, home, system=not args.no_system)
            return 0
        server = server_url(getattr(args, "server", None), home)
        if args.command == "update":
            selfupdate.update(server, home)
            return 0
        if args.command == "list":
            for t in tools(server, home):
                print(f"#{t.get('id')}  {plain(t['name'])}  {plain(t.get('title', ''))}")
        elif args.command == "install":
            root = home if args.glob else (args.dir or Path.cwd()).resolve()
            install(server, args.tool, root, home=home, yes=args.yes, force=args.force,
                    scope=" --global" if args.glob else "")
        else:
            uninstall(args.tool, home if args.glob else (args.dir or Path.cwd()).resolve(), yes=args.yes)
        if hint := selfupdate.notice(server, home):
            print(hint, file=sys.stderr)
        return 0
    except DevexError as e:
        print(f"devexai: {e}", file=sys.stderr)
        return 1
