"""Maintainer dashboard: a small stdlib web server for the company network.

People sign in with email and password. On the very first start nobody has a password yet, so the bot
prints a one-time setup link that creates the admin account. Beyond this machine it only serves over
TLS, unless the admin explicitly accepts plain HTTP. Every idea action is a POST that runs the same
chat command a maintainer would type, so the rules, stage checks and thread updates are identical in
chat and on the web.
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import re
import secrets
import ssl
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..chat import Event
from ..chat.slack_ids import unmention
from ..config import WebSettings
from ..flow import commands
from ..stages import TERMINAL, WAITING_ON_MAINTAINER
from . import pages, people_pages
from .auth import SESSION_SECONDS, Session, Sessions, Throttle
from .people_routes import account_post, people_post, setup_post
from .slack_routes import slack_get, slack_post

log = logging.getLogger(__name__)

COOKIE = "devexai_session"
MAX_BODY = 64 * 1024
ACTIONS = {"approve", "deny", "suggest", "built", "publish", "stop", "assign"}
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "[::1]")
_SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                               "frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
    # not "no-referrer": that makes browsers send "Origin: null" on form posts, which the origin check refuses
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


class _Capture:
    """The bot, except that replies to the acting user come back to the web page instead of chat."""

    def __init__(self, bot):
        self._bot = bot
        self.replies: list[str] = []

    def __getattr__(self, name):
        return getattr(self._bot, name)

    def reply(self, event, text, buttons=()):
        self.replies.append(text)


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


class Dashboard(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, bot, web: WebSettings, env_path: Path = Path(".env")):
        self.local_only = is_loopback(web.host)
        if not self.local_only and not web.tls and not web.insecure_http:
            raise ValueError("[web] serving beyond this machine needs tls_cert and tls_key (or, on a network "
                             "you trust, insecure_http = true: passwords then travel unencrypted)")
        self.bot = bot
        self.web = web
        self.sessions = Sessions()
        self.throttle = Throttle()
        self.setup_lock = threading.Lock()
        self.chat_lock = threading.Lock()  # one chat platform switch at a time
        self.env_path = env_path
        self.slack_checks = None  # the Slack page's last test results
        self.notices: list[str] = []  # shown on every page, e.g. "claude CLI not found", "update ready"
        self.setup_token: str | None = None if bot.store.people.anyone_can_sign_in() else secrets.token_urlsafe(32)
        ctx = None
        if web.tls:  # load before binding, so a bad file does not leave the port taken
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(web.tls_cert, web.tls_key)
        super().__init__((web.host, web.port), _Handler)
        if ctx:
            # handshake on first read, in the request thread, so one slow client cannot stall accept()
            self.socket = ctx.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)

    @property
    def port(self) -> int:
        return self.server_address[1]

    @property
    def origins(self) -> set[str]:
        """Host header values we answer to. Anything else (DNS rebinding, stray names) is refused."""
        names = (*LOOPBACK_NAMES, *self.web.allowed_hosts)
        default = 443 if self.web.tls else 80
        return {f"{n}:{self.port}" for n in names} | ({*names} if self.port == default else set())

    @property
    def base_url(self) -> str:
        scheme = "https" if self.web.tls else "http"
        host = "127.0.0.1" if self.local_only or not self.web.allowed_hosts else self.web.allowed_hosts[0]
        return f"{scheme}://{host}:{self.port}"

    @property
    def setup_url(self) -> str | None:
        return f"{self.base_url}/setup?token={self.setup_token}" if self.setup_token else None

    def startup_message(self) -> str:
        if self.setup_token:
            return (f"First run: create the admin account at {self.setup_url} "
                    "(one-time link, keep it private)")
        warn = "" if self.local_only or self.web.allowed_hosts else \
            " Add the names people use to reach it to [web] allowed_hosts."
        return f"Maintainer dashboard: {self.base_url}/ (sign in with email and password).{warn}"

    def handle_error(self, request, client_address) -> None:
        # e.g. plain HTTP sent to the HTTPS port, or a client hanging up: log it, don't print a traceback
        log.info("dashboard: dropped a connection from %s", client_address[0], exc_info=True)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.serve_forever, name="devexai-web", daemon=True)
        thread.start()
        return thread


class _Handler(BaseHTTPRequestHandler):
    server: Dashboard
    server_version = "DevExAI"
    sys_version = ""

    def log_message(self, fmt, *args):  # never print request lines (they may hold the setup token)
        log.info("web %s %s -> %s", self.command, self.path.split("?")[0], args[1] if len(args) > 1 else "")

    # plumbing
    def _send(self, status: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        extra = {"Strict-Transport-Security": "max-age=31536000"} if self.server.web.tls else {}
        for key, value in {**_SECURITY_HEADERS, **extra, **(headers or {})}.items():
            self.send_header(key, value)
        if body:
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _redirect(self, where: str, headers: dict[str, str] | None = None) -> None:
        self._send(HTTPStatus.SEE_OTHER, headers={"Location": where, **(headers or {})})

    def _deny(self, status: int, why: str) -> None:
        self._send(status, pages.message_page("Not allowed", why))

    def _cookie(self, sid: str, max_age: int = SESSION_SECONDS) -> dict[str, str]:
        secure = "; Secure" if self.server.web.tls else ""
        return {"Set-Cookie": f"{COOKIE}={sid}; Max-Age={max_age}; HttpOnly; SameSite=Strict; Path=/{secure}"}

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "").lower() in self.server.origins

    def _sid(self) -> str:
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE:
                return value
        return ""

    def _session(self) -> tuple[Session, object] | None:
        """The signed-in session and its person, if they are still an active maintainer."""
        sid = self._sid()
        sess = self.server.sessions.get(sid) if sid else None
        person = self.server.bot.store.people.get(sess.user) if sess else None
        if sess and (person is None or not person.active):
            self.server.sessions.end(sid)
            return None
        return (sess, person) if sess else None

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        if not origin or origin == "null":
            return origin is None
        return urllib.parse.urlsplit(origin).netloc.lower() in self.server.origins

    def _form(self) -> dict[str, str] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length < 0 or length > MAX_BODY:
            return None
        raw = self.rfile.read(length).decode("utf-8", "replace")
        fields = urllib.parse.parse_qs(raw, keep_blank_values=True, max_num_fields=20)
        return {k: v[0] for k, v in fields.items()}

    def sign_in(self, user: str, flash: str = "", where: str = "/") -> None:
        """Start a fresh session (a new id, so a planted cookie is useless) and go to the ideas list."""
        sessions = self.server.sessions
        if old := self._sid():
            sessions.end(old)
        sid = sessions.create(user)
        if flash:
            sessions.flash(sessions.get(sid), flash)
        self._redirect(where, self._cookie(sid))

    # GET
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            self._get()
        except Exception:
            log.exception("dashboard GET %s failed", self.path.split("?")[0])
            self._send(500, pages.message_page("Error", "Something went wrong. The error is in the bot's log."))

    def _get(self) -> None:
        if not self._host_ok():
            return self._deny(HTTPStatus.MISDIRECTED_REQUEST, "Open the dashboard at its configured address.")
        url = urllib.parse.urlsplit(self.path)
        query = dict(urllib.parse.parse_qsl(url.query))
        bot = self.server.bot
        if url.path == "/setup":
            token = self.server.setup_token
            if not token:
                return self._redirect("/login")
            if not hmac.compare_digest(query.get("token", "").encode(), token.encode()):
                return self._deny(HTTPStatus.UNAUTHORIZED, "That setup link is wrong or from an earlier run.")
            admin = next(p for p in bot.store.people.list() if p.is_admin)
            return self._send(HTTPStatus.OK, people_pages.setup_page(token, admin.name, email=admin.email or ""))
        if url.path == "/login":
            return self._send(HTTPStatus.OK, people_pages.login_page())
        signed_in = self._session()
        if signed_in is None:
            return self._redirect("/login")
        sess, me = signed_in
        names = [m.name for m in bot.router.maintainers]
        flash = self.server.sessions.pop_flash(sess)

        if url.path == "/":
            view = query.get("view", "open")
            ideas = bot.store.ideas.list(1000)
            keep = {"open": lambda i: i.stage not in TERMINAL, "mine": lambda i: i.maintainer == me.name,
                    "waiting": lambda i: i.stage in WAITING_ON_MAINTAINER}.get(view, lambda i: True)
            body = pages.ideas_page([i for i in ideas if keep(i)], overdue=bot.router.overdue,
                                    user=me.name, view=view)
            title = "Ideas"
        elif url.path == "/maintainers":
            body = pages.maintainers_page(bot.router.maintainers, bot.store.ideas.list(100_000),
                                          overdue=bot.router.overdue)
            title = "Maintainers"
        elif url.path == "/projects":
            body, title = pages.projects_page(bot.store.projects.list(), csrf=sess.csrf), "Projects"
        elif url.path == "/account":
            body, title = people_pages.account_page(me, sess.csrf), "Account"
        elif url.path == "/people" and me.is_admin:
            body = people_pages.people_page(bot.store.people.list(include_inactive=True),
                                            bot.store.ideas.list(100_000), csrf=sess.csrf, me=me.name)
            title = "People"
        elif url.path == "/slack" and me.is_admin:
            body, title = slack_get(self, sess), "Slack"
        elif m := re.fullmatch(r"/idea/(\d+)", url.path):
            try:
                idea = bot.store.ideas.get(int(m.group(1)))
            except KeyError:
                return self._send(HTTPStatus.NOT_FOUND, pages.message_page("Not found", "No such idea."))
            audit = [{**a, "detail": unmention(a["detail"] or "", bot.store.meta)}
                     for a in bot.store.audit.for_idea(idea.id)]
            folder = bot.settings.builds_dir / str(idea.id)
            body = pages.idea_page(idea, audit, csrf=sess.csrf, maintainers=names, admin=me.is_admin,
                                   build_folder=str(folder.resolve()) if folder.is_dir() else "")
            title = f"#{idea.id}"
        else:
            return self._send(HTTPStatus.NOT_FOUND, pages.message_page("Not found", "No such page."))
        self._send(HTTPStatus.OK, pages.layout(title, body, user=me.name, is_admin=me.is_admin,
                                               csrf=sess.csrf, flash=flash, notices=self.server.notices))

    # POST
    def do_POST(self):
        try:
            self._post()
        except Exception:
            log.exception("dashboard POST %s failed", self.path)
            self._send(500, pages.message_page("Error", "Something went wrong. The error is in the bot's log."))

    def _post(self) -> None:
        if not self._host_ok():
            return self._deny(HTTPStatus.MISDIRECTED_REQUEST, "Open the dashboard at its configured address.")
        if not self._same_origin():
            return self._deny(HTTPStatus.FORBIDDEN, "Request came from another site.")
        path = urllib.parse.urlsplit(self.path).path
        form = self._form()
        if form is None:
            return self._deny(HTTPStatus.BAD_REQUEST, "The form was too large.")
        if path == "/login":
            return self._login(form)
        if path == "/setup":
            return setup_post(self, form)
        signed_in = self._session()
        if signed_in is None:
            return self._redirect("/login")
        sess, me = signed_in
        if not hmac.compare_digest(form.get("csrf", "").encode(), sess.csrf.encode()):
            return self._deny(HTTPStatus.FORBIDDEN, "The form expired. Go back, reload the page and try again.")
        if path == "/logout":
            self.server.sessions.end(self._sid())
            return self._redirect("/login", self._cookie("", 0))
        if path == "/account":
            return account_post(self, sess, me, form)
        if path == "/people" and me.is_admin:
            return people_post(self, sess, me, form)
        if path == "/slack" and me.is_admin:
            return slack_post(self, sess, me, form)
        if path == "/delete-idea" and me.is_admin:
            return self._delete_idea(sess, me, form)
        if path == "/action":
            return self._action(sess, form)
        if path == "/project":
            return self._project(sess, form)
        self._send(HTTPStatus.NOT_FOUND, pages.message_page("Not found", "No such action."))

    def _login(self, form: dict[str, str]) -> None:
        email, password = form.get("email", "").strip()[:254], form.get("password", "")[:200]
        who = self.client_address[0]
        if self.server.throttle.blocked(who, email.lower()):
            return self._send(HTTPStatus.TOO_MANY_REQUESTS,
                              people_pages.login_page("Too many wrong passwords. Wait 15 minutes.", email))
        person = self.server.bot.store.people.check_login(email, password)
        if person is None:
            self.server.throttle.failed(who, email.lower())
            log.warning("dashboard: failed sign-in from %s", who)
            return self._send(HTTPStatus.UNAUTHORIZED, people_pages.login_page("Wrong email or password.", email))
        self.server.throttle.succeeded(who, email.lower())
        self.server.bot.store.audit.add(None, person.name, "signed_in", who)
        self.sign_in(person.name)

    def run_command(self, sess: Session, text: str, idea_id: int | None) -> str:
        """Run a chat command as the signed-in maintainer; return what the bot said back to them."""
        bot = self.server.bot
        capture = _Capture(bot)
        bot.store.audit.add(idea_id, sess.user, "web", text[:500])
        try:
            commands.dispatch(capture, Event(sess.user, text, bot.settings.ideas_channel))
        except Exception:
            log.exception("dashboard command %r failed", text)
            capture.replies.append("Sorry, something went wrong. The error is in the bot's log.")
        return unmention("\n".join(capture.replies), bot.store.meta)

    def _action(self, sess: Session, form: dict[str, str]) -> None:
        action, idea = form.get("action", ""), form.get("idea", "")
        if action not in ACTIONS or not idea.isdigit():
            return self._deny(HTTPStatus.BAD_REQUEST, "Unknown action.")
        text = " ".join(form.get("text", "").split())  # one line, like a chat command
        said = self.run_command(sess, f"/devex-{action} {idea} {text}".rstrip(), int(idea))
        self.server.sessions.flash(sess, said or f"Done: {action} #{idea}.")
        self._redirect(f"/idea/{idea}")

    def _delete_idea(self, sess: Session, me, form: dict[str, str]) -> None:
        bot = self.server.bot
        try:
            idea = bot.store.ideas.get(int(form.get("idea", "")))
            with self.server.chat_lock:
                said = bot.delete_idea(idea, me.name)
        except (KeyError, ValueError) as e:
            self.server.sessions.flash(sess, str(e).strip("'") or "No such idea.")
            return self._redirect(f"/idea/{form.get('idea', '')}" if form.get("idea", "").isdigit() else "/")
        self.server.sessions.flash(sess, said)
        self._redirect("/")

    def _project(self, sess: Session, form: dict[str, str]) -> None:
        op, name = form.get("op", ""), form.get("name", "").strip()
        summary = " ".join(form.get("summary", "").split())
        if op not in ("set", "remove") or not re.fullmatch(r"\S{1,80}", name):
            return self._deny(HTTPStatus.BAD_REQUEST, "Give a one-word project name.")
        said = self.run_command(sess, f"/devex-projects {op} {name} {summary}".rstrip(), None)
        self.server.sessions.flash(sess, said)
        self._redirect("/projects")
