"""Scripted provider for tests: no network, no keys."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .base import LLMError

Reply = dict[str, Any] | Callable[[str, str], dict[str, Any]] | LLMError


@dataclass(frozen=True)
class Call:
    role: str
    system: str
    prompt: str
    schema: dict[str, Any]


@dataclass
class StubLLM:
    """`replies[role]` is a dict, a callable(system, prompt) -> dict, or an LLMError to raise."""

    replies: dict[str, Reply] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)

    def complete(self, role: str, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(Call(role, system, prompt, schema))
        reply = self.replies.get(role)
        if reply is None:
            raise LLMError(f"stub has no reply for role {role!r}")
        if isinstance(reply, LLMError):
            raise reply
        return dict(reply(system, prompt) if callable(reply) else reply)
