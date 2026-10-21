"""HTML for the maintainer dashboard. Every value is escaped: idea text, AI output and fetched pages are untrusted."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from html import escape
from typing import Any

from ..plan.planner import FREE
from ..stages import LABELS, TERMINAL, WAITING_ON_MAINTAINER, Stage
from ..store import Idea, Project
from .theme import CSS

_URL = re.compile(r"https?://[^\s<>\"']+")

_NAV = (("/", "Ideas"), ("/maintainers", "Maintainers"), ("/projects", "Projects"))


def e(value: Any) -> str:
    return escape("" if value is None else str(value))


def empty(title: str, hint: str = "") -> str:
    """An empty state: one Material shape, a title and a hint."""
    return (f'<div class="empty"><span class="shape" aria-hidden="true"></span><b>{e(title)}</b>'
            f'{f"<span class=muted>{e(hint)}</span>" if hint else ""}</div>')


def confirm(csrf: str, action: str, label: str, yes: str, **fields: Any) -> str:
    """A destructive button that asks first, without scripts: the first tap opens the confirm button."""
    return (f'<details class="confirm"><summary class="btn danger">{e(label)}</summary>'
            f'<form method="post" action="{e(action)}">{_hidden(csrf, **fields)}'
            f'<button class="danger strong">{e(yes)}</button></form></details>')


def link_or_text(url: str | None) -> str:
    """Only plain http(s) links become clickable."""
    if url and _URL.fullmatch(url):
        return f'<a href="{e(url)}" rel="noopener noreferrer" target="_blank">{e(url)}</a>'
    return e(url)


def stage_pill(stage: Stage) -> str:
    cls = "wait" if stage in WAITING_ON_MAINTAINER else "done" if stage is Stage.PUBLISHED else \
        "bad" if stage in (Stage.REJECTED, Stage.STOPPED) else ""
    return f'<span class="pill {cls}">{e(LABELS[stage])}</span>'


def _hidden(csrf: str, **fields: Any) -> str:
    items = {"csrf": csrf, **fields}
    return "".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in items.items())


def layout(title: str, body: str, *, user: str, is_admin: bool, csrf: str, flash: str = "",
           notices: list[str] = ()) -> str:
    note = "".join(f'<div class="flash warn" role="status">{e(n)}</div>' for n in notices)
    note += f'<div class="flash" role="status">{e(flash)}</div>' if flash else ""
    links = (*_NAV, ("/people", "People"), ("/slack", "Slack")) if is_admin else _NAV
    nav = "".join(f'<a href="{h}"{" aria-current=page" if t == title else ""}>{t}</a>' for h, t in links)
    me = " aria-current=page" if title == "Account" else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} - DevExAI</title>
<style>{CSS}</style></head><body><header>
<a class="brand" href="/"><span class="mark" aria-hidden="true"></span>DevExAI</a><nav>{nav}</nav>
<span class="grow"></span><span class="who">Signed in as <a href="/account"{me}>{e(user)}{" (admin)" if is_admin else ""}</a></span>
<form method="post" action="/logout">{_hidden(csrf)}<button class="text">Sign out</button></form>
</header><main>{note}{body}</main></body></html>"""


def ts(value: str | None) -> str:
    """2026-10-20T14:11:12+00:00 -> 2026-10-20 14:11"""
    return e(value[:16].replace("T", " ")) if value else ""


def _age(ts: str | None, now: datetime) -> str:
    if not ts:
        return ""
    hours = (now - datetime.fromisoformat(ts)).total_seconds() / 3600
    return f"{hours:.0f}h" if hours >= 1 else f"{hours * 60:.0f}m"


