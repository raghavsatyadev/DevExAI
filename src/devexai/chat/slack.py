"""Slack chat adapter over Socket Mode: the bot connects out to Slack, so the server needs no public URL.

Thread refs are "<channel ID>:<thread ts>", built the same way for posts and for incoming replies, so
an idea's thread is found again whichever side spoke. Slash-command replies go back privately to the
person who typed the command (through the command's response URL). Every envelope is acknowledged
before it is handled, so a slow command never makes Slack deliver it twice.
"""

from __future__ import annotations

import html
import itertools
import logging
import re
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from .base import Button, Event, Handler
from .slack_ids import SlackIds

log = logging.getLogger(__name__)

_MENTION = re.compile(r"(<@[UW][A-Z0-9]+>)")
_BLANK = re.compile(r"<[a-z ]+>")  # "<reason>" in a button's command
_LINK = re.compile(r"<((?:https?|mailto):[^|>]+)(?:\|[^>]*)?>")
_CHANNEL = re.compile(r"<#[CG][A-Z0-9]+\|([^>]*)>")
_REF = re.compile(r"([CDG][A-Z0-9]+):(\d+\.\d+)")
_SECTION = 2900  # Block Kit section text limit is 3000
_KEEP_SUBTYPES = {None, "file_share", "thread_broadcast"}


def slack_text(text: str) -> str:
    """Escape &, < and > (so AI or idea text cannot ping @channel or forge links); keep our user mentions."""
    return "".join(p if _MENTION.fullmatch(p) else p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                   for p in _MENTION.split(text))


def plain_text(text: str, bot_user: str | None = None) -> str:
    """Slack's message markup back to what the person typed: bare links, #channel names, no @bot."""
    if bot_user:
        text = text.replace(f"<@{bot_user}>", "")
    text = _CHANNEL.sub(lambda m: f"#{m.group(1)}", _LINK.sub(lambda m: m.group(1), text))
    return html.unescape(text).strip()


def blocks_for(text: str, buttons: tuple[Button, ...]) -> list[dict] | None:
    if not buttons:
        return None
    sections = [{"type": "section", "text": {"type": "mrkdwn", "text": text[i:i + _SECTION]}}
                for i in range(0, len(text), _SECTION)][:45] or []
    actions = [{"type": "button", "action_id": f"devex-{n}", "value": b.command[:2000],
                "text": {"type": "plain_text", "text": b.label[:75]},
                **({"style": "danger"} if b.label.lower().startswith(("deny", "reject", "stop")) else {})}
               for n, b in enumerate(buttons[:25])]
    return [*sections, {"type": "actions", "elements": actions}]


