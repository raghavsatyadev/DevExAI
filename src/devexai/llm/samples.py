"""Built-in replies for replay runs that have no recording for a role yet (the build step).

They match the first pilot idea (a Claude Code status line that shows the git branch), so a replay
run can go all the way to review without spending tokens.
"""

from __future__ import annotations

_SCRIPT = '''"""Claude Code status line: prints the current git branch of the session's folder."""

import json
import subprocess
import sys


def folder_from(stdin_text):
    try:
        return json.loads(stdin_text).get("workspace", {}).get("current_dir") or "."
    except (ValueError, AttributeError):
        return "."


def git(folder, *args):
    try:
        out = subprocess.run(["git", "-C", folder, *args], capture_output=True, text=True, timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def status(folder):
    branch = git(folder, "branch", "--show-current") or git(folder, "rev-parse", "--short", "HEAD")
    return f"\\u2387 {branch}" if branch else "-"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to cp1252, which has no branch symbol
    print(status(folder_from(sys.stdin.read())))
'''

_TESTS = '''import subprocess

import statusline_branch as sb


def make_repo(path, branch="main"):
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "-m", "x"], check=True)


def test_branch_name(tmp_path):
    make_repo(tmp_path, "feature/x")
    assert sb.status(str(tmp_path)) == "\\u2387 feature/x"


def test_not_a_repo(tmp_path):
    assert sb.status(str(tmp_path)) == "-"


def test_broken_json_falls_back():
    assert sb.folder_from("not json") == "."
    assert sb.folder_from('{"workspace": {"current_dir": "/w"}}') == "/w"
'''

_README = '''# Git branch status line for Claude Code

Shows the git branch of the folder Claude Code is working in, for example `⎇ main`.
Outside a git repo it shows `-`. It never breaks the status line: errors and slow git calls fall back quietly.

## Install

1. Copy `statusline_branch.py` somewhere stable, e.g. `~/.claude/statusline_branch.py`.
2. Add this to `~/.claude/settings.json` (see `settings.example.json`):
   `"statusLine": {"type": "command", "command": "python ~/.claude/statusline_branch.py"}`

## Tests

`python -m pytest tests`
'''

SAMPLES = {
    "builder": {
        "files": [
            {"path": "statusline_branch.py", "content": _SCRIPT},
            {"path": "tests/test_statusline_branch.py", "content": _TESTS},
            {"path": "README.md", "content": _README},
            {"path": "settings.example.json", "content":
                '{\n  "statusLine": {"type": "command", "command": "python ~/.claude/statusline_branch.py"}\n}\n'},
        ],
        "summary": "A small Python script Claude Code runs as its status line. It prints the git branch of the "
                   "session's folder, or the short commit on a detached HEAD, and a dash outside a repo.",
        "install": "Copy statusline_branch.py to ~/.claude/ and add the statusLine entry from "
                   "settings.example.json to ~/.claude/settings.json.",
        "test_command": "python -m pytest tests",
    },
    "reviewer": {
        "verdict": "ok",
        "safe": True,
        "safety_issues": [],
        "findings": ["Only git is run, with a 1 second limit, and nothing leaves the machine."],
    },
}
