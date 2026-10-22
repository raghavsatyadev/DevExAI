import base64
import hashlib
import http.client
import io
import re
import zipfile

import pytest
from test_web import Client, make_server

from devexai.chat import Event
from devexai.flow import post
from devexai.stages import Stage
from devexai.web import blog


@pytest.fixture
def web(tmp_path):
    server = make_server(tmp_path)
    yield server
    server.shutdown()
    server.server_close()


FILES = [{"path": "README.md", "content": "# Tool\n\n## Install\n\n1. Copy `a.py` to `~/.claude/`.\n"
                                         "2. Run:\n   `python a.py --x <y>`\n\n```\npip install x && echo '<b>'\n```\n"},
         {"path": "a.py", "content": "print('<script>&amp;')\n"},
         {"path": "tests/test_a.py", "content": "def test(): pass\n"}]


def raw(server, method, path):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    conn.request(method, path, headers={"Host": f"127.0.0.1:{server.server_address[1]}"})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp, data


def publish(server):
    bot = server.bot
    bot.handle(Event("carol", "Run ktlint before commit <script>x</script>", bot.settings.ideas_channel))
    idea = bot.store.ideas.list(10)[0]
    bot.store.ideas.update(idea.id, build={"files": FILES})
    for text in (f"/devex-approve {idea.id}", f"/devex-built {idea.id}", f"/devex-publish {idea.id} run **it**"):
        bot.handle(Event("alice", text, bot.settings.ideas_channel))
    idea = bot.store.ideas.get(idea.id)
    assert idea.stage is Stage.PUBLISHED
    return idea


def test_published_post_is_public_and_escaped(web):
    idea = publish(web)
    name = next(web.bot.settings.blog.dir.glob("*.html")).name
    client = Client(web)  # not signed in
    resp, index = client.request("GET", "/blog")
    assert resp.status == 200 and f'href="/blog/{name}"' in index and "Lint &lt;b&gt;skill&lt;/b&gt;" in index
    resp, page = client.request("GET", f"/blog/{name}")
    assert resp.status == 200 and "<h1>Lint &lt;b&gt;skill&lt;/b&gt;</h1>" in page
    assert page.count("<script>") == 1 and "<li>SKILL.md</li>" in page
    assert "run <strong>it</strong>" not in page and "run **it**" in page  # the install note stays plain text
    assert idea.id


def test_bad_names_are_not_found(web, tmp_path):
    (tmp_path / "secret.md").write_text("x", encoding="utf-8")
    client = Client(web)
    for path in ("/blog/../secret.md", "/blog/secret.md", "/blog/0001-x.txt", "/blog/0001-missing.html",
                 "/blog/%2e%2e%2fsecret.md"):
        assert client.request("GET", path)[0].status == 404


def test_empty_blog(web):
    resp, text = Client(web).request("GET", "/blog/")
    assert resp.status == 200 and "No tools published yet" in text


def test_hand_edited_html_is_shown_as_text():
    html = blog.to_html("Hi <img src=x onerror=alert(1)> &amp; **bold** \\*no\\*\n- a\n- b\n\n## Next")
    assert "<img" not in html and "&lt;img" in html and "<strong>bold</strong>" in html and "*no*" in html
    assert "<ul><li>a</li><li>b</li></ul>" in html and "<h3>Next</h3>" in html


def test_front_matter():
    front, body = blog.split_front('---\ntitle: "A \\"q\\""\nidea: 3\n---\n# A\n')
    assert front == {"title": 'A "q"', "idea": "3"} and body == "# A\n"
    assert blog.split_front("no front")[0] == {}


def test_published_tool_files_can_be_copied_and_downloaded(web):
    publish(web)
    name = next(web.bot.settings.blog.dir.glob("*.html")).name
    resp, page = Client(web).request("GET", f"/blog/{name}")
    script = re.search(r"<script>(.*?)</script>", page, re.DOTALL).group(1)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in resp.getheader("Content-Security-Policy")
    assert f'href="/blog/{name}/files.zip"' in page and "<h2>Files</h2>" in page
    assert "print('&lt;script&gt;&amp;amp;')" in page
    assert '<code data-copy="" title="Click to copy">python a.py --x &lt;y&gt;</code>' in page
    assert "pip install x &amp;&amp; echo '&lt;b&gt;'</pre>" in page and "<ol>" in page
    assert f"curl.exe --ssl-no-revoke -fLo lint-b-skill-b.zip http://127.0.0.1:{web.server_address[1]}/blog/{name}/files.zip" in page

    resp, data = raw(web, "GET", f"/blog/{name}/files.zip")
    assert resp.status == 200 and resp.getheader("Content-Type") == "application/zip"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert sorted(zf.namelist()) == ["README.md", "a.py", "tests/test_a.py"]
        assert zf.read("a.py") == b"print('<script>&amp;')\n"
    resp, data = raw(web, "GET", f"/blog/{name}/files/tests/test_a.py")
    assert resp.status == 200 and data == b"def test(): pass\n"
    assert resp.getheader("Content-Type") == "text/plain; charset=utf-8"
    assert resp.getheader("Content-Disposition") == 'attachment; filename="test_a.py"'
    resp, data = raw(web, "HEAD", f"/blog/{name}/files.zip")
    assert resp.status == 200 and data == b"" and int(resp.getheader("Content-Length")) > 0
    for bad in ("files/missing.py", "files/../a.py", "files/%2e%2e/a.py", "files/A.PY", "other.zip"):
        assert raw(web, "GET", f"/blog/{name}/{bad}")[0].status == 404


