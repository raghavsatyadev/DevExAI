"""HTML for sign-in, first-run setup, the account page and the admin's People page."""

from __future__ import annotations

from collections import Counter

from ..stages import TERMINAL
from ..store import Idea, Person
from ..store.people import MIN_PASSWORD, ROLES
from .pages import _hidden, bare_page, confirm, e, ts

_PW = f'minlength="{MIN_PASSWORD}" maxlength="200" autocomplete="new-password" required'


def _err(error: str) -> str:
    return f'<p class="err">{e(error)}</p>' if error else ""


def login_page(error: str = "", email: str = "") -> str:
    return bare_page("Sign in", f"""<div class="narrow card"><h1>DevExAI sign in</h1>{_err(error)}
<form method="post" action="/login"><b>Email</b><input type="email" name="email" value="{e(email)}"
 autocomplete="username" required maxlength="254" autofocus><b>Password</b><input type="password"
 name="password" autocomplete="current-password" required maxlength="200"><button class="big">Sign in</button></form>
<p class="muted">Forgot your password? Ask an admin to set a new one.</p></div>""")


def setup_page(token: str, admin: str, error: str = "", email: str = "") -> str:
    return bare_page("Set up", f"""<div class="narrow card"><h1>Welcome to DevExAI</h1>
<p>Create the admin account for <b>{e(admin)}</b>. You will use it to sign in from now on, and to add
the other maintainers on the People page.</p>{_err(error)}
<form method="post" action="/setup"><input type="hidden" name="token" value="{e(token)}">
<b>Your email</b><input type="email" name="email" value="{e(email)}" required maxlength="254" autofocus
 autocomplete="username"><b>Password</b> (at least {MIN_PASSWORD} characters)<input type="password"
 name="password" {_PW}><b>Password again</b><input type="password" name="password2" {_PW}>
<button class="big">Create admin account</button></form></div>""")


def account_page(person: Person, csrf: str) -> str:
    return f"""<h1>Your account</h1><table><tr><th>Name</th><td>{e(person.name)}</td></tr>
<tr><th>Email</th><td>{e(person.email)}</td></tr><tr><th>Role</th><td>{e(person.role)}</td></tr>
<tr><th>Topics</th><td>{e(", ".join(person.topics))}</td></tr></table>
<h2>Change password</h2><form class="card" style="max-width:480px" method="post" action="/account">
{_hidden(csrf)}<b>Current password</b><input type="password" name="current" required maxlength="200"
 autocomplete="current-password"><b>New password</b><input type="password" name="password" {_PW}>
<b>New password again</b><input type="password" name="password2" {_PW}><button>Change password</button>
</form><p class="muted">Changing it signs you out everywhere else.</p>"""


def _roles(current: str) -> str:
    return "".join(f'<option value="{r}"{" selected" if r == current else ""}>{r}</option>' for r in ROLES)


def _person_row(p: Person, open_ideas: int, csrf: str, me: str) -> str:
    edit = (f'<form method="post" action="/people">{_hidden(csrf, op="edit", name=p.name)}'
            f'<input type="email" name="email" value="{e(p.email)}" placeholder="email" maxlength="254">'
            f'<input type="text" name="topics" value="{e(" ".join(p.topics))}" placeholder="topics" maxlength="300">'
            f'<select name="role">{_roles(p.role)}</select><button class="tonal">Save</button></form>')
    pw = (f'<form method="post" action="/people">{_hidden(csrf, op="password", name=p.name)}'
          f'<input type="password" name="password" placeholder="new password" {_PW}>'
          f'<button class="tonal">{"Reset password" if p.has_password else "Set password"}</button></form>')
    if p.name == me:
        toggle = '<span class="muted">you</span>'
    elif p.active:
        toggle = confirm(csrf, "/people", "Deactivate", f"Deactivate {p.name}", op="deactivate", name=p.name)
    else:
        toggle = (f'<form method="post" action="/people">{_hidden(csrf, op="activate", name=p.name)}'
                  f'<button class="tonal">Reactivate</button></form>')
    state = ("active" if p.active else '<span class="late">inactive</span>') + \
        ("" if p.has_password else '<br><span class="muted">cannot sign in yet</span>')
    return (f'<tr><td><b>{e(p.name)}</b><br><span class="muted">since {ts(p.created_at)}</span></td>'
            f'<td>{state}</td><td>{open_ideas}</td><td>{edit}</td><td>{pw}</td><td>{toggle}</td></tr>')


def people_page(people: list[Person], ideas: list[Idea], *, csrf: str, me: str) -> str:
    open_ = Counter(i.maintainer for i in ideas if i.stage not in TERMINAL)
    rows = "".join(_person_row(p, open_[p.name], csrf, me) for p in people)
    return f"""<h1>People</h1><p class="muted">Maintainers look after ideas for their topics; admins can also
manage this list. Someone can sign in once they have an email and a password. Deactivating someone hands
their open ideas to other maintainers.</p>
<table><tr><th>Name</th><th>State</th><th>Open ideas</th><th>Email, topics, role</th><th>Password</th><th></th></tr>
{rows}</table><h2>Add a maintainer</h2><form class="card" method="post" action="/people">{_hidden(csrf, op="add")}
<b>Name</b> (their chat name, exactly as in chat)<input type="text" name="name" required maxlength="40"
 pattern="[A-Za-z0-9][A-Za-z0-9._\\-]*"><b>Email</b><input type="email" name="email" maxlength="254">
<b>Topics</b> (space separated, e.g. android backend)<input type="text" name="topics" maxlength="300">
<b>Role</b><select name="role" class="wide">{_roles("maintainer")}</select>
<b>First password</b> (optional; give it to them privately)<input type="password" name="password"
 maxlength="200" autocomplete="new-password"><button>Add maintainer</button></form>"""
