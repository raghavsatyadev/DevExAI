import pytest

from devexai.chat.slack_check import Check
from devexai.web import slack_routes

from test_web import Client, make_server

BOT = "xoxb-1234567890-secretvalue"
APP = "xapp-1-A0-secretvalue123"


@pytest.fixture
def admin(tmp_path, monkeypatch):
    for key in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "DEVEXAI_LICENCE_KEY"):
        monkeypatch.setenv(key, "")
    server = make_server(tmp_path)
    server.env_path = tmp_path / ".env"
    yield server, Client(server).login()
    server.shutdown()


def post(c, **form):
    return c.request("POST", "/slack", {"csrf": c.csrf("/slack"), **form})


def test_slack_page_is_admin_only(admin):
    server, _ = admin
    bob = Client(server).login("bob@example.com")
    assert bob.request("GET", "/slack")[0].status == 404
    assert 'href="/slack"' not in bob.request("GET", "/")[1]


def test_tokens_are_saved_but_never_shown(admin):
    server, c = admin
    resp, _ = post(c, op="tokens", bot_token=BOT, app_token=APP)
    assert resp.status == 303
    page = c.request("GET", "/slack")[1]
    assert "Tokens saved" in page and "secretvalue" not in page and page.count("pill done\">set") == 2
    env = server.env_path.read_text(encoding="utf-8")
    assert f"SLACK_BOT_TOKEN={BOT}" in env and f"SLACK_APP_TOKEN={APP}" in env
    with server.bot.store.audit.db.connect() as db:
        details = [r[0] for r in db.execute("SELECT detail FROM audit")]
    assert "SLACK_APP_TOKEN, SLACK_BOT_TOKEN" in details and not any("secretvalue" in d for d in details)


def test_bad_token_and_bad_channel_are_refused(admin):
    server, c = admin
    post(c, op="tokens", bot_token="xapp-wrong-kind-of-token", app_token="")
    assert "does not look like" in c.request("GET", "/slack")[1]
    assert not server.env_path.exists()
    post(c, op="channels", ideas="#Bad Name", public="#ai-tools")
    assert "Channel names are" in c.request("GET", "/slack")[1]


def test_channels_apply_live(admin):
    server, c = admin
    post(c, op="channels", ideas="dev-ideas", public="#dev-tools")
    assert server.bot.settings.ideas_channel == "#dev-ideas"
    assert server.bot.store.meta.get("cfg:public_channel") == "#dev-tools"


def test_licence_and_test_results(admin, monkeypatch):
    server, c = admin
    post(c, op="licence", licence="LIC-12345678")
    assert "DEVEXAI_LICENCE_KEY=LIC-12345678" in server.env_path.read_text(encoding="utf-8")
    monkeypatch.setattr(slack_routes, "check_slack", lambda *a: [Check(True, "Bot token works."),
                                                                 Check(False, "Invite the <bot>.")])
    post(c, op="test")
    page = c.request("GET", "/slack")[1]
    assert "1 thing(s) to fix" in page and "Invite the &lt;bot&gt;." in page


def test_connect_failure_keeps_running(admin):
    server, c = admin
    before = server.bot.chat
    post(c, op="connect")  # no tokens: refused, the old platform stays
    assert "Could not connect" in c.request("GET", "/slack")[1] and server.bot.chat is before