class SlackChat:
    def __init__(self, bot_token: str, app_token: str, store, *, web=None):
        if web is None:
            from slack_sdk import WebClient

            web = WebClient(token=bot_token)
        self.web = web
        self.app_token = app_token
        self.ids = SlackIds(web, store)
        self.bot_user: str | None = None
        self._handler: Handler | None = None
        self._socket = None
        self._stop = threading.Event()
        self._work = ThreadPoolExecutor(max_workers=1, thread_name_prefix="devexai-slack")  # keeps order
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._replies: OrderedDict[str, str] = OrderedDict()  # "resp:N" -> slash command response URL
        self._reply_ids = itertools.count(1)

    # outgoing
    def post(self, channel, text, *, thread=None, buttons: tuple[Button, ...] = ()):
        body = slack_text(text)
        blocks = blocks_for(body, tuple(buttons))
        if thread and thread.startswith("resp:"):
            return self._respond(thread, body, blocks)
        m = _REF.fullmatch(thread or "")
        cid = m.group(1) if m else self.ids.channel_id(channel)  # old console refs ("t3") post at top level
        resp = self.web.chat_postMessage(channel=cid, text=body, blocks=blocks, thread_ts=m.group(2) if m else None,
                                         unfurl_links=False, unfurl_media=False)
        return thread if m else thread or f"{cid}:{resp['ts']}"

    def dm(self, user: str, text: str, buttons: tuple[Button, ...] = ()) -> bool:
        """Post in the user's direct chat with the bot. False when Slack does not know them."""
        uid = self.ids.uid_for(user)
        if not uid:
            return False
        cid = self.web.conversations_open(users=uid)["channel"]["id"]
        self.post(cid, text, buttons=buttons)
        return True

    def delete_thread(self, ref: str) -> int:
        """Delete the bot's own posts in a thread (Slack lets a bot delete only its own). Returns how many."""
        m = _REF.fullmatch(ref or "")
        if not m:
            return 0
        cid, ts = m.groups()
        me = self.bot_user or self.web.auth_test()["user_id"]
        msgs = self.web.conversations_replies(channel=cid, ts=ts, limit=1000).get("messages", [])
        mine = [x["ts"] for x in msgs if x.get("user") == me]
        for t in sorted(mine, key=lambda t: t == ts):  # replies first: the parent last
            self.web.chat_delete(channel=cid, ts=t)
        return len(mine)

    def _respond(self, ref: str, text: str, blocks) -> str:
        url = self._replies.get(ref)
        if not url:
            log.warning("slack: reply for an expired command dropped")
            return ref
        from slack_sdk.webhook import WebhookClient

        WebhookClient(url).send(text=text, blocks=blocks, response_type="ephemeral")
        return ref

    def mention(self, user: str) -> str:
        uid = self.ids.uid_for(user)
        return f"<@{uid}>" if uid else f"@{user}"

    # incoming
    def start(self, handler: Handler) -> None:
        """Check the bot token and connect. Raises if Slack refuses either token."""
        from slack_sdk.socket_mode import SocketModeClient

        self._handler = handler
        self.bot_user = self.web.auth_test()["user_id"]
        self._socket = SocketModeClient(app_token=self.app_token, web_client=self.web, concurrency=1)
        self._socket.socket_mode_request_listeners.append(self._on_request)
        self._socket.connect()
        log.info("slack: connected as %s", self.bot_user)

    def run(self, handler: Handler) -> None:
        if self._socket is None:
            self.start(handler)
        try:
            while not self._stop.wait(1):  # short waits so Ctrl+C is seen on Windows
                pass
        except KeyboardInterrupt:
            pass

    def stop(self) -> None:
        self._stop.set()
        if self._socket is not None:
            self._socket.close()
        self._work.shutdown(wait=False)

    def _on_request(self, client, req) -> None:
        from slack_sdk.socket_mode.response import SocketModeResponse

        client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
        self._work.submit(self._deliver, req.type, req.payload)

    def _deliver(self, kind: str, payload: dict) -> None:
        try:
            event = self.to_event(kind, payload)
            if event and _BLANK.search(event.text):  # a button that needs words from the user
                self.post(event.channel, f"Type it with your words: `{event.text}`", thread=event.thread)
            elif event and self._handler:
                self._handler(event)
        except Exception:
            log.exception("slack: could not handle a %s envelope", kind)

    def _once(self, key: str | None) -> bool:
        if not key:
            return True
        if key in self._seen:
            return False
        self._seen[key] = None
        while len(self._seen) > 500:
            self._seen.popitem(last=False)
        return True

    def to_event(self, kind: str, p: dict) -> Event | None:
        if kind == "events_api":
            return self._message(p) if self._once(p.get("event_id")) else None
        if kind == "slash_commands":
            ref = f"resp:{next(self._reply_ids)}"
            self._replies[ref] = p["response_url"]
            while len(self._replies) > 200:
                self._replies.popitem(last=False)
            cid = p["channel_id"]
            text = f"{p['command']} {plain_text(p.get('text', ''), self.bot_user)}".strip()
            return Event(self.ids.name_for(p["user_id"]), text, self.ids.channel_name(cid), thread=ref,
                         is_dm=cid.startswith("D"))
        if kind == "interactive" and p.get("type") == "block_actions" and p.get("actions"):
            cid, msg = p["channel"]["id"], p.get("message") or {}
            ts = msg.get("thread_ts") or msg.get("ts")
            return Event(self.ids.name_for(p["user"]["id"]), p["actions"][0].get("value", ""),
                         self.ids.channel_name(cid), thread=f"{cid}:{ts}" if ts else None)
        return None

    def _message(self, p: dict) -> Event | None:
        ev = p.get("event") or {}
        # app_mention is ignored: the same post also arrives as a message, and handling both doubles ideas
        if ev.get("type") != "message" or ev.get("bot_id") or ev.get("subtype") not in _KEEP_SUBTYPES:
            return None
        uid = ev.get("user")
        if not uid or uid == self.bot_user:
            return None
        cid, ts, parent = ev["channel"], ev.get("ts"), ev.get("thread_ts")
        is_dm = ev.get("channel_type") == "im" or cid.startswith("D")
        return Event(self.ids.name_for(uid), plain_text(ev.get("text", ""), self.bot_user),
                     cid if is_dm else self.ids.channel_name(cid),
                     thread=f"{cid}:{parent}" if parent and parent != ts else None, is_dm=is_dm)
