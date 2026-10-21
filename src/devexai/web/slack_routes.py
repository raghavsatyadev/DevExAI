"""The admin's Slack page: save tokens and channels, test the setup, connect or disconnect live."""

from __future__ import annotations

import os
import re
from dataclasses import replace
from typing import TYPE_CHECKING

from ..chat.slack import SlackChat
from ..chat.slack_check import check_slack
from ..config import save_env
from . import slack_pages

if TYPE_CHECKING:
    from ..store import Person
    from .auth import Session
    from .server import _Handler

_TOKEN = {"bot_token": ("SLACK_BOT_TOKEN", re.compile(r"xoxb-[A-Za-z0-9-]{10,300}")),
          "app_token": ("SLACK_APP_TOKEN", re.compile(r"xapp-[A-Za-z0-9-]{10,300}"))}
_CHANNEL = re.compile(r"#?([a-z0-9][a-z0-9_-]{0,79})")
_LICENCE = re.compile(r"[A-Za-z0-9._~+/=-]{8,512}")


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def slack_get(h: _Handler, sess: Session) -> str:
    bot = h.server.bot
    return slack_pages.slack_page(
        sess.csrf, connected=isinstance(bot.chat, SlackChat), platform=type(bot.chat).__name__.removesuffix("Chat"),
        bot_set=bool(_env("SLACK_BOT_TOKEN")), app_set=bool(_env("SLACK_APP_TOKEN")),
        licence_set=bool(_env("DEVEXAI_LICENCE_KEY")), ideas=bot.settings.ideas_channel,
        public=bot.settings.public_channel, checks=h.server.slack_checks)


def _switch(h: _Handler, adapter: str) -> None:
    from ..app import make_chat, switch_chat

    bot = h.server.bot
    with h.server.chat_lock:
        switch_chat(bot, make_chat(bot.settings, bot.store, adapter))
    bot.store.meta.set("cfg:chat_adapter", adapter)
    h.server.notices[:] = [n for n in h.server.notices if not n.startswith("Chat not connected")]


def _do(h: _Handler, me: Person, op: str, form: dict[str, str]) -> str:
    bot, server = h.server.bot, h.server
    if op == "tokens":
        updates = {}
        for field, (key, pattern) in _TOKEN.items():
            value = form.get(field, "").strip()
            if value and not pattern.fullmatch(value):
                return f"That does not look like a {key.split('_')[1].lower()} token ({pattern.pattern[:5]}...)."
            if value:
                updates[key] = value
        if not updates:
            return "Nothing to save: both token boxes were empty."
        save_env(server.env_path, updates)
        bot.store.audit.add(None, me.name, "slack:tokens", ", ".join(sorted(updates)))  # names only, never values
        tail = " Press Reconnect to use them." if isinstance(bot.chat, SlackChat) else " Now Test connection."
        return "Tokens saved." + tail
    if op == "channels":
        names = {}
        for field, setting in (("ideas", "ideas_channel"), ("public", "public_channel")):
            m = _CHANNEL.fullmatch(form.get(field, "").strip().lower())
            if not m:
                return "Channel names are lowercase letters, digits, - and _."
            names[setting] = f"#{m.group(1)}"
        for setting, name in names.items():
            bot.store.meta.set(f"cfg:{setting}", name)
        bot.settings = replace(bot.settings, **names)
        bot.store.audit.add(None, me.name, "slack:channels", " ".join(names.values()))
        return f"Channels saved: ideas in {names['ideas_channel']}, announcements in {names['public_channel']}."
    if op == "licence":
        value = form.get("licence", "").strip()
        if not _LICENCE.fullmatch(value):
            return "That does not look like a licence key."
        save_env(server.env_path, {"DEVEXAI_LICENCE_KEY": value})
        bot.store.audit.add(None, me.name, "licence", "set")
        return "Licence key saved."
    if op == "test":
        server.slack_checks = check_slack(_env("SLACK_BOT_TOKEN"), _env("SLACK_APP_TOKEN"), bot.settings.ideas_channel,
                                          bot.settings.public_channel, bot.store.people.list())
        bad = sum(not c.ok for c in server.slack_checks)
        return "Everything checks out." if not bad else f"{bad} thing(s) to fix, listed below."
    if op in ("connect", "disconnect"):
        try:
            _switch(h, "slack" if op == "connect" else "none")
        except Exception as e:  # Slack's error codes (invalid_auth...) carry no secrets
            return f"Could not connect to Slack: {e}. Try Test connection to see what is wrong."
        bot.store.audit.add(None, me.name, f"slack:{op}", "")
        return "Connected to Slack." if op == "connect" else "Disconnected. The bot now runs without a chat platform."
    return "Unknown change."


def slack_post(h: _Handler, sess: Session, me: Person, form: dict[str, str]) -> None:
    h.server.sessions.flash(sess, _do(h, me, form.get("op", ""), form))
    h._redirect("/slack")
