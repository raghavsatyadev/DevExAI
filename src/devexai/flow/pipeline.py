"""The AI steps (safety gate, planning, building) run here, one job at a time, off the chat thread."""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from ..chat import Button
from ..gate import safety
from ..llm import LLMError
from ..plan import planner
from ..stages import LABELS, InvalidTransition, Stage
from . import building

if TYPE_CHECKING:
    from .bot import Bot

log = logging.getLogger(__name__)

GATE, PLAN, BUILD = "gate", "plan", "build"
MAINTAINER, POSTER = "maintainer", "poster"
_PAST_GATE = frozenset({Stage.RESEARCHING, Stage.PLAN_READY, Stage.WAITING_APPROVAL, Stage.BUILDING,
                        Stage.UNDER_REVIEW, Stage.PUBLISHED})


@dataclass(frozen=True)
class Job:
    kind: str
    idea_id: int
    note: str = ""  # a suggested change for a re-plan
    by: str = MAINTAINER  # who suggested it; a poster's suggestion passes the safety gate first


class Pipeline:
    def __init__(self, bot: Bot, inline: bool = False):
        self.bot = bot
        self.inline = inline  # tests run jobs immediately on the calling thread
        self.jobs: queue.Queue[Job | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def submit(self, job: Job) -> None:
        if self.inline:
            self.run(job)
        else:
            self.jobs.put(job)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="devexai-pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.jobs.put(None)

    def _loop(self) -> None:
        while (job := self.jobs.get()) is not None:
            try:
                self.run(job)
            except Exception:  # last line of defence: keep the worker alive
                log.exception("worker survived an error in job %s", job)

    def run(self, job: Job) -> None:
        try:
            {GATE: self._gate, PLAN: self._plan, BUILD: self._build}[job.kind](job)
        except InvalidTransition as e:  # someone stopped or moved the idea meanwhile
            log.info("job %s skipped: %s", job, e)
        except Exception:  # one bad job must not kill the worker
            log.exception("job %s failed", job)
            try:
                self.bot.fail(job.idea_id, f"internal error during {job.kind}")
            except Exception:
                log.exception("could not report failure of job %s", job)

    # Step 1
    def _gate(self, job: Job) -> None:
        bot = self.bot
        idea = bot.store.ideas.get(job.idea_id)
        if idea.stage is Stage.RECEIVED:  # already SAFETY_CHECK when resuming after a restart
            idea = bot.move(idea, Stage.SAFETY_CHECK, "Safety check started.")
        if idea.stage is not Stage.SAFETY_CHECK:
            return  # stopped meanwhile
        try:
            result = safety.check_idea(bot.llm, bot.current_settings(), idea.text, _earlier(bot, idea))
        except LLMError as e:
            idea = bot.assign(idea, None)
            idea = bot.store.ideas.update(idea.id, gate={"verdict": "error", "error": str(e)})
            bot.store.audit.add(idea.id, "bot", "gate_error", str(e))
            bot.move(idea, Stage.SAFETY_UNSURE, "The automatic safety check could not run, so a maintainer must decide.",
                     buttons=_decide_buttons(idea.id))
            return
        idea = bot.store.ideas.update(idea.id, gate=result.record(), topic=result.topic, title=result.title)
        idea = bot.assign(idea, result.topic)
        bot.store.audit.add(idea.id, "bot", f"gate_{result.verdict}", "; ".join(result.reasons))
        reasons = "".join(f"\n  - {r}" for r in result.reasons)
        if result.verdict == safety.PASS and result.duplicate_of:
            same = bot.store.ideas.get(result.duplicate_of)
            bot.move(idea, Stage.POSSIBLE_DUPLICATE, f"This looks like the same tool as {same.label} "
                     f"({LABELS[same.stage]}), so it is on hold. {bot.chat.mention(idea.poster)}, to add to it, "
                     "reply in that idea's thread. Maintainer: if it is a different tool, let it go ahead.",
                     buttons=(Button("Not a duplicate", f"/devex-approve {idea.id}"),
                              Button("Same idea, close it", f"/devex-deny {idea.id} duplicate of #{same.id}")))
        elif result.verdict == safety.PASS:
            idea = bot.move(idea, Stage.RESEARCHING, "Safety check passed. Researching and planning now.")
            ask_live(bot, idea)
            bot.pipeline.submit(Job(PLAN, idea.id))
        elif result.verdict == safety.UNSURE:
            bot.move(idea, Stage.SAFETY_UNSURE, f"The safety check is unsure, so a maintainer will decide.{reasons}",
                     buttons=_decide_buttons(idea.id))
        else:
            bot.move(idea, Stage.REJECTED, "Sorry, this idea can't go ahead because it did not pass "
                     f"the safety check.{reasons}\nIf you think this is a mistake, reply here and the maintainer will look.")

    # Steps 2-4
    def _plan(self, job: Job) -> None:
        bot = self.bot
        idea = bot.store.ideas.get(job.idea_id)
        if idea.stage is not Stage.RESEARCHING:
            return  # stopped meanwhile
        if job.by == POSTER and not self._poster_note_safe(idea, job.note):
            if idea.plan is not None:
                return  # the old plan stands
            job = replace(job, note="")  # nothing to fall back to: plan without the suggestion
        text = idea.text + (f"\n\n{job.by.capitalize()}'s suggestion: {job.note}" if job.note else "")
        # Only text the safety gate has checked reaches the planner: the gated page snapshots (never
        # a re-fetch) and other ideas that already got past the gate.
        pages = safety.checked_pages(idea.gate)
        recent = [o for o in bot.store.ideas.list(100)
                  if o.id != idea.id and (o.stage in _PAST_GATE or o.plan is not None)]
        try:
            plan = planner.make_plan(bot.llm, bot.settings, replace(idea, text=text), pages,
                                     bot.store.projects.list(), recent)
        except LLMError as e:
            bot.store.audit.add(idea.id, "bot", "plan_error", str(e))
            bot.fail(idea.id, f"planning failed: {e}")
            return
        idea = bot.store.ideas.update(idea.id, plan=plan)
        if bot.store.ideas.get(idea.id).stage is not Stage.RESEARCHING:
            return
        bot.store.audit.add(idea.id, "bot", "plan_ready", plan["summary"][:200])
        idea = bot.move(idea, Stage.PLAN_READY, planner.format_plan(plan) + "\n\n" + _PLAN_READY,
                        buttons=_plan_buttons(idea.id))
        ask_poster(bot, idea)

    # Step 5
    def _build(self, job: Job) -> None:
        building.run(self.bot, job.idea_id)

    def _poster_note_safe(self, idea, note: str) -> bool:
        """A poster's suggestion is new untrusted text, so it passes the safety gate like the idea did."""
        bot = self.bot
        try:
            verdict = safety.check_idea(bot.llm, bot.current_settings(), note).verdict
        except LLMError as e:
            verdict = f"error: {e}"
        bot.store.audit.add(idea.id, "bot", "suggestion_gate", verdict)
        if verdict == safety.PASS:
            return True
        if idea.plan is None:
            return False
        bot.move(idea, Stage.PLAN_READY, f"{bot.chat.mention(idea.poster)}, your suggestion did not pass the "
                 "safety check, so the plan is unchanged. A maintainer can look at it.\n" + _PLAN_READY,
                 buttons=_plan_buttons(idea.id))
        return False


def _earlier(bot: Bot, idea) -> list:
    """Older ideas the gate compares against: only text that passed the gate, nothing stopped or rejected."""
    seen = _PAST_GATE | {Stage.POSSIBLE_DUPLICATE}
    return [o for o in bot.store.ideas.list(100) if o.id < idea.id and o.stage in seen]


_PLAN_READY = "Maintainer: approve the plan, suggest a change, or stop it."


def _plan_buttons(idea_id: int) -> tuple[Button, ...]:
    return (Button("Approve plan", f"/devex-approve {idea_id}"),
            Button("Suggest change", f"/devex-suggest {idea_id} <what to change>"),
            Button("Stop", f"/devex-stop {idea_id} <reason>"))


def ask_live(bot: Bot, idea) -> None:
    """Ask once, right after the safety gate. Planning never waits for the answer; no answer means no."""
    bot.say(idea, f"{bot.chat.mention(idea.poster)}, do you want this tool built live, in public? You would "
            "answer the bot's questions here and can steer it with your own suggestions; everyone in this "
            "channel can follow along. If you don't answer, the maintainer handles it quietly.", buttons=(
                Button("Yes, build it live", f"/devex-live {idea.id} yes"),
                Button("No thanks", f"/devex-live {idea.id} no"),
            ))


def ask_poster(bot: Bot, idea) -> None:
    """In a live build, the plan's open questions go to the poster."""
    questions = (idea.plan or {}).get("questions") or []
    if idea.live != "yes" or not questions or idea.stage not in (Stage.PLAN_READY, Stage.WAITING_APPROVAL):
        return
    listing = "\n".join(f"  - {q}" for q in questions)
    bot.say(idea, f"{bot.chat.mention(idea.poster)}, the bot has questions for you:\n{listing}\n"
            f"Answer or steer it with `/devex-suggest {idea.id} <your answer>`.")


def _decide_buttons(idea_id: int) -> tuple[Button, ...]:
    return (Button("Allow", f"/devex-approve {idea_id}"), Button("Reject", f"/devex-deny {idea_id} <reason>"))

