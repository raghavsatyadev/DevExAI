"""POST handlers for first-run setup, the account page and the admin's People page."""

from __future__ import annotations

import hmac
from http import HTTPStatus
from typing import TYPE_CHECKING

from ..stages import TERMINAL
from ..store.people import MIN_PASSWORD, PeopleError, clean_topics
from . import people_pages

if TYPE_CHECKING:
    from ..store import Person
    from .auth import Session
    from .server import _Handler


def setup_post(h: _Handler, form: dict[str, str]) -> None:
    """Create the first admin's sign-in. Works once, and only with the token printed at start."""
    server, people = h.server, h.server.bot.store.people
    with server.setup_lock:
        token = server.setup_token
        if not token:
            return h._redirect("/login")
        if not hmac.compare_digest(form.get("token", "").encode(), token.encode()):
            return h._deny(HTTPStatus.UNAUTHORIZED, "That setup link is wrong or from an earlier run.")
        admin = next(p for p in people.list() if p.is_admin)
        email = form.get("email", "").strip()
        try:
            if form.get("password", "") != form.get("password2", ""):
                raise PeopleError("The two passwords are different.")
            people.update(admin.name, email=email)
            people.set_password(admin.name, form.get("password", ""))
        except PeopleError as e:
            return h._send(HTTPStatus.BAD_REQUEST, people_pages.setup_page(token, admin.name, str(e), email))
        server.setup_token = None
    server.bot.store.audit.add(None, admin.name, "setup", "admin account created")
    h.sign_in(admin.name, "Welcome! Connect Slack here, then add the other maintainers on the People page.", "/slack")


def account_post(h: _Handler, sess: Session, me: Person, form: dict[str, str]) -> None:
    people = h.server.bot.store.people
    try:
        if people.check_login(me.email or "", form.get("current", "")) is None:
            raise PeopleError("Your current password is wrong.")
        if form.get("password", "") != form.get("password2", ""):
            raise PeopleError("The two new passwords are different.")
        people.set_password(me.name, form.get("password", ""))
    except PeopleError as e:
        h.server.sessions.flash(sess, str(e))
        return h._redirect("/account")
    h.server.sessions.end_user(me.name)
    h.server.bot.store.audit.add(None, me.name, "password_changed", "own")
    h.sign_in(me.name, "Password changed. Other sessions were signed out.")


def people_post(h: _Handler, sess: Session, me: Person, form: dict[str, str]) -> None:
    bot, sessions = h.server.bot, h.server.sessions
    op, name = form.get("op", ""), form.get("name", "").strip()  # as written: chat IDs can be case-sensitive
    people = bot.store.people
    try:
        if op == "add":
            if form.get("password") and len(form["password"]) < MIN_PASSWORD:  # check before adding anyone
                raise PeopleError(f"Use a password of at least {MIN_PASSWORD} characters.")
            if form.get("password") and not form.get("email", "").strip():
                raise PeopleError("Give this person an email address first; it is their sign-in name.")
            person = people.add(name, form.get("email", ""), form.get("role", "maintainer"),
                                clean_topics(form.get("topics", "")))
            if form.get("password"):
                people.set_password(person.name, form["password"])
            said = f"Added {person.name}." + ("" if person.email else " Give them an email so they can sign in.")
        elif op == "edit":
            people.update(name, email=form.get("email", ""), role=form.get("role"),
                          topics=clean_topics(form.get("topics", "")))
            said = f"Saved {name}."
        elif op == "password":
            if name == me.name:
                raise PeopleError("Change your own password on the Account page.")
            people.set_password(name, form.get("password", ""))
            sessions.end_user(name)
            said = f"New password set for {name}. Give it to them privately."
        elif op in ("deactivate", "activate"):
            if name == me.name:
                raise PeopleError("You cannot deactivate yourself.")
            people.update(name, active=op == "activate")
            said = f"{name} is {op}d."
            if op == "deactivate":
                sessions.end_user(name)
                moved = bot.hand_over(name, me.name)
                left = sum(1 for i in bot.store.ideas.list(100_000) if i.maintainer == name and i.stage not in TERMINAL)
                said += f" {moved} open idea(s) handed to others." + (
                    f" {left} could not move: there is no other maintainer." if left else "")
        else:
            raise PeopleError("Unknown change.")
    except PeopleError as e:
        sessions.flash(sess, str(e))
        return h._redirect("/people")
    bot.store.audit.add(None, me.name, f"people:{op}", name)
    sessions.flash(sess, said)
    h._redirect("/people")
