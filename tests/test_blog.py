import pytest
from test_web import Client, make_server

from devexai.chat import Event
from devexai.stages import Stage
from devexai.web import blog


@pytest.fixture
def web(tmp_path):
    server = make_server(tmp_path)
    yield server
    server.shutdown()
    server.server_close()


def publish(server):
    bot = server.bot
    bot.handle(Event("carol", "Run ktlint before commit <script>x</script>", bot.settings.ideas_channel))
    idea = bot.store.ideas.list(10)[0]
    for text in (f"/devex-approve {idea.id}", f"/devex-built {idea.id}", f"/devex-publish {idea.id} run **it**"):
        bot.handle(Event("alice", text, bot.settings.ideas_channel))
    idea = bot.store.ideas.get(idea.id)
    assert idea.stage is Stage.PUBLISHED
    return idea


def test_published_post_is_public_and_escaped(web):
    idea = publish(web)
    name = next(web.bot.settings.blog.dir.glob("*.md")).name
    client = Client(web)  # not signed in
    resp, index = client.request("GET", "/blog")
    assert resp.status == 200 and f'href="/blog/{name}"' in index and "Lint  b skill /b" in index
    resp, page = client.request("GET", f"/blog/{name}")
    assert resp.status == 200 and "<h1>Lint &lt;b&gt;skill&lt;/b&gt;</h1>" in page
    assert "<script>" not in page and "<li>SKILL.md</li>" in page
    assert "run <strong>it</strong>" not in page and "run **it**" in page  # the install note stays plain text
    assert idea.id


def test_bad_names_are_not_found(web, tmp_path):
    (tmp_path / "secret.md").write_text("x", encoding="utf-8")
    client = Client(web)
    for path in ("/blog/../secret.md", "/blog/secret.md", "/blog/0001-x.txt", "/blog/0001-missing.md",
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
