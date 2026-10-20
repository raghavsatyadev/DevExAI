"""AI provider plug-in point (README section 9).

Contract every caller relies on: `system` holds only our own instructions; untrusted text
(the idea, linked pages) goes only in `prompt`, quoted as data.
"""

from __future__ import annotations

from typing import Any, Protocol


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    def complete(self, role: str, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Run one model call for `role` and return JSON matching `schema`. Raises LLMError."""
