import json

import pytest
from test_blog import raw
from test_devex import publish, run, web  # noqa: F401  (web is a fixture)
from test_web import Client

from devexai.llm.samples import SAMPLES
from devexai_cli import statusline

SCRIPT = ".claude/statusline_branch.py"
FILES = SAMPLES["builder"]["files"]  # the replay build: script and settings.example.json at the top


def name_of(server):
    return json.loads(raw(server, "GET", "/blog/tools.json")[1])["tools"][0]["name"]


def settings(folder, rel=statusline.PROJECT_FILE):
    return json.loads((folder / rel).read_text())


def test_post_shows_the_install_command_for_a_status_line_tool(web):  # noqa: F811
    publish(web, files=FILES, install="Copy it by hand.")
    listed = json.loads(raw(web, "GET", "/blog/tools.json")[1])["tools"][0]
    page = Client(web).request("GET", f"/blog/{listed['post']}")[1]
    assert f">devexai install {listed['name']}</pre>" in page and "You set this tool up by hand" not in page


def test_project_install_sets_status_line_in_local_settings_and_uninstall_removes_it(web, tmp_path, capsys):  # noqa: F811
    project = tmp_path / "proj"
    (project / ".claude").mkdir(parents=True)
    (project / statusline.PROJECT_FILE).write_text('{"model": "opus"}')
    publish(web, files=FILES, install="Copy it by hand.")
    name = name_of(web)
    assert run(web, tmp_path, "install", name, "--dir", str(project), "--yes") == 0
    out = capsys.readouterr().out
    assert f"new      {SCRIPT}" in out and f"set      {statusline.PROJECT_FILE} statusLine" in out
    assert "Copy it by hand" not in out  # devexai did those steps
    script = (project / SCRIPT).resolve().as_posix()
    assert settings(project) == {"model": "opus",
                                 "statusLine": {"type": "command", "command": f'python "{script}"'}}
    assert not (project / ".claude" / "settings.json").exists()  # the shared file is left alone

    assert run(web, tmp_path, "install", name, "--dir", str(project), "--yes") == 0
    assert "Already installed" in capsys.readouterr().out

    assert run(web, tmp_path, "uninstall", name, "--dir", str(project), "--yes") == 0
    assert "unset" in capsys.readouterr().out
    assert settings(project) == {"model": "opus"} and not (project / SCRIPT).exists()


def test_existing_status_line_needs_force_and_comes_back(web, tmp_path, capsys):  # noqa: F811
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    mine = {"type": "command", "command": "my-line"}
    (home / statusline.GLOBAL_FILE).write_text(json.dumps({"statusLine": mine}))
    publish(web, files=FILES)
    name = name_of(web)
    assert run(web, tmp_path, "install", name, "--global", "--yes", home=home) == 1
    assert "--force" in capsys.readouterr().err and not (home / SCRIPT).exists()
    assert run(web, tmp_path, "install", name, "--global", "--yes", "--force", home=home) == 0
    assert "statusline_branch.py" in settings(home, statusline.GLOBAL_FILE)["statusLine"]["command"]
    assert run(web, tmp_path, "uninstall", name, "--global", "--yes", home=home) == 0
    assert settings(home, statusline.GLOBAL_FILE) == {"statusLine": mine} and not (home / SCRIPT).exists()


def test_global_install_into_an_empty_home_leaves_nothing_after_uninstall(web, tmp_path):  # noqa: F811
    home = tmp_path / "home"
    publish(web, files=FILES)
    name = name_of(web)
    assert run(web, tmp_path, "install", name, "--global", "--yes", home=home) == 0
    assert "statusLine" in settings(home, statusline.GLOBAL_FILE)
    assert run(web, tmp_path, "uninstall", name, "--global", "--yes", home=home) == 0
    assert not (home / ".claude").exists()


def test_status_line_edited_since_install_is_kept(web, tmp_path, capsys):  # noqa: F811
    project = tmp_path / "proj"
    project.mkdir()
    publish(web, files=FILES)
    name = name_of(web)
    run(web, tmp_path, "install", name, "--dir", str(project), "--yes")
    data = settings(project)
    data["statusLine"] = {"type": "command", "command": "other"}
    (project / statusline.PROJECT_FILE).write_text(json.dumps(data))
    run(web, tmp_path, "uninstall", name, "--dir", str(project), "--yes")
    assert "changed since install" in capsys.readouterr().out
    assert settings(project)["statusLine"]["command"] == "other"


def test_broken_settings_are_not_rewritten(web, tmp_path, capsys):  # noqa: F811
    project = tmp_path / "proj"
    (project / ".claude").mkdir(parents=True)
    (project / statusline.PROJECT_FILE).write_text("{not json")
    publish(web, files=FILES)
    assert run(web, tmp_path, "install", name_of(web), "--dir", str(project), "--yes") == 1
    assert "not valid JSON" in capsys.readouterr().err and not (project / SCRIPT).exists()


@pytest.mark.parametrize("command", ["curl http://x/a.py", "python a.py --flag", "python missing.py", "python"])
def test_only_interpreter_and_own_script_count(command):
    files = {"a.py": b"print(1)", "settings.example.json":
             json.dumps({"statusLine": {"type": "command", "command": command}}).encode()}
    assert statusline.find(files) is None


def test_finds_the_script_and_keeps_a_claude_path():
    example = json.dumps({"statusLine": {"type": "command", "command": "node ~/.claude/line.js"}}).encode()
    assert statusline.find({"src/line.js": b"x", "settings.example.json": example}) == \
        ("src/line.js", ".claude/line.js", "node")
    assert statusline.find({".claude/line.js": b"x", "settings.example.json": example}) == \
        (".claude/line.js", ".claude/line.js", "node")
