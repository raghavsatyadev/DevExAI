"""The bot: ties chat, store, AI pipeline and maintainer routing together."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from datetime import UTC, datetime

from ..chat import Button, ChatAdapter, Event
from ..config import Settings
from ..llm import LLMProvider
from ..stages import LABELS, TERMINAL, Stage
from ..store import Idea, Store
from . import building, commands
from .pipeline import BUILD, GATE, PLAN, Job, Pipeline
from .routing import Router

log = logging.getLogger(__name__)


class Bot:
    def __init__(self, settings: Settings, store: Store, chat: ChatAdapter, llm: LLMProvider,
                 *, inline_jobs: bool = False):
        self.settings = settings
        self.store = store
        self.chat = chat
        self.llm = llm
        store.people.seed(settings.maintainers)
        self.router = Router(store.people.maintainers, store.meta, settings.maintainer_timeout_hours)
        self.pipeline = Pipeline(self, inline=inline_jobs)

    def current_settings(self) -> Settings:
        """Settings with today's maintainers (the dashboard can change them while the bot runs)."""
        return replace(self.settings, maintainers=self.router.maintainers)

    # incoming
    def handle(self, event: Event) -> None:
        try:
            commands.dispatch(self, event)
        except Exception:
            log.exception("failed to handle %r", event)
            self.reply(event, "Sorry, something went wrong handling that. The error is in the bot's log.")

    def reply(self, event: Event, text: str, buttons: tuple[Button, ...] = ()) -> None:
        self.chat.post(event.channel, text, thread=event.thread, buttons=buttons)

    # ideas
    def submit_idea(self, event: Event, text: str) -> Idea:
        if same := self.same_idea(text):  # a repost: no new idea, no AI spend
            self.reply(event, f"That is the same as idea #{same.id}, which is already {LABELS[same.stage]}. "
                              f"Follow or add to it in its thread in {self.settings.ideas_channel}.")
            return same
        idea = self.store.ideas.create(event.user, text, event.channel)
        self.store.audit.add(idea.id, event.user, "submitted", text[:500])
        ref = self.chat.post(
            self.settings.ideas_channel,
            # The idea text is not repeated here: it has not passed the safety gate yet.
            f"*Idea #{idea.id}* from {self.chat.mention(event.user)} received. Your tracking number "
            f"is #{idea.id}. Every update goes in this thread.",
        )
        idea = self.store.ideas.update(idea.id, thread_ref=ref)
        if event.is_dm:
            self.reply(event, f"Got it: idea #{idea.id}. Updates go in its thread in {self.settings.ideas_channel}.")
        self.pipeline.submit(Job(GATE, idea.id))
        return idea

    def same_idea(self, text: str) -> Idea | None:
        """An open or published idea with the same words (case, spacing and punctuation aside)."""
        if not (key := _words(text)):
            return None
        return next((i for i in self.store.ideas.list(1000)
                     if (i.stage not in TERMINAL or i.stage is Stage.PUBLISHED) and _words(i.text) == key), None)

    def say(self, idea: Idea, text: str, buttons: tuple[Button, ...] = ()) -> None:
        self.chat.post(self.settings.ideas_channel, text, thread=idea.thread_ref, buttons=buttons)

    def move(self, idea: Idea, dst: Stage, text: str = "", *, actor: str = "bot",
             buttons: tuple[Button, ...] = ()) -> Idea:
        """Change stage (only if nobody else moved it first) and tell poster and maintainer."""
        idea = self.store.ideas.move(idea.id, dst, expect=idea.stage)
        self.announce(idea, text, actor=actor, buttons=buttons)
        return idea

    def announce(self, idea: Idea, text: str = "", *, actor: str = "bot", buttons: tuple[Button, ...] = ()) -> None:
        """Record the stage the idea has just moved to and tell poster and maintainer."""
        dst = idea.stage
        self.store.audit.add(idea.id, actor, f"stage:{dst.value}", text[:500])
        people = " ".join(self.chat.mention(u) for u in dict.fromkeys(filter(None, (idea.poster, idea.maintainer))))
        head = f"*{idea.label}* is now: *{LABELS[dst]}*  {people}".rstrip()
        if buttons and self.tell_maintainer(idea, text, buttons):  # decisions go to the maintainer privately
            text = f"{text}\nThe maintainer has been asked in a direct message.".lstrip()
            buttons = ()
        self.say(idea, f"{head}\n{text}".rstrip(), buttons)

    def tell_maintainer(self, idea: Idea, text: str, buttons: tuple[Button, ...] = ()) -> bool:
        """Direct message to the idea's maintainer, where the platform has them. False: say it in the thread."""
        dm = getattr(self.chat, "dm", None)
        if dm is None or not idea.maintainer:
            return False
        try:
            return dm(idea.maintainer, f"*{idea.label}* ({LABELS[idea.stage]}) needs you:\n{text}", buttons)
        except Exception:
            log.exception("could not message %s directly", idea.maintainer)
            return False

    def assign(self, idea: Idea, topic: str | None) -> Idea:
        if idea.maintainer:
            return idea
        name = self.router.pick(topic)
        self.store.audit.add(idea.id, "bot", "assigned", name)
        return self.store.ideas.update(idea.id, maintainer=name)

    def hand_over(self, name: str, actor: str) -> int:
        """Give a departing maintainer's open ideas to others. Returns how many moved."""
        moved = 0
        for idea in self.store.ideas.list(100_000):
            if idea.maintainer != name or idea.stage in TERMINAL:
                continue
            new = self.router.pick(idea.topic, exclude=name)
            if new == name:
                continue  # nobody else left; the admin is told on the People page
            self.store.ideas.update(idea.id, maintainer=new)
            if idea.waiting_since:  # the new maintainer gets a full timeout, as with /devex-assign
                self.store.ideas.reset_wait(idea.id)
            self.store.audit.add(idea.id, actor, "reassigned", f"{name} -> {new}")
            self.say(idea, f"{self.chat.mention(new)} now looks after {idea.label} ({LABELS[idea.stage]}).")
            self.tell_maintainer(self.store.ideas.get(idea.id), f"You now look after this, handed over from {name}. "
                                 f"Use `/devex-status {idea.id}` to see where it is.")
            moved += 1
        return moved

    def delete_idea(self, idea: Idea, actor: str) -> str:
        """Admin clean-up: drop the idea and the bot's posts about it. Others' chat messages stay."""
        if idea.stage in (Stage.RECEIVED, Stage.SAFETY_CHECK, Stage.RESEARCHING):
            raise ValueError(f"{idea.label} is in an AI step right now; stop it first, then delete.")
        if idea.stage is Stage.BUILDING and (idea.build or {}).get("pending"):
            raise ValueError(f"The bot is building {idea.label} right now; stop it first, then delete.")
        removed = ""
        clean = getattr(self.chat, "delete_thread", None)
        if clean and idea.thread_ref:
            try:
                removed = f" Removed {clean(idea.thread_ref)} bot message(s) from chat."
            except Exception as e:  # the record goes anyway; chat can be tidied by hand
                log.exception("could not delete the chat thread of %s", idea.label)
                removed = f" Chat messages were not removed ({e})."
        self.store.ideas.delete(idea.id)
        building.forget(self, idea)
        self.store.audit.add(None, actor, "idea:deleted", f"#{idea.id} {idea.title or idea.text[:80]}")
        return f"Deleted {idea.label}.{removed}"

    def fail(self, idea_id: int, reason: str) -> None:
        idea = self.store.ideas.get(idea_id)
        if idea.stage in TERMINAL:
            return
        idea = self.store.ideas.update(idea_id, stop_reason=reason)
        self.move(idea, Stage.STOPPED, f"Stopped: {reason}. A maintainer can ask the poster to resubmit.")

    # background duties
    def tick(self, now: datetime | None = None) -> None:
        """Reassign ideas whose maintainer has been silent past the timeout."""
        now = now or datetime.now(UTC)
        for idea in self.store.ideas.waiting_on_maintainer():
            if not self.router.overdue(idea.waiting_since, now):
                continue
            old = idea.maintainer
            new = self.router.pick(idea.topic, exclude=old)
            self.store.ideas.reset_wait(idea.id)
            hours = f"{self.settings.maintainer_timeout_hours:g}h"
            if new == old:
                if not self.tell_maintainer(idea, f"Reminder: this has waited {hours} for you."):
                    self.say(idea, f"Reminder {self.chat.mention(old)}: {idea.label} has waited {hours} for you "
                                   f"({LABELS[idea.stage]}).")
                continue
            self.store.ideas.update(idea.id, maintainer=new)
            self.store.audit.add(idea.id, "bot", "reassigned", f"{old} -> {new}")
            self.say(idea, f"{self.chat.mention(old or 'nobody')} has not answered in {hours}, so "
                           f"{self.chat.mention(new)} now looks after {idea.label} ({LABELS[idea.stage]}).")
            self.tell_maintainer(self.store.ideas.get(idea.id), f"You now look after this; {old or 'nobody'} "
                                 f"did not answer in {hours}. Use `/devex-status {idea.id}` to see where it is.")

    def resume(self) -> None:
        """After a restart, re-queue ideas that were mid-way through an AI step."""
        for idea in reversed(self.store.ideas.list(1000)):
            if idea.stage in (Stage.RECEIVED, Stage.SAFETY_CHECK):
                self.pipeline.submit(Job(GATE, idea.id))
            elif idea.stage is Stage.RESEARCHING:
                self.pipeline.submit(Job(PLAN, idea.id))
            elif idea.stage is Stage.BUILDING and (idea.build or {}).get("pending") and building.by_bot(self):
                self.pipeline.submit(Job(BUILD, idea.id))


def _words(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))
