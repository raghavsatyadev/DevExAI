import io
import json
import zipfile

import pytest
from test_blog import raw
from test_web import Client, make_server

from devexai.chat import Event
from devexai.stages import Stage
from devexai_cli import cli, files, tools
from devexai_cli.net import DevexError

SKILL = ".claude/skills/lint/SKILL.md"
HELPER = ".claude/skills/lint/run_lint.py"
FILES = [{"path": "README.md", "content": "# Lint\n"},
         {"path": SKILL, "content": "---\nname: lint\n---\nRun run_lint.py.\n"},
         {"path": HELPER, "content": "print('lint')\n"},
         {"path": "tests/test_lint.py", "content": "def test(): pass\n"}]


@pytest.fixture
def web(tmp_path):
    server = make_server(tmp_path)
    yield server
    server.shutdown()
    server.server_close()


def publish(server, files=FILES, text="Run ktlint before commit", install="Add \x1b[31mlint\x1b[0m to CI."):
    bot = server.bot
    bot.handle(Event("carol", text, bot.settings.ideas_channel))
    idea = bot.store.ideas.list(1)[0]
    bot.store.ideas.update(idea.id, build={"files": files, "install": install})
    for cmd in (f"/devex-approve {idea.id}", f"/devex-built {idea.id}", f"/devex-publish {idea.id} ok"):
        bot.handle(Event("alice", cmd, bot.settings.ideas_channel))
    idea = bot.store.ideas.get(idea.id)
    assert idea.stage is Stage.PUBLISHED
    return idea


def url(server):
    return f"http://127.0.0.1:{server.server_address[1]}"


def run(server, tmp_path, *args, home=None):
    return cli.main([*args, "--server", url(server)], home=home or tmp_path / "home")


def test_tool_list_has_only_published_tools_and_the_post_shows_the_commands(web, tmp_path):
    bot = web.bot
    bot.handle(Event("dan", "Unpublished idea", bot.settings.ideas_channel))
    bot.store.ideas.update(bot.store.ideas.list(1)[0].id, build={"files": FILES})
    idea = publish(web)
    resp, data = raw(web, "GET", "/blog/tools.json")
    listed = json.loads(data)["tools"]
    assert resp.status == 200 and [t["id"] for t in listed] == [idea.id]
    resp, _ = raw(web, "GET", "/blog/devex.py")
    assert resp.status == 303 and resp.getheader("Location") == "/get"  # the old script is gone
    page = Client(web).request("GET", f"/blog/{listed[0]['post']}")[1]
    assert f">devexai install {listed[0]['name']}</pre>" in page
    assert '<ol class="steps">' in page and ">--global</code>" in page
    assert f"devexai uninstall {listed[0]['name']}" in page and f'href="{url(web)}/get"' in page


def test_install_project_then_uninstall(web, tmp_path, capsys):
    idea = publish(web)
    project = tmp_path / "proj"
    (project / ".claude").mkdir(parents=True)  # exists before: must survive uninstall
    assert run(web, tmp_path, "install", str(idea.id), "--project", "--dir", str(project), "--yes") == 0
    out = capsys.readouterr().out
    assert f"new      {SKILL}" in out and "README.md" not in out
    assert "Add lint to CI." in out and "\x1b" not in out  # manual steps, no terminal escapes
    assert (project / HELPER).read_text() == "print('lint')\n"
    assert not (project / "README.md").exists() and not (project / "tests").exists()
    name = json.loads(raw(web, "GET", "/blog/tools.json")[1])["tools"][0]["name"]
    receipt = json.loads((project / ".devex" / f"{name}.json").read_text())
    assert set(receipt["files"]) == {SKILL, HELPER} and receipt["dirs"] == [".claude/skills", ".claude/skills/lint"]

    assert run(web, tmp_path, "install", name, "--project", "--dir", str(project), "--yes") == 0
    assert "Already installed" in capsys.readouterr().out

    assert run(web, tmp_path, "uninstall", name, "--project", "--dir", str(project), "--yes") == 0
    assert not (project / ".claude" / "skills").exists() and not (project / ".devex").exists()
    assert (project / ".claude").is_dir()


def test_edited_file_is_kept_on_uninstall(web, tmp_path, capsys):
    idea = publish(web)
    project = tmp_path / "proj"
    project.mkdir()
    run(web, tmp_path, "install", str(idea.id), "--project", "--dir", str(project), "--yes")
    (project / HELPER).write_text("print('mine')\n")
    name = json.loads(raw(web, "GET", "/blog/tools.json")[1])["tools"][0]["name"]
    run(web, tmp_path, "uninstall", name, "--project", "--dir", str(project), "--yes")
    assert "keep     " + HELPER in capsys.readouterr().out
    assert (project / HELPER).read_text() == "print('mine')\n" and not (project / SKILL).exists()