def ideas_page(ideas: list[Idea], *, overdue, user: str, view: str) -> str:
    now = datetime.now(UTC)
    views = [("open", "Open"), ("mine", "Mine"), ("waiting", "Waiting on a maintainer"), ("all", "All")]
    filters = "".join(f'<a href="/?view={k}"{" aria-current=page" if k == view else ""}>{e(v)}</a>'
                      for k, v in views)
    rows = []
    for i in ideas:
        late = overdue(i.waiting_since, now)
        wait = f'<span class="{"late" if late else ""}">{e(_age(i.waiting_since, now))}' \
               f'{" overdue" if late else ""}</span>'
        rows.append(f'<tr><td><a href="/idea/{i.id}">#{i.id}</a></td><td><a href="/idea/{i.id}">'
                    f'{e(i.title or "(no title yet)")}</a></td><td>{stage_pill(i.stage)}</td>'
                    f'<td>{e(i.poster)}</td><td>{e(i.maintainer or "")}</td><td>{e(i.topic or "")}</td>'
                    f'<td>{wait}</td><td class="muted">{ts(i.updated_at)}</td></tr>')
    table = ("<table><tr><th>#</th><th>Title</th><th>Stage</th><th>Poster</th><th>Maintainer</th>"
             "<th>Topic</th><th>Waiting</th><th>Updated (UTC)</th></tr>" + "".join(rows) + "</table>"
             if rows else empty("No ideas here", "Ideas posted in chat show up here."))
    return f'<h1>Ideas</h1><nav class="filters">{filters}</nav>{table}'


def maintainers_page(maintainers, ideas: list[Idea], *, overdue) -> str:
    now = datetime.now(UTC)
    open_ = Counter(i.maintainer for i in ideas if i.stage not in TERMINAL)
    waiting = Counter(i.maintainer for i in ideas if i.stage in WAITING_ON_MAINTAINER)
    late = Counter(i.maintainer for i in ideas if overdue(i.waiting_since, now))
    done = Counter(i.maintainer for i in ideas if i.stage is Stage.PUBLISHED)
    rows = "".join(
        f'<tr><td>{e(m.name)}</td><td>{e(", ".join(m.topics))}</td><td>{open_[m.name]}</td>'
        f'<td>{waiting[m.name]}</td><td class="{"late" if late[m.name] else ""}">{late[m.name]}</td>'
        f'<td>{done[m.name]}</td></tr>' for m in maintainers)
    return ("<h1>Maintainers</h1><table><tr><th>Name</th><th>Topics</th><th>Open ideas</th>"
            "<th>Waiting on them</th><th>Overdue</th><th>Published</th></tr>" + rows + "</table>"
            '<p class="muted">Admins add and remove maintainers on the People page.</p>')


def _list(items) -> str:
    return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>" if items else '<p class="muted">none</p>'


def _gate(gate: dict[str, Any] | None) -> str:
    if not gate:
        return '<p class="muted">Not checked yet.</p>'
    out = [f'<p>Verdict: <b>{e(gate.get("verdict"))}</b>'
           f'{" &middot; <span class=late>possible prompt injection found</span>" if gate.get("injection_found") else ""}'
           f' &middot; topic {e(gate.get("topic"))}</p>', _list(gate.get("reasons", []))]
    for link in gate.get("links", []):
        state = "fetched" + (", cut short" if link.get("truncated") else "") if link.get("ok") \
            else f'not fetched: {e(link.get("error"))}'
        out.append(f'<details><summary>{e(link.get("url"))} ({state})</summary>'
                   f'<pre>{e(link.get("text") or "")}</pre></details>')
    return "".join(out)


def _plan(plan: dict[str, Any] | None) -> str:
    if not plan:
        return '<p class="muted">No plan yet.</p>'
    res = "".join(
        f'<tr><td>{e(r.get("name"))}</td><td>{e(r.get("why"))}</td><td>{e(r.get("cost"))}</td>'
        f'<td>{"free, automatic" if r.get("lane") == FREE else "<b>needs approval</b>"}</td></tr>'
        for r in plan.get("resources", []))
    return (f'<p>{e(plan.get("summary"))}</p><p>Size: <b>{e(plan.get("size"))}</b> &middot; assistants: '
            f'{e(", ".join(plan.get("assistants", [])))}</p><h3>Deliverables</h3>{_list(plan.get("deliverables", []))}'
            f'<h3>Test plan</h3><p>{e(plan.get("test_plan"))}</p>'
            + (f"<h3>Resources</h3><table><tr><th>Name</th><th>Why</th><th>Cost</th><th>Lane</th></tr>{res}</table>"
               if res else "")
            + f'<h3>Possible duplicates</h3>{_list(plan.get("duplicate_of", []))}'
            f'<h3>Existing tools</h3>{_list(plan.get("existing_tools", []))}'
            f'<h3>Open questions</h3>{_list(plan.get("questions", []))}')


