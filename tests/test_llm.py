import pytest

from devexai.config import LLMSettings
from devexai.llm import LLMError, make_provider
from devexai.llm import claude_cli
from devexai.llm.stub import StubLLM


def test_stub_records_calls_and_raises():
    llm = StubLLM({"gate": {"verdict": "pass"}, "planner": LLMError("boom")})
    assert llm.complete("gate", "sys", "data", {}) == {"verdict": "pass"}
    assert llm.calls[0].prompt == "data"
    with pytest.raises(LLMError):
        llm.complete("planner", "s", "p", {})
    with pytest.raises(LLMError):
        llm.complete("other", "s", "p", {})


def test_child_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("KEEP_ME", "1")
    env = claude_cli._child_env()
    assert "SLACK_BOT_TOKEN" not in env and "ANTHROPIC_API_KEY" not in env and env["KEEP_ME"] == "1"


def test_missing_binary_is_llm_error():
    cli = make_provider(LLMSettings(claude_bin="definitely-not-a-real-binary-xyz"))
    with pytest.raises(LLMError, match="not found"):
        cli.complete("gate", "s", "p", {})


def test_unknown_provider():
    with pytest.raises(ValueError):
        make_provider(LLMSettings(provider="nope"))
