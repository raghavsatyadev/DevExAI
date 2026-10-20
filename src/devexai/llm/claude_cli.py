"""Provider that runs `claude -p` with every tool disabled and a JSON schema for the answer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any

from ..config import LLMSettings
from .base import LLMError

# Bot secrets the model process never needs. ANTHROPIC_API_KEY is dropped so the CLI uses
# its logged-in account instead of silently billing an API key.
_STRIP_ENV_PREFIXES = ("SLACK_", "DEVEXAI_")
_STRIP_ENV_NAMES = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"}


def _child_env() -> dict[str, str]:
    return {
        k: v for k, v in os.environ.items()
        if k.upper() not in _STRIP_ENV_NAMES and not k.upper().startswith(_STRIP_ENV_PREFIXES)
    }


def _tail(text: str, n: int = 800) -> str:
    text = (text or "").strip()
    return text[-n:]


class ClaudeCLI:
    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def _binary(self) -> str:
        path = shutil.which(self.settings.claude_bin)
        if not path:
            raise LLMError(f"claude CLI not found: {self.settings.claude_bin!r} (set [llm] claude_bin)")
        return path

    def complete(self, role: str, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        args = [
            self._binary(), "-p",
            "--model", self.settings.model_for(role),
            "--tools", "",
            "--output-format", "json",
            "--no-session-persistence",
            "--setting-sources", "",
            "--json-schema", json.dumps(schema, separators=(",", ":")),
            "--system-prompt", system,
        ]
        with tempfile.TemporaryDirectory(prefix="devexai-llm-") as cwd:
            try:
                proc = subprocess.run(
                    args, input=prompt, capture_output=True, cwd=cwd, env=_child_env(),
                    encoding="utf-8", errors="replace", timeout=self.settings.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                raise LLMError(f"{role}: claude timed out after {self.settings.timeout_seconds}s") from None
            except OSError as e:
                raise LLMError(f"{role}: could not run claude: {e}") from None
        if proc.returncode != 0:
            raise LLMError(f"{role}: claude exited {proc.returncode}: {_tail(proc.stderr or proc.stdout)}")
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise LLMError(f"{role}: claude returned non-JSON: {_tail(proc.stdout)}") from None
        if envelope.get("is_error"):
            raise LLMError(f"{role}: claude reported an error: {_tail(str(envelope.get('result')))}")
        result = envelope.get("structured_output")
        if not isinstance(result, dict):
            raise LLMError(f"{role}: no structured_output in claude reply: {_tail(proc.stdout)}")
        return result
