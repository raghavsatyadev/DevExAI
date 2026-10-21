from devexai.chat.base import Button
from devexai.chat.slack import SlackChat, blocks_for, plain_text, slack_text
from devexai.chat.slack_ids import unmention
from devexai.config import Maintainer, save_env
from devexai.store import Store


class FakeWeb:
    """Just enough of slack_sdk's WebClient."""

    def __init__(self):
        self.users = {"U1": ("alice@example.com", "Alice A"), "U2": ("eve@other.com", "alice"),
                      "U3": ("zed@other.com", "Zed")}
        self.posts = []
        self.deleted = []

    def users_info(self, user):
        email, name = self.users[user]
        return {"user": {"profile": {"email": email, "display_name": name}}}

    def users_lookupByEmail(self, email):
        for uid, (mail, _) in self.users.items():
            if mail == email:
                return {"user": {"id": uid}}
        raise LookupError(email)

    def conversations_list(self, **kw):
        return {"channels": [{"name": "ai-ideas", "id": "C1"}, {"name": "ai-tools", "id": "C2"}]}

    def conversations_replies(self, channel, ts, limit):
        return {"messages": [{"ts": ts, "user": "UBOT"}, {"ts": "2.0", "user": "U1"}, {"ts": "3.0", "user": "UBOT"}]}

    def chat_delete(self, channel, ts):
        self.deleted.append((channel, ts))

    def conversations_open(self, users):
        return {"channel": {"id": f"D{users}"}}

    def chat_postMessage(self, **kw):
        self.posts.append(kw)
        return {"ts": "111.222"}


def make(tmp_path=None):
    store = Store(":memory:")
    store.people.seed((Maintainer("alice", (), "alice@example.com", admin=True),))
    chat = SlackChat("xoxb-x", "xapp-x", store, web=FakeWeb())
    chat.bot_user = "UBOT"
    return chat, store


def test_text_escaping_keeps_mentions_and_blocks_pings():
    assert slack_text("<@U1> <!channel> a&b") == "<@U1> &lt;!channel&gt; a&amp;b"
    assert plain_text("<@UBOT> see <https://x.io/a|x.io> in <#C1|ai-ideas> &amp; go", "UBOT") == \
        "see https://x.io/a in #ai-ideas & go"


def test_blocks_only_with_buttons_and_deny_is_red():
    assert blocks_for("hi", ()) is None
    blocks = blocks_for("x" * 6000, (Button("Approve", "/devex-approve 1"), Button("Deny", "/devex-deny 1")))
    assert [b["type"] for b in blocks] == ["section", "section", "section", "actions"]
    approve, deny = blocks[-1]["elements"]
    assert approve["value"] == "/devex-approve 1" and "style" not in approve and deny["style"] == "danger"
    words = " ".join(["word"] * 1500)  # 7499 chars: sections must break between words
    parts = [b["text"]["text"] for b in blocks_for(words, (Button("Ok", "/devex-status 1"),))[:-1]]
    assert all(len(p) <= 2900 for p in parts) and " ".join(parts) == words


def test_names_follow_people_emails_and_never_borrow_a_maintainer_name():
    chat, store = make()
    assert chat.ids.name_for("U1") == "alice"            # email matches the People page
    impostor = chat.ids.name_for("U2")                    # Slack display name "alice", other email
    assert impostor != "alice" and impostor.startswith("alice-")
    assert chat.ids.name_for("U3") == "zed"
    assert chat.mention("alice") == "<@U1>" and chat.mention("nobody") == "@nobody"
    assert unmention("approved by <@U1> and <@U9>", store.meta) == "approved by @alice and @U9"


def test_post_threads_and_top_level():
    chat, _ = make()
    ref = chat.post("#ai-ideas", "new idea")
    assert ref == "C1:111.222" and chat.web.posts[-1]["channel"] == "C1"
    assert chat.post("#ai-ideas", "update", thread=ref) == ref
    assert chat.web.posts[-1]["thread_ts"] == "111.222"