def test_foreign_file_needs_force_and_comes_back(web, tmp_path, capsys):
    idea = publish(web)
    project = tmp_path / "proj"
    (project / SKILL).parent.mkdir(parents=True)
    (project / SKILL).write_text("my own skill\n")
    assert run(web, tmp_path, "install", str(idea.id), "--project", "--dir", str(project), "--yes") == 1
    assert "--force" in capsys.readouterr().err and (project / SKILL).read_text() == "my own skill\n"
    assert not (project / HELPER).exists()
    assert run(web, tmp_path, "install", str(idea.id), "--project", "--dir", str(project), "--yes", "--force") == 0
    assert (project / SKILL).read_text().startswith("---")
    name = json.loads(raw(web, "GET", "/blog/tools.json")[1])["tools"][0]["name"]
    run(web, tmp_path, "uninstall", name, "--project", "--dir", str(project), "--yes")
    assert (project / SKILL).read_text() == "my own skill\n" and not (project / HELPER).exists()


def test_global_goes_to_home_and_server_is_remembered(web, tmp_path):
    idea = publish(web)
    home = tmp_path / "home"
    assert run(web, tmp_path, "install", str(idea.id), "--global", "--yes", home=home) == 0
    assert (home / SKILL).is_file()
    assert cli.main(["list"], home=home) == 0  # no --server: the saved one
    name = json.loads(raw(web, "GET", "/blog/tools.json")[1])["tools"][0]["name"]
    assert cli.main(["uninstall", name, "--global", "--yes"], home=home) == 0
    assert not (home / ".claude").exists()


def test_asks_and_refuses_without_a_terminal(web, tmp_path, capsys):
    idea = publish(web)
    project = tmp_path / "proj"
    project.mkdir()
    assert run(web, tmp_path, "install", str(idea.id), "--project", "--dir", str(project)) == 1
    assert "--yes" in capsys.readouterr().err and not (project / ".claude").exists()


def test_nothing_installable_points_to_readme(web, tmp_path, capsys):
    idea = publish(web, files=[{"path": "README.md", "content": "x"}, {"path": "a.py", "content": "y"}])
    assert run(web, tmp_path, "install", str(idea.id), "--project", "--dir", str(tmp_path), "--yes") == 0
    assert "nothing to install automatically" in capsys.readouterr().out


def test_unknown_and_ambiguous_names(web, tmp_path, capsys):
    first, second = publish(web), publish(web, text="Run ktlint before commit please")
    assert run(web, tmp_path, "install", "nope", "--project", "--dir", str(tmp_path), "--yes") == 1
    assert "no published tool" in capsys.readouterr().err
    names = [t["name"] for t in json.loads(raw(web, "GET", "/blog/tools.json")[1])["tools"]]
    assert names[0] == names[1]  # same title, so the same name: the number tells them apart
    assert run(web, tmp_path, "install", names[0], "--project", "--dir", str(tmp_path), "--yes") == 1
    assert f"#{first.id}" in capsys.readouterr().err
    assert run(web, tmp_path, "install", str(second.id), "--project", "--dir", str(tmp_path), "--yes") == 0


def zipped(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.parametrize("entries", [
    [("../evil.md", "x")], [("/abs.md", "x")], [("C:/x.md", "x")], [(".claude/a\\..\\b.md", "x")],
    [(".claude/A.md", "x"), (".claude/a.md", "y")], [(f".claude/{i}.md", "x") for i in range(41)],
    [(".claude/big.md", "x" * 1_000_001)],
])
def test_bad_downloads_are_refused(entries):
    with pytest.raises(DevexError):
        files.read_zip(zipped(entries))


def test_receipt_outside_assistant_folders_is_refused(tmp_path):
    (tmp_path / ".devex").mkdir()
    (tmp_path / ".devex" / "x.json").write_text(json.dumps({"files": {"src/main.py": "0"}}))
    with pytest.raises(DevexError, match="not touching"):
        tools.uninstall("x", tmp_path, yes=True)


def test_idea_page_shows_the_install_command_once_published(web):
    c = Client(web)
    c.login()
    idea = publish(web)
    name = json.loads(raw(web, "GET", "/blog/tools.json")[1])["tools"][0]["name"]
    assert f"<code>devexai install {name}</code>" in c.request("GET", f"/idea/{idea.id}")[1]
