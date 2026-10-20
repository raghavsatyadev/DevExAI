"""Wires settings, store, chat adapter and AI provider into a running bot."""

from __future__ import annotations

import logging
import re
import shutil
import threading
import webbrowser
from pathlib import Path

from .chat import ChatAdapter
from .config import Settings, load_dotenv, load_settings
from .flow.bot import Bot
from .llm import make_provider
from .store import Store
from .update import start_checks

TICK_SECONDS = 300


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
    raise ValueError(f"unknown [chat] adapter {settings.chat_adapter!r}")


def startup_notices(settings: Settings) -> list[str]:
    if settings.llm.provider == "claude_cli" and not shutil.which(settings.llm.claude_bin):
        return [f"The claude CLI ({settings.llm.claude_bin}) was not found on this server, so ideas cannot be "
                "checked or planned. Install Claude Code, sign it in, and restart DevExAI."]
    return []


def run(settings_path: Path, env_path: Path = Path(".env"), *, adapter: str | None = None,
        open_browser: bool = False) -> None:
    load_dotenv(env_path)
    settings = load_settings(settings_path)
    log_path = settings.db_path.with_suffix(".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    store = Store(settings.db_path)
    store.people.seed(settings.maintainers)
    chat = make_chat(settings, store, adapter)
    bot = Bot(settings, store, chat, make_provider(settings.llm))
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
    notices = startup_notices(settings)
    for note in notices:
        logging.warning(note)
        print(f"Warning: {note}", flush=True)
    web = None
    if settings.web.enabled:
        from .web import Dashboard

        try:
            web = Dashboard(bot, settings.web)
        except (OSError, ValueError) as e:  # port taken, bad TLS files...: the bot still works from chat
            logging.error("dashboard not started: %s", e)
            print(f"Maintainer dashboard not started: {e}", flush=True)
        else:
            web.notices.extend(notices)
            web.start()
            print(web.startup_message(), flush=True)
            if open_browser and web.setup_url:  # first run: go straight to creating the admin account
                webbrowser.open(web.setup_url)

    def update_ready(text: str) -> None:
        print(text, flush=True)
        if web and text not in web.notices:
            web.notices.append(text)

    start_checks(settings.update, stop, update_ready)
    try:
        chat.run(bot.handle)
    finally:
        stop.set()
        if web:
            web.shutdown()
            web.server_close()
        bot.pipeline.stop()
