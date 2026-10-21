"""Record real AI replies once, then replay them: test the whole flow without spending tokens."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import LLMError, LLMProvider


def _fit(reply: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields the role's schema asks for (a stored gate record also has fetched pages)."""
    props = schema.get("properties")
    return {k: v for k, v in reply.items() if k in props} if props else dict(reply)


@dataclass
class ReplayLLM:
    """Answers each role with `<dir>/<role>.json`, whatever the idea says."""

    dir: Path

    def complete(self, role: str, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        path = self.dir / f"{role}.json"
        try:
            reply = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise LLMError(f"{role}: no recorded reply in {path} ({e})") from None
        return _fit(reply, schema)


@dataclass
class Recorder:
    """Passes calls through and saves each role's latest reply for ReplayLLM."""

    inner: LLMProvider
    dir: Path

    def complete(self, role: str, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        reply = self.inner.complete(role, system, prompt, schema)
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f"{role}.json.tmp"
        tmp.write_text(json.dumps(reply, indent=2), encoding="utf-8")
        os.replace(tmp, self.dir / f"{role}.json")
        return reply
