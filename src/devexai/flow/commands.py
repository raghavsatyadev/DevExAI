"""Chat commands. In an idea's thread the idea number can be left out."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..chat import Button, Event
from ..plan.planner import FREE, needs_approval
from ..stages import LABELS, TERMINAL, InvalidTransition, Stage
from ..store import Idea
from . import post
from .pipeline import PLAN, POSTER, Job, ask_live, ask_poster

if TYPE_CHECKING:
    from .bot import Bot

HELP = """DevExAI commands:
  /devex-idea <text and links>     submit an idea (or just post it in the ideas channel / DM me)
  /devex-status [id]               where an idea is; without id, your ideas
  /devex-stop [id] <reason>        stop an idea (poster or maintainer)
  /devex-live [id] yes|no          poster: build it live in public, answering the bot and steering it
  /devex-suggest [id] <change>     re-plan with a suggestion (maintainers; the poster in a live build)
Maintainers:
  /devex-approve [id]              allow after an unsure safety check, approve a plan or its paid/login resources
  /devex-deny [id] <reason>        reject, deny resources, or send a built tool back with changes
  /devex-built [id] [note]         the tool is built; it goes to review
  /devex-publish [id] [install]    release it: writes the blog post (Markdown) and announces it
  /devex-assign [id] <maintainer>  hand the idea to another maintainer
  /devex-projects [list | show <name> | set <name> <summary> | remove <name>]"""

MAINTAINER_ONLY = {"approve", "deny", "built", "publish", "assign", "projects"}
_ID = re.compile(r"#?(\d+)$")


class Refusal(Exception):
    """A polite no, shown to the user."""


def dispatch(bot: Bot, event: Event) -> None:
    text = event.text.strip()
    if not text.startswith("/devex-"):
        _plain_message(bot, event, text)
        return
    name, _, rest = text[len("/devex-"):].partition(" ")
    handler = _COMMANDS.get(name)
    if handler is None:
        bot.reply(event, HELP)
        return
    try:
        if name in MAINTAINER_ONLY and not bot.router.is_maintainer(event.user):
            raise Refusal(f"Only maintainers can use /devex-{name}.")
        handler(bot, event, rest.strip())
    except Refusal as e:
        bot.reply(event, str(e))
    except InvalidTransition:
        bot.reply(event, "That idea has moved on already; check /devex-status.")


def _plain_message(bot: Bot, event: Event, text: str) -> None:
    if event.thread:
        idea = bot.store.ideas.find_by_thread(event.thread)
        if idea:  # people talking in the idea's thread: keep it in the record
            bot.store.audit.add(idea.id, event.user, "comment", text[:500])
        return
    if text and (event.is_dm or event.channel == bot.settings.ideas_channel):
        bot.submit_idea(event, text)


def _target(bot: Bot, event: Event, rest: str) -> tuple[Idea, str]:
    """Idea named by a leading id, else the thread's idea. Returns the idea and the remaining text."""
    first, _, tail = rest.partition(" ")
    if m := _ID.match(first):
        try:
            return bot.store.ideas.get(int(m.group(1))), tail.strip()
        except KeyError:
            raise Refusal(f"There is no idea #{m.group(1)}.") from None
    idea = bot.store.ideas.find_by_thread(event.thread) if event.thread else None
    if idea is None:
        raise Refusal("Which idea? Add its number, e.g. `/devex-status 12`, or reply in its thread.")
    return idea, rest


def _cmd_idea(bot: Bot, event: Event, rest: str) -> None:
    if not rest:
        raise Refusal("Tell me the idea: `/devex-idea <what you want, plus any links>`.")
    bot.submit_idea(event, rest)


def _cmd_help(bot: Bot, event: Event, rest: str) -> None:
    bot.reply(event, HELP)


