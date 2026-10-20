"""Chat platform plug-in point (README section 9). Every adapter maps its platform onto these."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class Button:
    label: str
    command: str  # text command sent back as if the clicking user typed it


@dataclass(frozen=True)
class Event:
    """Something a person said to the bot."""

    user: str
    text: str
    channel: str
    thread: str | None = None  # thread ref when the message is a reply inside a thread
    is_dm: bool = False


Handler = Callable[[Event], None]


class ChatAdapter(Protocol):
    def post(
        self, channel: str, text: str, *, thread: str | None = None, buttons: tuple[Button, ...] = ()
    ) -> str:
        """Post a message. Returns a thread ref usable for later replies.

        Platforms without buttons should render them as text hints of the command.
        """

    def mention(self, user: str) -> str:
        """How to @-mention a user on this platform."""

    def run(self, handler: Handler) -> None:
        """Block, delivering incoming events to handler until stopped."""
