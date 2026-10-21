"""Step 5 in the flow: hand an approved idea to the bot builder (or a person) and report what it made."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..builder import build as builder
from ..builder import files as tool_files
from ..chat import Button
from ..gate import safety
from ..llm import LLMError
from ..plan.planner import FREE
from ..stages import Stage
from ..store import Idea

if TYPE_CHECKING:
    from .bot import Bot

log = logging.getLogger(__name__)

NOT_RUN = ("The tests were written but not run yet: running AI-written code needs a sandbox, "
           "which is not built.")


def by_bot(bot: Bot) -> bool:
    return bot.settings.build_by == "bot"


def start(bot: Bot, idea: Idea, why: str, actor: str) -> bool:
    """Move to Building. True if the bot should now be given a build job."""
    free = [r["name"] for r in (idea.plan or {}).get("resources", []) if r.get("lane") == FREE]
    used = f" Free resources, used automatically: {', '.join(free)}." if free else ""
    if not by_bot(bot):
        bot.move(idea, Stage.BUILDING, f"{why}{used}\nA person builds the tool now, with tests and a short "
                 f"README. When it is ready: `/devex-built {idea.id}`.", actor=actor)
        return False
    idea = bot.store.ideas.update(idea.id, build={**(idea.build or {}), "pending": True, "request": ""})
    bot.move(idea, Stage.BUILDING, f"{why}{used}\nThe bot is writing the tool now, with tests and a README. "
             "A second AI reviews it, then the maintainer gets it to check.", actor=actor)
    return True


def send_back(bot: Bot, idea: Idea, changes: str, actor: str) -> bool:
    """Under review -> Building with the maintainer's changes. True if the bot should rebuild it."""
    who = bot.chat.mention(actor)
    if not by_bot(bot):
        bot.move(idea, Stage.BUILDING, f"{who} asked for changes: {changes}\nWhen fixed: "
                 f"`/devex-built {idea.id}`.", actor=actor)
        return False
    idea = bot.store.ideas.update(idea.id, build={**(idea.build or {}), "pending": True, "request": changes})
    bot.move(idea, Stage.BUILDING, f"{who} asked for changes: {changes}\nThe bot is changing it now.", actor=actor)
    return True


def run(bot: Bot, idea_id: int) -> None:
    """The build job: write, review, save, then hand the result to the maintainer."""
    idea = bot.store.ideas.get(idea_id)
    if idea.stage is not Stage.BUILDING:
        return  # stopped meanwhile
    old = idea.build or {}
    request = old.get("request", "")
    try:
        record = builder.build(bot.llm, idea, safety.checked_pages(idea.gate), request,
                               builder.file_map(old) or None)
        tool_files.save(bot.settings.builds_dir / str(idea.id), builder.file_map(record))
    except (LLMError, tool_files.BadFiles) as e:
        bot.store.ideas.update(idea.id, build={**old, "pending": False, "error": str(e)})
        bot.store.audit.add(idea.id, "bot", "build_error", str(e)[:500])
        _tell(bot, idea, f"The bot could not build it: {e}\nA person can build it and send it on with "
                         f"`/devex-built {idea.id}`, or stop it.")
        return
    idea = bot.store.ideas.update(idea.id, build=record)
    rev = record["review"]
    bot.store.audit.add(idea.id, "bot", "built", f"{len(record['files'])} files, review {rev['verdict']}, "
                        f"safe {rev['safe']}, rounds {record['rounds']}")
    if idea.stage is not Stage.BUILDING:
        return
    if not rev["safe"]:  # never offered for release; a person looks first
        issues = "".join(f"\n  - {s}" for s in rev["safety_issues"]) or "\n  - (no details given)"
        _tell(bot, idea, f"The bot built it, but the reviewing AI found safety problems:{issues}\n"
                         f"Nothing is offered for release. Read the files on the dashboard; if they are fine, "
                         f"`/devex-built {idea.id}` sends it to review. Otherwise stop it.")
        return
    bot.move(idea, Stage.UNDER_REVIEW, report(bot, idea, record), buttons=(
        Button("Publish", f"/devex-publish {idea.id}"),
        Button("Send back", f"/devex-deny {idea.id} <changes needed>")))


def report(bot: Bot, idea: Idea, record: dict) -> str:
    rev = record["review"]
    names = ", ".join(f["path"] for f in record["files"])
    verdict = "looks right" if rev["verdict"] == builder.OK else "still has things to fix"
    findings = "".join(f"\n  - {x}" for x in rev["findings"])
    return (f"The bot built it: {record['summary']}\nFiles ({len(record['files'])}): {names}\n"
            f"The reviewing AI says it {verdict}.{findings}\n{NOT_RUN}\n"
            f"Maintainer: read the files on the dashboard (idea #{idea.id}), then "
            f"`/devex-publish {idea.id} [install steps]`, or `/devex-deny {idea.id} <changes needed>` "
            "and the bot changes it.")


def _tell(bot: Bot, idea: Idea, text: str) -> None:
    """A problem for the maintainer: said in the thread, and directly to them where the platform can."""
    bot.say(idea, text)
    bot.tell_maintainer(idea, text)


def forget(bot: Bot, idea: Idea) -> None:
    """The idea is deleted: its files go too."""
    tool_files.remove(bot.settings.builds_dir / str(idea.id))
