from pathlib import Path

from ..config import LLMSettings
from .base import LLMError, LLMProvider


def make_provider(settings: LLMSettings) -> LLMProvider:
    if settings.provider == "replay":
        from .replay import ReplayLLM

        return ReplayLLM(Path(settings.recordings or "data/llm-replies"))
    if settings.provider == "claude_cli":
        from .claude_cli import ClaudeCLI

        if settings.recordings:
            from .replay import Recorder

            return Recorder(ClaudeCLI(settings), Path(settings.recordings))
        return ClaudeCLI(settings)
    if settings.provider == "stub":
        from .stub import StubLLM

        return StubLLM()
    raise ValueError(f"unknown [llm] provider {settings.provider!r}")


__all__ = ["LLMError", "LLMProvider", "make_provider"]