def test_files_only_for_published_ideas(web):
    bot = web.bot
    bot.handle(Event("carol", "Run ktlint before commit", bot.settings.ideas_channel))
    idea = bot.store.ideas.update(bot.store.ideas.list(10)[0].id, build={"files": FILES})
    name = post.filename(idea)
    bot.settings.blog.dir.mkdir(parents=True, exist_ok=True)
    (bot.settings.blog.dir / name).write_text("# Hand placed\n", encoding="utf-8")
    resp, page = Client(web).request("GET", f"/blog/{name}")
    assert resp.status == 200 and "files.zip" not in page
    assert raw(web, "GET", f"/blog/{name}/files.zip")[0].status == 404
    assert raw(web, "GET", f"/blog/{name}/files/a.py")[0].status == 404


def test_dashboard_pages_allow_no_scripts(web):
    resp, _ = Client(web).request("GET", "/login")
    assert "script-src" not in resp.getheader("Content-Security-Policy")


def test_hand_edited_post_is_cleaned(web):
    folder = web.bot.settings.blog.dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "0042-x.html").write_text(
        '<!-- devexai-post {"title": "X"} --><article><h1 onclick="a()">X</h1><meta http-equiv="refresh" '
        'content="0;url=https://evil.example"><form action="https://evil.example"><input name=p></form>'
        '<script>alert(1)</script><style>body{display:none}</style><p style="x">ok <a href="javascript:a">j</a> '
        '<a href="https://example.com/a">w</a></p></article>', encoding="utf-8")
    page = Client(web).request("GET", "/blog/0042-x.html")[1]
    for bad in ("refresh", "<form", "<input", "alert(1)", "body{display:none}", "onclick", "javascript:", 'style="x"'):
        assert bad not in page
    assert "<a>j</a>" in page and '<a href="https://example.com/a">w</a>' in page and "<h1>X</h1>" in page


def test_old_markdown_post_becomes_html_and_old_links_redirect(web):
    idea = publish(web)
    folder, new = web.bot.settings.blog.dir, post.filename(idea)
    old = new[:-5] + ".md"
    (folder / new).replace(folder / old.replace(".md", ".gone"))
    (folder / old).write_text('---\ntitle: "T"\ndate: 2026-10-01\nmaintainer: "bob"\n---\n# T\n\n'
                              '## Install\n\nRun \\`x\\`.\n', encoding="utf-8")
    web.bot.store.ideas.update(idea.id, blog_url=f"http://h/blog/{old}")
    assert post.migrate(folder, web.bot.store) == [new]
    assert (folder / (old + ".old")).exists() and not (folder / old).exists()
    text = (folder / new).read_text(encoding="utf-8")
    assert r"2026\u002d10\u002d01" in text and "@bob" in text and "Run `x`." in text
    assert web.bot.store.ideas.get(idea.id).blog_url == f"http://h/blog/{new}"
    assert post.migrate(folder, web.bot.store) == []
    resp, _ = raw(web, "GET", f"/blog/{old}/files.zip")
    assert resp.status == 303 and resp.getheader("Location") == f"/blog/{new}/files.zip"


def publish_with(server, build):
    idea = publish(server)
    server.bot.store.ideas.update(idea.id, build=build)
    return next(server.bot.settings.blog.dir.glob("*.html")).name


def install_panel(page):
    return re.search(r'<div class="panel lift" id="install">(.*?)</aside>', page, re.DOTALL).group(1)


def test_tool_set_up_by_hand_shows_its_own_steps(web):
    from devexai.llm.samples import SAMPLES
    build = SAMPLES["builder"]  # the replay status-line tool: one script copied by hand, no .claude/ files
    name = publish_with(web, {"files": build["files"], "install": build["install"]})
    side = install_panel(Client(web).request("GET", f"/blog/{name}")[1])
    assert "devexai install lint" not in side and "devexai uninstall" not in side and "Get DevExAI" not in side
    assert "set this tool up by hand" in side
    assert "Copy statusline_branch.py to ~/.claude/ and add the statusLine entry" in side
    assert "curl.exe --ssl-no-revoke -fLo lint-b-skill-b.zip" in side and "unzip -d lint-b-skill-b" in side
    assert "Notes from the maintainer" in side and "run **it**" in side
    assert "\u2014" not in side
    web.bot.store.ideas.update(web.bot.store.ideas.list(10)[0].id, build={"files": build["files"], "install": "run **it**"})
    side = install_panel(Client(web).request("GET", f"/blog/{name}")[1])
    assert "Notes from the maintainer" not in side and "**it**" not in side  # the note repeats the steps: once
    assert side.count("<strong>it</strong>") == 1


def test_tool_by_hand_steps_are_escaped_and_have_a_fallback(web):
    name = publish_with(web, {"files": FILES, "install": "Run `rm <x>` then <script>alert(1)</script>"})
    page = Client(web).request("GET", f"/blog/{name}")[1]
    side = install_panel(page)
    assert "&lt;script&gt;" in side and page.count("<script>") == 1
    assert '<code data-copy="" title="Click to copy">rm &lt;x&gt;</code>' in side
    web.bot.store.ideas.update(web.bot.store.ideas.list(10)[0].id, build={"files": FILES})
    side = install_panel(Client(web).request("GET", f"/blog/{name}")[1])
    assert "The README in the files says how to set it up." in side


def test_tool_devexai_can_install_keeps_the_install_command(web):
    files = FILES + [{"path": ".claude/skills/lint/SKILL.md", "content": "# Lint\n"}]
    name = publish_with(web, {"files": files, "install": "Restart Claude Code."})
    page = Client(web).request("GET", f"/blog/{name}")[1]
    side = install_panel(page)
    assert "devexai install lint-b-skill-b" in side and "devexai uninstall lint-b-skill-b" in side
    assert "set this tool up by hand" not in side and "curl.exe" not in side
    assert "Download and unpack with one command" in page
