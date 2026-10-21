"""Wires settings, store, chat adapter and AI provider into a running bot."""

from __future__ import annotations

import logging
import os
import re
import shutil
import threading
import webbrowser
from dataclasses import replace
from pathlib import Path

from .chat import ChatAdapter
from .config import Settings, load_dotenv, load_settings
from .flow.bot import Bot
from .llm import make_provider
from .store import Meta, Store
from .update import start_checks

TICK_SECONDS = 300
# settings the admin changes in the dashboard; they win over settings.toml
OVERRIDES = {"chat_adapter": "cfg:chat_adapter", "ideas_channel": "cfg:ideas_channel",
             "public_channel": "cfg:public_channel"}


def with_overrides(settings: Settings, meta: Meta) -> Settings:
    return replace(settings, **{field: v for field, key in OVERRIDES.items() if (v := meta.get(key))})


def slack_tokens() -> tuple[str, str]:
    return os.environ.get("SLACK_BOT_TOKEN", "").strip(), os.environ.get("SLACK_APP_TOKEN", "").strip()


def switch_chat(bot: Bot, new: ChatAdapter) -> None:
    """Connect the new platform first, then retire the old one; the main loop then runs the new one."""
    if hasattr(new, "start"):
        new.start(bot.handle)
    old, bot.chat = bot.chat, new
    if hasattr(old, "stop"):
        old.stop()


def make_chat(settings: Settings, store: Store, adapter: str | None = None) -> ChatAdapter:
    adapter = adapter or settings.chat_adapter
    used = [int(m.group(1)) for i in store.ideas.list(100_000)
            if i.thread_ref and (m := re.fullmatch(r"t(\d+)", i.thread_ref))]
    if adapter == "console":
        from .chat.console import ConsoleChat

        return ConsoleChat(settings.ideas_channel, user=(store.people.list() or settings.maintainers)[0].name,
                           first_ref=max(used, default=0) + 1)
    if adapter == "none":
        from .chat.headless import HeadlessChat

        return HeadlessChat(first_ref=max(used, default=0) + 1)
    if adapter == "slack":
        from .chat.slack import SlackChat

        bot_token, app_token = slack_tokens()
        if not bot_token or not app_token:
            raise ValueError("Slack needs SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env (see the Slack page)")
        return SlackChat(bot_token, app_token, store)
    raise ValueError(f"unknown [chat] adapter {settings.chat_adapter!r}")


def startup_notices(settings: Settings) -> list[str]:
    if settings.llm.provider == "claude_cli" and not shutil.which(settings.llm.claude_bin):
        return [f"The claude CLI ({settings.llm.claude_bin}) was not found on this server, so ideas cannot be "
                "checked or planned. Install Claude Code, sign it in, and restart DevExAI."]
    return []


def start_tray(bot: Bot, web, log_path: Path):
    """The notification-area icon of the windowed build: open the dashboard, the data or the log, quit."""
    from . import home, tray

    def open_dashboard() -> None:
        if web:
            webbrowser.open(web.setup_url or f"{web.base_url}/")
        else:
            os.startfile(Path.cwd())

    menu = [("Open dashboard", open_dashboard),
            ("Open data folder", lambda: os.startfile(Path.cwd())),
            ("Open log", lambda: os.startfile(log_path.resolve())),
            None,
            ("Quit DevExAI", lambda: bot.chat.stop())]  # ends the main loop in run()
    return tray.create("DevExAI", menu, open_dashboard, home.bundled("assets/logo/devexai.ico"))


def run(settings_path: Path, env_path: Path = Path(".env"), *, adapter: str | None = None,
        open_browser: bool = False, replay: bool = False, tray: bool = False) -> None:
    """Run until the chat platform stops (Ctrl+C, or Quit in the tray icon's menu).

    With tray, there is no console: the console chat is replaced by none, and messages that would be
    printed are shown as notifications next to the icon.
    """
    load_dotenv(env_path)
    settings = load_settings(settings_path)
    if replay:
        settings = replace(settings, llm=replace(settings.llm, provider="replay",
                                                 recordings=settings.llm.recordings or "llm-replies"))
    log_path = settings.db_path.with_suffix(".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    store = Store(settings.db_path)
    store.people.seed(settings.maintainers)
    settings = with_overrides(settings, store.meta)
    if tray and (adapter or settings.chat_adapter) == "console":
        adapter = "none"  # nobody can type into a console that is not there
    notices = startup_notices(settings)
    bot = Bot(settings, store, make_chat(settings, store, "none"), make_provider(settings.llm))
    try:
        switch_chat(bot, make_chat(settings, store, adapter))
    except Exception as e:  # bad tokens, Slack down: keep the dashboard up so the admin can fix it
        logging.exception("chat platform not started")
        notices.append(f"Chat not connected: {e}. Fix it on the Slack page in the dashboard.")
    bot.pipeline.start()
    bot.resume()

    stop = threading.Event()

    def ticker() -> None:
        while not stop.wait(TICK_SECONDS):
            try:
                bot.tick()
            except Exception:
                logging.exception("tick failed")

    threading.Thread(target=ticker, name="devexai-tick", daemon=True).start()
    for note in notices:
        logging.warning(note)
        print(f"Warning: {note}", flush=True)
    web = None
    if settings.web.enabled:
        from .web import Dashboard

        try:
            web = Dashboard(bot, settings.web, env_path)
        except (OSError, ValueError) as e:  # port taken, bad TLS files...: the bot still works from chat
            logging.error("dashboard not started: %s", e)
            print(f"Maintainer dashboard not started: {e}", flush=True)
        else:
            web.notices.extend(notices)
            web.start()
            print(web.startup_message(), flush=True)
            if open_browser and web.setup_url:  # first run: go straight to creating the admin account
                webbrowser.open(web.setup_url)
    icon = start_tray(bot, web, log_path) if tray else None
    if icon:
        if notices:  # Windows shows one notification at a time, so the warnings go first and together
            icon.notify("DevExAI needs attention", " ".join(notices), warning=True)
        else:
            icon.notify("DevExAI is running", web.startup_message() if web else "The dashboard is off.")

    def update_ready(text: str) -> None:
        print(text, flush=True)
        if icon:
            icon.notify("DevExAI update", text)
        if web and text not in web.notices:
            web.notices.append(text)

    start_checks(settings.update, stop, update_ready)
    try:
        while True:  # the dashboard can switch platforms (e.g. console -> Slack) while we run
            current = bot.chat
            current.run(bot.handle)
            if bot.chat is current:
                break
    finally:
        stop.set()
        if icon:
            icon.close()
        if hasattr(bot.chat, "stop"):  # e.g. close the Slack socket so its threads do not hold the exit
            bot.chat.stop()
        if web:
            web.shutdown()
            web.server_close()
        bot.pipeline.stop()