def _cmd_status(bot: Bot, event: Event, rest: str) -> None:
    if rest or event.thread:
        idea, _ = _target(bot, event, rest)
        keeper = bot.chat.mention(idea.maintainer) if idea.maintainer else "not assigned yet"
        lines = [f"{idea.label}: {LABELS[idea.stage]}. Poster {bot.chat.mention(idea.poster)}, "
                 f"maintainer {keeper}."]
        if idea.stop_reason:
            lines.append(f"Reason: {idea.stop_reason}")
        if idea.blog_url:
            lines.append(f"Blog post: {idea.blog_url}")
        lines += [f"  {a['at']} {a['actor']}: {a['action']}" for a in bot.store.audit.for_idea(idea.id)[-5:]]
        bot.reply(event, "\n".join(lines))
        return
    mine = bot.router.is_maintainer(event.user)
    ideas = [i for i in bot.store.ideas.list(200) if mine or i.poster == event.user][:15]
    if not ideas:
        bot.reply(event, "No ideas yet. Submit one with /devex-idea.")
        return
    bot.reply(event, "\n".join(f"{i.label}: {LABELS[i.stage]}" for i in ideas))


def _cmd_stop(bot: Bot, event: Event, rest: str) -> None:
    idea, reason = _target(bot, event, rest)
    if event.user != idea.poster and not bot.router.is_maintainer(event.user):
        raise Refusal("Only the poster or a maintainer can stop this idea.")
    if idea.stage in TERMINAL:
        raise Refusal(f"{idea.label} is already {LABELS[idea.stage]}.")
    reason = reason or "no reason given"
    idea = bot.store.ideas.update(idea.id, stop_reason=f"{reason} (by {event.user})")
    bot.move(idea, Stage.STOPPED, f"Stopped by {bot.chat.mention(event.user)}: {reason}", actor=event.user)


def _cmd_approve(bot: Bot, event: Event, rest: str) -> None:
    idea, _ = _target(bot, event, rest)
    who = bot.chat.mention(event.user)
    if idea.stage in (Stage.SAFETY_UNSURE, Stage.POSSIBLE_DUPLICATE):
        done = "allowed it" if idea.stage is Stage.SAFETY_UNSURE else "says it is not a duplicate"
        idea = bot.move(idea, Stage.RESEARCHING, f"{who} {done}. Researching and planning now.",
                        actor=event.user)
        if idea.live is None:
            ask_live(bot, idea)
        bot.pipeline.submit(Job(PLAN, idea.id))
    elif idea.stage is Stage.PLAN_READY:
        gated = needs_approval(idea.plan or {})
        if not gated:
            _start_building(bot, idea, f"Plan approved by {who}.", event.user)
            return
        items = "\n".join(f"  - {r['name']}: {r['why']} (cost: {r['cost']})" for r in gated)
        bot.move(idea, Stage.WAITING_APPROVAL,
                 f"Plan approved by {who}. These need a maintainer's yes because they are paid or need "
                 f"an account, key or licence:\n{items}\nKeys and logins go into the secret store, "
                 "never into chat.", actor=event.user, buttons=(
                     Button("Approve", f"/devex-approve {idea.id}"),
                     Button("Deny", f"/devex-deny {idea.id} <reason>"),
                     Button("Suggest alternative", f"/devex-suggest {idea.id} <alternative>"),
                 ))
    elif idea.stage is Stage.WAITING_APPROVAL:
        _start_building(bot, idea, f"Resources approved by {who}.", event.user)
    elif idea.stage is Stage.UNDER_REVIEW:
        raise Refusal(f"To release it, use `/devex-publish {idea.id} [install steps]`.")
    else:
        raise Refusal(f"{idea.label} is {LABELS[idea.stage]}; there is nothing to approve.")


def _start_building(bot: Bot, idea: Idea, why: str, actor: str) -> None:
    free = [r["name"] for r in (idea.plan or {}).get("resources", []) if r.get("lane") == FREE]
    used = f" Free resources, used automatically: {', '.join(free)}." if free else ""
    bot.move(idea, Stage.BUILDING, f"{why}{used}\nA person builds the tool now, with tests and a short "
             f"README. When it is ready: `/devex-built {idea.id}`.", actor=actor)


