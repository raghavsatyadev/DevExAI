"""Who and where on Slack: Slack user IDs to DevExAI names, channel names to channel IDs.

The bot knows people by name. A Slack user is a maintainer only when their Slack email matches an
active person's email on the People page; everyone else gets a name of their own that never equals a
person's name, so a display name can never borrow a maintainer's rights. Both directions are kept in
the database, so mentions in old ideas still work after a restart.
"""

from __future__ import annotations

import logging
import re
import threading
import time

log = logging.getLogger(__name__)

_USER_TTL = 3600  # re-read a Slack profile (email, name) after an hour
_SLUG = re.compile(r"[^a-z0-9._-]+")
_MENTION = re.compile(r"<@([UW][A-Z0-9]+)>")


def unmention(text: str, meta) -> str:
    """'<@U0123>' back to '@name' for places outside Slack (dashboard history, command replies)."""
    return _MENTION.sub(lambda m: f"@{meta.get(f'slack:uid:{m.group(1)}') or m.group(1)}", text)


class SlackIds:
    def __init__(self, web, store):
        self.web = web
        self.store = store
        self._lock = threading.Lock()
        self._profiles: dict[str, tuple[float, str, str]] = {}  # uid -> (read at, email, display name)
        self._channels: dict[str, str] = {}  # "#name" -> channel ID
        self._names: dict[str, str] = {}     # channel ID -> "#name"

    # people
    def _profile(self, uid: str) -> tuple[str, str]:
        hit = self._profiles.get(uid)
        if hit and time.monotonic() - hit[0] < _USER_TTL:
            return hit[1], hit[2]
        user = self.web.users_info(user=uid)["user"]
        prof = user.get("profile") or {}
        email = (prof.get("email") or "").strip().lower()
        shown = prof.get("display_name") or prof.get("real_name") or user.get("name") or uid
        self._profiles[uid] = (time.monotonic(), email, shown)
        return email, shown

    def name_for(self, uid: str) -> str:
        """The DevExAI name for a Slack user."""
        email, shown = self._profile(uid)
        people = self.store.people.list()
        meta = self.store.meta
        with self._lock:
            match = next((p for p in people if email and (p.email or "").lower() == email), None)
            if match:
                name = match.name
            else:
                taken = {p.name.lower() for p in self.store.people.list(include_inactive=True)}
                name = meta.get(f"slack:uid:{uid}")
                if not name or name.lower() in taken:  # a person now has that name: pick another
                    base = _SLUG.sub("-", shown.lower()).strip("-") or "slack-user"
                    name = base if base not in taken and not meta.get(f"slack:name:{base}") else f"{base}-{uid.lower()}"
            meta.set(f"slack:uid:{uid}", name)
            meta.set(f"slack:name:{name}", uid)
        return name

    def uid_for(self, name: str) -> str | None:
        """The Slack user ID behind a DevExAI name, looked up by email for maintainers never seen yet."""
        if uid := self.store.meta.get(f"slack:name:{name}"):
            return uid
        person = self.store.people.get(name)
        if not person or not person.email:
            return None
        try:
            uid = self.web.users_lookupByEmail(email=person.email)["user"]["id"]
        except Exception:  # not in this workspace, or a different email on Slack
            return None
        self.store.meta.set(f"slack:name:{name}", uid)
        self.store.meta.set(f"slack:uid:{uid}", name)
        return uid

    # channels
    def _load_channels(self) -> None:
        cursor, found = None, {}
        while True:
            resp = self.web.conversations_list(types="public_channel", exclude_archived=True, limit=1000,
                                               cursor=cursor)
            for ch in resp.get("channels", ()):
                found[f"#{ch['name']}"] = ch["id"]
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
        with self._lock:
            self._channels = found
            self._names = {v: k for k, v in found.items()}

    def channel_id(self, channel: str) -> str:
        """'#ai-ideas' -> 'C0123'. IDs (DMs, channels we only know by ID) pass through."""
        if not channel.startswith("#"):
            return channel
        key = channel.lower()
        if key not in self._channels:
            self._load_channels()
        try:
            return self._channels[key]
        except KeyError:
            raise LookupError(f"Slack has no public channel {channel}") from None

    def channel_name(self, cid: str) -> str:
        """'C0123' -> '#ai-ideas', so commands can compare with the configured channel names."""
        if cid.startswith("D"):
            return cid
        if cid not in self._names:
            try:
                self._load_channels()
            except Exception:
                log.exception("slack: could not list channels")
        return self._names.get(cid, cid)