def _built(build: dict[str, Any] | None, folder: str = "") -> str:
    """What the bot builder wrote: model output, shown escaped and never run here."""
    if not build or not build.get("files"):
        note = f"The last build failed: {e(build['error'])}" if build and build.get("error") else             "The bot is building it now." if build and build.get("pending") else "Nothing built yet."
        return f'<p class="muted">{note}</p>'
    rev = build.get("review") or {}
    safe = "" if rev.get("safe", True) else         f'<p class="late">The reviewing AI found safety problems:</p>{_list(rev.get("safety_issues", []))}'
    files = "".join(f'<details><summary>{e(f["path"])}</summary><pre>{e(f["content"])}</pre></details>'
                    for f in build["files"])
    return (f'<p>{e(build.get("summary"))}</p>{safe}'
            f'<p>Review by a second AI: <b>{e(rev.get("verdict"))}</b> after {e(build.get("rounds"))} round(s)</p>'
            f'{_list(rev.get("findings", []))}'
            f'<p class="late">The tests were written but not run yet (that needs a sandbox).</p>'
            f'<p>Install: {e(build.get("install"))}<br>Run the tests: <code>{e(build.get("test_command"))}</code></p>'
            + (f'<p class="muted">Files on the server: {e(folder)}</p>' if folder else "")
            + f'<h3>Files</h3>{files}')


_TONE = {"deny": "danger", "stop": "danger", "suggest": "tonal"}


def _form(csrf: str, idea_id: int, action: str, label: str, field: str = "", required: bool = False) -> str:
    box = (f'<input type="text" name="text" placeholder="{e(field)}" aria-label="{e(field)}" maxlength="2000"'
           f'{" required" if required else ""}>' if field else "<br>")
    return (f'<form method="post" action="/action">{_hidden(csrf, action=action, idea=idea_id)}'
            f'<b>{e(label)}</b>{box}<button class="{_TONE.get(action, "")}">{e(label)}</button></form>')


def _actions(idea: Idea, csrf: str, maintainers: list[str]) -> str:
    s, f = idea.stage, []
    if s is Stage.SAFETY_UNSURE:
        f += [_form(csrf, idea.id, "approve", "Allow it"),
              _form(csrf, idea.id, "deny", "Reject", "Why it cannot go ahead", required=True)]
    if s is Stage.POSSIBLE_DUPLICATE:
        f += [_form(csrf, idea.id, "approve", "Not a duplicate"),
              _form(csrf, idea.id, "deny", "Close as duplicate", "Of which idea", required=True)]
    if s in (Stage.PLAN_READY, Stage.WAITING_APPROVAL):
        f += [_form(csrf, idea.id, "approve", "Approve plan" if s is Stage.PLAN_READY else "Approve resources"),
              _form(csrf, idea.id, "suggest", "Re-plan", "Suggest a change", required=True),
              _form(csrf, idea.id, "deny", "Deny", "Why", required=True)]
    if s is Stage.BUILDING:
        if not (idea.build or {}).get("pending"):
            f.append(_form(csrf, idea.id, "built", "Mark built", "Note (optional)"))
    if s is Stage.UNDER_REVIEW:
        f += [_form(csrf, idea.id, "publish", "Publish", "Install steps for the blog post (optional)"),
              _form(csrf, idea.id, "deny", "Send back", "Changes needed", required=True)]
    if s not in TERMINAL:
        opts = "".join(f'<option value="{e(m)}">{e(m)}</option>' for m in maintainers if m != idea.maintainer)
        if opts:
            f.append(f'<form method="post" action="/action">{_hidden(csrf, action="assign", idea=idea.id)}'
                     f'<b>Hand to another maintainer</b><br><select name="text">{opts}</select> '
                     f'<button class="tonal">Reassign</button></form>')
        f.append(_form(csrf, idea.id, "stop", "Stop idea", "Reason", required=True))
    return f'<h2>Actions</h2><div class="actions">{"".join(f)}</div>' if f else ""