def test_events_messages_slash_commands_and_buttons():
    chat, _ = make()
    msg = {"event_id": "E1", "event": {"type": "message", "user": "U1", "channel": "C1", "ts": "5.0",
                                       "text": "<@UBOT> my idea"}}
    ev = chat.to_event("events_api", msg)
    assert (ev.user, ev.text, ev.channel, ev.thread, ev.is_dm) == ("alice", "my idea", "#ai-ideas", None, False)
    assert chat.to_event("events_api", msg) is None  # Slack retried: handled once
    reply = {"event_id": "E2", "event": {"type": "message", "user": "U3", "channel": "C1", "ts": "6.0",
                                         "thread_ts": "5.0", "text": "+1"}}
    assert chat.to_event("events_api", reply).thread == "C1:5.0"
    for skip in ({"bot_id": "B1"}, {"subtype": "message_changed"}, {"user": "UBOT"}):
        ev = {"type": "message", "user": "U1", "channel": "C1", "ts": "7.0", "text": "x", **skip}
        assert chat.to_event("events_api", {"event_id": f"E{skip}", "event": ev}) is None
    dm = chat.to_event("events_api", {"event_id": "E3", "event": {"type": "message", "user": "U1", "channel": "D9",
                                                                  "channel_type": "im", "ts": "8.0", "text": "hi"}})
    assert dm.is_dm and dm.channel == "D9"
    cmd = chat.to_event("slash_commands", {"command": "/devex-status", "text": "1", "user_id": "U1",
                                           "channel_id": "C1", "response_url": "https://hooks.slack.com/x"})
    assert cmd.text == "/devex-status 1" and cmd.thread.startswith("resp:")
    click = chat.to_event("interactive", {"type": "block_actions", "user": {"id": "U1"}, "channel": {"id": "C1"},
                                          "message": {"ts": "9.0", "thread_ts": "5.0"},
                                          "actions": [{"value": "/devex-approve 1"}]})
    assert (click.user, click.text, click.thread) == ("alice", "/devex-approve 1", "C1:5.0")


def test_save_env_replaces_in_place_and_refuses_odd_values(tmp_path, monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "")
    monkeypatch.setenv("NEW_KEY", "")
    env = tmp_path / ".env"
    env.write_text("# comment\nSLACK_BOT_TOKEN=\nOTHER=1\n", encoding="utf-8")
    save_env(env, {"SLACK_BOT_TOKEN": "xoxb-abc", "NEW_KEY": "v"})
    assert env.read_text(encoding="utf-8") == "# comment\nSLACK_BOT_TOKEN=xoxb-abc\nOTHER=1\nNEW_KEY=v\n"
    import os

    assert os.environ["SLACK_BOT_TOKEN"] == "xoxb-abc"
    for bad in ("a\nEVIL=1", "with space ", "x#y"):
        try:
            save_env(env, {"NEW_KEY": bad})
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad!r}")


def test_dm_opens_the_users_direct_chat():
    chat, _ = make()
    assert chat.dm("alice", "approve?", (Button("Approve", "/devex-approve 1"),))
    assert chat.web.posts[-1]["channel"] == "DU1" and chat.web.posts[-1]["blocks"]
    assert not chat.dm("nobody", "hi")


def test_button_that_needs_words_asks_for_them():
    chat, _ = make()
    seen = []
    chat._handler = seen.append
    chat._deliver("interactive", {"type": "block_actions", "user": {"id": "U1"}, "channel": {"id": "D5"},
                                  "message": {"ts": "9.0"}, "actions": [{"value": "/devex-deny 1 <reason>"}]})
    assert not seen and "/devex-deny 1 <reason>" in chat.web.posts[-1]["text"].replace("&lt;", "<").replace("&gt;", ">")


def test_delete_thread_removes_only_the_bots_posts_parent_last():
    chat, _ = make()
    assert chat.delete_thread("C1:1.0") == 2
    assert chat.web.deleted == [("C1", "3.0"), ("C1", "1.0")]
    assert chat.delete_thread("t3") == 0