def _cmd_deny(bot: Bot, event: Event, rest: str) -> None:
    idea, reason = _target(bot, event, rest)
    reason = reason or "no reason given"
    who = bot.chat.mention(event.user)
    if idea.stage is Stage.SAFETY_UNSURE:
        idea = bot.store.ideas.update(idea.id, stop_reason=reason)
        bot.move(idea, Stage.REJECTED, f"{who} decided it cannot go ahead: {reason}", actor=event.user)
    elif idea.stage is Stage.POSSIBLE_DUPLICATE:
        idea = bot.store.ideas.update(idea.id, stop_reason=reason)
        bot.move(idea, Stage.STOPPED, f"{who} closed it: {reason}", actor=event.user)
    elif idea.stage in (Stage.PLAN_READY, Stage.WAITING_APPROVAL):
        idea = bot.store.ideas.update(idea.id, stop_reason=f"denied: {reason}")
        bot.move(idea, Stage.STOPPED, f"{who} denied it: {reason}\n(To re-plan instead, use /devex-suggest.)",
                 actor=event.user)
    elif idea.stage is Stage.UNDER_REVIEW:
        bot.move(idea, Stage.BUILDING, f"{who} asked for changes: {reason}\nWhen fixed: `/devex-built {idea.id}`.",
                 actor=event.user)
    else:
        raise Refusal(f"{idea.label} is {LABELS[idea.stage]}; there is nothing to deny.")


def _cmd_suggest(bot: Bot, event: Event, rest: str) -> None:
    idea, change = _target(bot, event, rest)
    maintainer = bot.router.is_maintainer(event.user)
    if not maintainer and not (event.user == idea.poster and idea.live == "yes"):
        raise Refusal("Only maintainers can suggest changes, or the poster when the tool is built live "
                      f"(`/devex-live {idea.id} yes`).")
    if not change:
        raise Refusal("Say what to change: `/devex-suggest <id> <your suggestion>`.")
    if idea.stage not in (Stage.PLAN_READY, Stage.WAITING_APPROVAL):
        raise Refusal(f"{idea.label} is {LABELS[idea.stage]}; suggestions apply to a plan.")
    who = bot.chat.mention(event.user)
    if maintainer:
        bot.move(idea, Stage.RESEARCHING, f"{who} suggested: {change}\nRe-planning.", actor=event.user)
        bot.pipeline.submit(Job(PLAN, idea.id, note=change))
    else:  # not echoed: it has not passed the safety check yet
        bot.move(idea, Stage.RESEARCHING, f"Thanks {who}. Checking your suggestion, then re-planning.",
                 actor=event.user)
        bot.store.audit.add(idea.id, event.user, "suggestion", change[:500])
        bot.pipeline.submit(Job(PLAN, idea.id, note=change, by=POSTER))


def _cmd_live(bot: Bot, event: Event, rest: str) -> None:
    idea, answer = _target(bot, event, rest)
    if event.user != idea.poster:
        raise Refusal(f"Only {bot.chat.mention(idea.poster)}, who posted the idea, can choose this.")
    answer = answer.lower()
    if answer not in ("yes", "no"):
        raise Refusal(f"Answer `/devex-live {idea.id} yes` or `/devex-live {idea.id} no`.")
    if idea.stage in TERMINAL:
        raise Refusal(f"{idea.label} is already {LABELS[idea.stage]}.")
    idea = bot.store.ideas.update(idea.id, live=answer)
    bot.store.audit.add(idea.id, event.user, "live", answer)
    if answer == "yes":
        bot.say(idea, f"{bot.chat.mention(event.user)} is building {idea.label} live. Questions from the bot "
                f"come here, and you can steer it with `/devex-suggest {idea.id} <your suggestion>`.")
        ask_poster(bot, idea)
    else:
        bot.say(idea, f"OK {bot.chat.mention(event.user)}, the maintainer will handle the questions. "
                f"You can still follow every step here.")


def _cmd_built(bot: Bot, event: Event, rest: str) -> None:
    idea, note = _target(bot, event, rest)
    if idea.stage is not Stage.BUILDING:
        raise Refusal(f"{idea.label} is {LABELS[idea.stage]}, not being built.")
    text = f"Built by {bot.chat.mention(event.user)}. {note}".strip()
    bot.move(idea, Stage.UNDER_REVIEW, f"{text}\nMaintainer: review the code, then "
             f"`/devex-publish {idea.id} [install steps]`, or `/devex-deny {idea.id} <changes needed>`.",
             actor=event.user, buttons=(Button("Publish", f"/devex-publish {idea.id}"),
                                        Button("Deny", f"/devex-deny {idea.id} <changes needed>")))