def idea_page(idea: Idea, audit: list[dict[str, str]], *, csrf: str, maintainers: list[str],
              admin: bool = False, build_folder: str = "") -> str:
    unchecked = not idea.gate or idea.gate.get("verdict") != "pass"
    facts = [("Stage", stage_pill(idea.stage)), ("Poster", e(idea.poster)), ("Maintainer", e(idea.maintainer)),
             ("Topic", e(idea.topic)), ("Thread", e(idea.thread_ref)), ("Created (UTC)", ts(idea.created_at)),
             ("Waiting since (UTC)", ts(idea.waiting_since))]
    facts.append(("Built live", {"yes": "yes, with the poster", "no": "no"}.get(idea.live or "", "not answered")))
    if idea.stop_reason:
        facts.append(("Reason", e(idea.stop_reason)))
    if idea.blog_url:
        facts.append(("Blog post", link_or_text(idea.blog_url)))
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in facts)
    log = "".join(f'<tr><td class="muted">{ts(a["at"])}</td><td>{e(a["actor"])}</td><td>{e(a["action"])}</td>'
                  f'<td>{e(a["detail"])}</td></tr>' for a in audit)
    warn = ' <span class="late">(not passed by the safety check: read with care)</span>' if unchecked else ""
    return (f'<h1>#{idea.id} {e(idea.title or "(no title yet)")}</h1><table>{rows}</table>'
            f'{_actions(idea, csrf, maintainers)}'
            f'<h2>Idea text{warn}</h2><pre>{e(idea.text)}</pre>'
            f'<h2>Safety check</h2><div class="card">{_gate(idea.gate)}</div>'
            f'<h2>Plan</h2><div class="card">{_plan(idea.plan)}</div>'
            + (f'<h2>Built tool</h2><div class="card">{_built(idea.build, build_folder)}</div>' if idea.build else "")
            + f'<h2>History</h2>'
            f'<table><tr><th>When (UTC)</th><th>Who</th><th>What</th><th>Detail</th></tr>{log}</table>'
            + (f'<h2>Delete</h2><p class="muted">Removes this idea, its history and the bot&#39;s messages about it in '
               f'chat. People&#39;s own replies stay. Cannot be undone.</p>'
               f'{confirm(csrf, "/delete-idea", "Delete idea", f"Yes, delete #{idea.id}", idea=idea.id)}'
               if admin else ""))


def projects_page(projects: list[Project], *, csrf: str) -> str:
    rows = "".join(
        f'<tr><td>{e(p.name)}</td><td>{e(p.summary)}</td><td class="muted">{e(p.updated_by)}, {ts(p.updated_at)}</td>'
        f'<td>{confirm(csrf, "/project", "Remove", f"Remove {p.name}", op="remove", name=p.name)}</td></tr>'
        for p in projects)
    table = ("<table><tr><th>Name</th><th>Summary</th><th>Updated</th><th></th></tr>" + rows + "</table>"
             if rows else empty("No projects yet", "Add one below so the planner knows it."))
    return (f"<h1>Projects</h1><p class='muted'>Short summaries the planner reads. The bot never writes them.</p>"
            f"{table}<h2>Add or update</h2><form class='card' method='post' action='/project'>"
            f"{_hidden(csrf, op='set')}<b>Name</b> (one word)<input type='text' name='name' required "
            f"pattern='\\S+' maxlength='80'><b>Summary</b><input type='text' name='summary' required "
            f"maxlength='1000'><button>Save</button></form>")


def bare_page(title: str, body: str) -> str:
    """A page without the signed-in header: sign-in, setup and errors."""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} - DevExAI</title>'
            f'<style>{CSS}</style></head><body class="bare"><div class="hero" aria-hidden="true"></div>'
            f'<main>{body}</main></body></html>')


def message_page(title: str, text: str) -> str:
    return bare_page(title, f'<div class="narrow card"><h1>{e(title)}</h1><p>{e(text)}</p>'
                           f'<p><a href="/">Back to DevExAI</a></p></div>')
