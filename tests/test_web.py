import http.client
import re
import urllib.parse

import pytest

from devexai.chat import Event
from devexai.chat.fake import FakeChat
from devexai.config import BlogSettings, Maintainer, Settings, WebSettings
from devexai.flow.bot import Bot
from devexai.llm.stub import StubLLM
from devexai.stages import Stage
from devexai.store import Store
from devexai.web import Dashboard

PASSWORD = "correct horse battery"
GATE = {"verdict": "pass", "reasons": [], "topic": "android", "title": "Lint <b>skill</b>", "injection_found": False}
PLAN = {"summary": "A ktlint skill.", "assistants": ["Claude Code"], "deliverables": ["SKILL.md"],
        "test_plan": "pytest", "size": "small", "resources": [], "duplicate_of": [], "existing_tools": [],
        "questions": []}


class Client:
    """http.client, not urllib: no system proxies, and full control of Host/Origin headers."""

    def __init__(self, server):
        self.server = server
        self.port = server.server_address[1]
        self.host = f"127.0.0.1:{self.port}"
        self.cookie = ""

    def request(self, method, path, form=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = urllib.parse.urlencode(form) if form is not None else None
        hdrs = {"Host": self.host, **({"Cookie": self.cookie} if self.cookie else {})}
        if body is not None:
            hdrs |= {"Content-Type": "application/x-www-form-urlencoded", "Origin": f"http://{self.host}"}
        hdrs |= headers or {}
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        text = resp.read().decode()
        conn.close()
        if cookie := resp.getheader("Set-Cookie"):
            self.cookie = cookie.split(";")[0]
        return resp, text

    def login(self, email="alice@example.com", password=PASSWORD):
        resp, _ = self.request("POST", "/login", {"email": email, "password": password})
        assert resp.status == 303 and self.cookie.split("=", 1)[1]
        return self

    def csrf(self, path="/"):
        return re.search(r'name="csrf" value="([^"]+)"', self.request("GET", path)[1]).group(1)

    def act(self, action, idea_id, text=""):
        return self.request("POST", "/action", {"csrf": self.csrf(f"/idea/{idea_id}"), "action": action,
                                                "idea": idea_id, "text": text})

    def people(self, **form):
        return self.request("POST", "/people", {"csrf": self.csrf("/people"), **form})


def make_server(tmp_path, passwords=True):
    settings = Settings(maintainers=(Maintainer("alice", ("android",), "alice@example.com", admin=True),
                                     Maintainer("bob", (), "bob@example.com")),
                        blog=BlogSettings(dir=tmp_path / "blog"), db_path=tmp_path / "devexai.db",
                        build_by="person")
    bot = Bot(settings, Store(":memory:"), FakeChat(), StubLLM({"gate": GATE, "planner": PLAN}), inline_jobs=True)
    if passwords:
        bot.store.people.set_password("alice", PASSWORD)
        bot.store.people.set_password("bob", PASSWORD)
    server = Dashboard(bot, WebSettings(port=0))
    server.start()
    return server


@pytest.fixture
def web(tmp_path):
    server = make_server(tmp_path)
    yield server
    server.shutdown()
    server.server_close()


def submit(server, text="Run ktlint"):
    server.bot.handle(Event("carol", text, "#ai-ideas"))
    return server.bot.store.ideas.list()[0]


def test_network_serving_needs_tls_or_explicit_opt_in():
    with pytest.raises(ValueError, match="tls_cert"):
        Dashboard(None, WebSettings(host="0.0.0.0", port=0))


def test_needs_sign_in(web):
    c = Client(web)
    resp, _ = c.request("GET", "/")
    assert resp.status == 303 and resp.getheader("Location") == "/login"
    assert c.request("POST", "/login", {"email": "alice@example.com", "password": "wrong-password"})[0].status == 401
    assert not c.cookie
    c.login()
    resp, text = c.request("GET", "/")
    assert resp.status == 200 and "Ideas" in text and "Signed in as" in text
    assert resp.getheader("Content-Security-Policy").startswith("default-src 'none'")
    assert web.setup_token is None and "sign in with email and password" in web.startup_message()


def test_wrong_passwords_lock_out(web):
    c = Client(web)
    for _ in range(5):
        c.request("POST", "/login", {"email": "alice@example.com", "password": "nope-nope-nope"})
    resp, text = c.request("POST", "/login", {"email": "alice@example.com", "password": PASSWORD})
    assert resp.status == 429 and "Wait 15 minutes" in text and not c.cookie


def test_first_run_setup_creates_admin(tmp_path):
    server = make_server(tmp_path, passwords=False)
    try:
        token = server.setup_token
        assert token and token in server.startup_message()
        c = Client(server)
        assert c.request("GET", "/setup?token=wrong")[0].status == 401
        assert "alice" in c.request("GET", f"/setup?token={token}")[1]
        form = {"token": token, "email": "raghav@example.com", "password": PASSWORD, "password2": "different-pw"}
        assert "different" in c.request("POST", "/setup", form)[1]
        resp, _ = c.request("POST", "/setup", {**form, "password2": PASSWORD})
        assert resp.status == 303 and server.setup_token is None
        assert "Welcome!" in c.request("GET", "/")[1]
        assert c.request("GET", f"/setup?token={token}")[0].status == 303  # the link is spent
        Client(server).login("raghav@example.com")
    finally:
        server.shutdown()
        server.server_close()


def test_rejects_foreign_host_and_origin(web):
    c = Client(web).login()
    idea = submit(web)
    assert c.request("GET", "/", headers={"Host": "evil.example"})[0].status == 421
    csrf = c.csrf()
    form = {"csrf": csrf, "action": "approve", "idea": idea.id}
    assert c.request("POST", "/action", form, {"Origin": "https://evil.example"})[0].status == 403
    assert c.request("POST", "/action", {**form, "csrf": "nope"})[0].status == 403
    assert web.bot.store.ideas.get(idea.id).stage is Stage.PLAN_READY


def test_approve_moves_stage_and_posts_in_thread(web):
    c = Client(web).login()
    idea = submit(web)
    resp, _ = c.act("approve", idea.id)
    assert resp.status == 303 and resp.getheader("Location") == f"/idea/{idea.id}"
    assert web.bot.store.ideas.get(idea.id).stage is Stage.BUILDING
    assert "approved by @alice" in web.bot.chat.in_thread(idea.thread_ref)[-1]
    assert any(a["action"] == "web" for a in web.bot.store.audit.for_idea(idea.id))


def test_refusal_shows_on_page(web):
    c = Client(web).login()
    idea = submit(web)
    c.act("publish", idea.id)
    assert "only a reviewed tool can be published" in c.request("GET", f"/idea/{idea.id}")[1]


def test_actions_run_as_signed_in_person(web):
    c = Client(web).login("bob@example.com")
    idea = submit(web)
    c.act("assign", idea.id, "bob")
    assert web.bot.store.ideas.get(idea.id).maintainer == "bob"
    assert web.bot.store.audit.for_idea(idea.id)[-1]["actor"] == "bob"
    c.act("assign", idea.id, "bob")
    assert "already looks after" in c.request("GET", f"/idea/{idea.id}")[1]


def test_only_admins_manage_people(web):
    bob = Client(web).login("bob@example.com")
    assert "People</a>" not in bob.request("GET", "/")[1]
    assert bob.request("GET", "/people")[0].status == 404
    resp, _ = bob.request("POST", "/people", {"csrf": bob.csrf(), "op": "add", "name": "eve"})
    assert resp.status == 404 and web.bot.store.people.get("eve") is None


def test_admin_adds_and_deactivates_people(web):
    alice = Client(web).login()
    idea = submit(web)
    assert web.bot.store.ideas.get(idea.id).maintainer == "alice"
    alice.people(op="add", name="dana", email="dana@example.com", role="maintainer", topics="android, web",
                 password=PASSWORD)
    dana = Client(web).login("dana@example.com")
    assert web.bot.store.people.get("dana").topics == ("android", "web")
    alice.people(op="deactivate", name="alice")
    assert "cannot deactivate yourself" in alice.request("GET", "/people")[1]
    alice.people(op="edit", name="alice", email="alice@example.com", role="maintainer", topics="android")
    assert "at least one active admin" in alice.request("GET", "/people")[1]
    alice.people(op="deactivate", name="dana")
    assert dana.request("GET", "/")[0].status == 303  # signed out
    assert not web.bot.router.is_maintainer("dana")
    alice.people(op="password", name="bob", password="short")
    assert "at least 10" in alice.request("GET", "/people")[1]


def test_deactivating_hands_over_open_ideas(web):
    alice = Client(web).login()
    idea = submit(web)
    alice.people(op="add", name="zed", email="zed@example.com", role="admin", topics="")
    alice.people(op="password", name="zed", password=PASSWORD)
    zed = Client(web).login("zed@example.com")
    zed.people(op="deactivate", name="alice")
    assert web.bot.store.ideas.get(idea.id).maintainer in ("bob", "zed")
    assert "now looks after" in web.bot.chat.in_thread(idea.thread_ref)[-1]
    assert alice.request("GET", "/")[0].status == 303


def test_change_own_password(web):
    c = Client(web).login()
    other = Client(web).login()
    form = {"current": "wrong", "password": "a new password", "password2": "a new password"}
    c.request("POST", "/account", {**form, "csrf": c.csrf("/account")})
    assert "current password is wrong" in c.request("GET", "/account")[1]
    resp, _ = c.request("POST", "/account", {**form, "csrf": c.csrf("/account"), "current": PASSWORD})
    assert resp.status == 303 and "Password changed" in c.request("GET", "/")[1]
    assert other.request("GET", "/")[0].status == 303
    Client(web).login(password="a new password")


def test_allowed_hosts_extend_origins(web):
    web.web = WebSettings(port=web.port, allowed_hosts=("devexai.corp.local",))
    assert f"devexai.corp.local:{web.port}" in web.origins
    c = Client(web)
    c.host = f"devexai.corp.local:{web.port}"
    c.login()
    assert c.request("GET", "/")[0].status == 200


def test_public_url_is_an_origin_and_the_link_base(web):
    web.web = WebSettings(port=web.port, public_url="https://demo.ngrok-free.app")
    assert "demo.ngrok-free.app" in web.origins and web.base_url == "https://demo.ngrok-free.app"
    c = Client(web)
    c.host = "demo.ngrok-free.app"
    c.login()
    assert c.request("GET", "/")[0].status == 200


def test_untrusted_text_is_escaped(web):
    c = Client(web).login()
    idea = submit(web, "<script>alert(1)</script>")
    for path in ("/", f"/idea/{idea.id}"):
        text = c.request("GET", path)[1]
        assert "<script>" not in text and "<b>skill</b>" not in text
    assert "&lt;script&gt;" in c.request("GET", f"/idea/{idea.id}")[1]


def test_projects_set_and_remove(web):
    c = Client(web).login()
    c.request("POST", "/project", {"csrf": c.csrf("/projects"), "op": "set", "name": "app", "summary": "Kotlin app"})
    assert web.bot.store.projects.get("app").summary == "Kotlin app"
    c.request("POST", "/project", {"csrf": c.csrf("/projects"), "op": "remove", "name": "app"})
    assert web.bot.store.projects.list() == []


def test_sign_out_ends_session(web):
    c = Client(web).login()
    cookie = c.cookie
    c.request("POST", "/logout", {"csrf": c.csrf()})
    c.cookie = cookie
    assert c.request("GET", "/")[0].status == 303


def test_own_sign_in_does_not_reset_guessing_at_others(web):
    from devexai.web.auth import MAX_ADDRESS_FAILURES

    c = Client(web)
    for i in range(MAX_ADDRESS_FAILURES):
        if i % 4 == 3:
            Client(web).login("bob@example.com")  # the guesser's own account
        c.request("POST", "/login", {"email": f"user{i}@example.com", "password": "guess-guess"})
    resp, _ = c.request("POST", "/login", {"email": "alice@example.com", "password": PASSWORD})
    assert resp.status == 429 and not c.cookie


def test_people_page_keeps_names_as_written(web):
    web.bot.store.people.add("U01ABC", "u01@example.com", "maintainer", ())
    alice = Client(web).login()
    alice.people(op="edit", name="U01ABC", email="u01@example.com", role="maintainer", topics="web")
    assert web.bot.store.people.get("U01ABC").topics == ("web",)
    alice.people(op="add", name="Dana", email="", role="maintainer", topics="")
    assert web.bot.store.people.get("Dana") is not None


def test_add_with_bad_password_adds_no_one(web):
    alice = Client(web).login()
    alice.people(op="add", name="dana", email="dana@example.com", role="maintainer", topics="", password="short")
    alice.people(op="add", name="erin", email="", role="maintainer", topics="", password=PASSWORD)
    assert web.bot.store.people.get("dana") is None and web.bot.store.people.get("erin") is None


def test_only_admins_delete_ideas(web):
    idea = submit(web)
    bob = Client(web).login("bob@example.com")
    assert "Delete idea" not in bob.request("GET", f"/idea/{idea.id}")[1]
    assert bob.request("POST", "/delete-idea", {"csrf": bob.csrf(), "idea": str(idea.id)})[0].status == 404
    c = Client(web).login()
    assert "Delete idea" in c.request("GET", f"/idea/{idea.id}")[1]
    resp, _ = c.request("POST", "/delete-idea", {"csrf": c.csrf(f"/idea/{idea.id}"), "idea": str(idea.id)})
    assert resp.status == 303 and resp.getheader("Location") == "/"
    assert web.bot.store.ideas.list() == [] and web.bot.store.audit.for_idea(idea.id) == []
    assert "Deleted" in c.request("GET", "/")[1]