def _cmd_publish(bot: Bot, event: Event, rest: str) -> None:
    idea, note = _target(bot, event, rest)
    if idea.stage is not Stage.UNDER_REVIEW:
        raise Refusal(f"{idea.label} is {LABELS[idea.stage]}; only a reviewed tool can be published.")
    blog = bot.settings.blog
    name = post.filename(idea)
    if (blog.dir / name).exists():
        raise Refusal(f"A blog post file {name} is already there; move it away and publish again.")
    # Claim the release first: once it is Published nobody can send it back, so the post never
    # goes out for an idea that is still being changed. A concurrent deny makes this raise instead.
    idea = bot.store.ideas.move(idea.id, Stage.PUBLISHED, expect=Stage.UNDER_REVIEW)
    try:
        path = post.write(idea, blog.dir, maintainer=event.user, note=note)
    except (post.PostExists, OSError) as e:
        bot.store.audit.add(idea.id, event.user, "post-failed", str(e)[:500])
        raise Refusal(f"{idea.label} is published, but its blog post could not be written ({e}). "
                      f"Put the post in {blog.dir} by hand.") from None
    url = blog.link(path.name)
    idea = bot.store.ideas.update(idea.id, blog_url=url)
    poster = bot.chat.mention(idea.poster)
    bot.announce(idea, f"Released by {bot.chat.mention(event.user)}. Blog post: {url}\n"
                 f"Thank you {poster} for the idea!", actor=event.user)
    bot.chat.post(bot.settings.public_channel,
                  f"New tool: *{idea.title or idea.label}*. Idea by {poster}. Read and install: {url}")


def _cmd_assign(bot: Bot, event: Event, rest: str) -> None:
    idea, name = _target(bot, event, rest)
    name = name.lstrip("@")
    if not bot.router.is_maintainer(name):
        raise Refusal(f"{name or 'Nobody'} is not a maintainer. Use `/devex-assign {idea.id} <maintainer>`.")
    if idea.stage in TERMINAL:
        raise Refusal(f"{idea.label} is already {LABELS[idea.stage]}.")
    if name == idea.maintainer:
        raise Refusal(f"{bot.chat.mention(name)} already looks after {idea.label}.")
    old = idea.maintainer
    bot.store.ideas.update(idea.id, maintainer=name)
    if idea.waiting_since:
        bot.store.ideas.reset_wait(idea.id)  # the new maintainer gets the full response time
    bot.store.audit.add(idea.id, event.user, "reassigned", f"{old} -> {name}")
    bot.say(idea, f"{bot.chat.mention(event.user)} handed {idea.label} to {bot.chat.mention(name)}"
                  f" ({LABELS[idea.stage]}).")


def _cmd_projects(bot: Bot, event: Event, rest: str) -> None:
    action, _, args = rest.partition(" ")
    name, _, summary = args.strip().partition(" ")
    summary = summary.strip()
    projects = bot.store.projects
    if action in ("", "list"):
        rows = projects.list()
        bot.reply(event, "\n".join(f"- {p.name}: {p.summary}" for p in rows) or
                  "No projects yet. Add one: `/devex-projects set <name> <summary>`.")
    elif action == "show" and name:
        p = projects.get(name)
        bot.reply(event, f"{p.name}: {p.summary}\n(updated by {p.updated_by}, {p.updated_at})" if p
                  else f"No project called {name}.")
    elif action == "set" and name and summary:
        new = projects.upsert(name, summary, event.user)
        bot.store.audit.add(None, event.user, "project_added" if new else "project_edited", name)
        bot.reply(event, f"Project {name} {'added' if new else 'updated'}.")
    elif action == "remove" and name:
        gone = projects.remove(name)
        if gone:
            bot.store.audit.add(None, event.user, "project_removed", name)
        bot.reply(event, f"Project {name} removed." if gone else f"No project called {name}.")
    else:
        raise Refusal("Use: /devex-projects [list | show <name> | set <name> <summary> | remove <name>]")


_COMMANDS = {
    "idea": _cmd_idea, "help": _cmd_help, "status": _cmd_status, "stop": _cmd_stop,
    "approve": _cmd_approve, "deny": _cmd_deny, "suggest": _cmd_suggest, "built": _cmd_built,
    "publish": _cmd_publish, "assign": _cmd_assign, "projects": _cmd_projects, "live": _cmd_live,
}
