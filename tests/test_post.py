import pytest

from devexai.flow import post
from devexai.stages import Stage
from devexai.store import Idea

EVIL = "../../x <script>alert(1)</script> [click](javascript:a) https://evil.example"


def idea(title=EVIL, idea_id=7, summary=EVIL):
    return Idea(id=idea_id, poster="carol", text="", channel="#ai-ideas", thread_ref=None,
                stage=Stage.UNDER_REVIEW, maintainer="alice", topic="android", title=title, gate=None,
                plan={"summary": summary, "assistants": ["Claude Code"], "deliverables": ["- SKILL.md"]},
                blog_url=None, live=None, stop_reason=None, waiting_since=None, created_at="", updated_at="")


def test_filename_is_safe():
    assert post.filename(idea()) == "0007-x-script-alert-1-script-click-javascript-a-https-evil-exampl.md"
    assert post.filename(idea(title="")) == "0007-tool.md"
    assert post.filename(idea(title="Lint skill")) == "0007-lint-skill.md"


def test_content_is_escaped():
    text = post.render(idea(), maintainer="alice", note="`rm -rf /` <b>", today="2026-10-20")
    body = text.split("---", 2)[2]
    assert "<script>" not in text and "<b>" not in text
    assert r"\[click\](javascript:a)" in body and r"https\://evil.example" in body
    assert r"\- SKILL.md" in body and r"\`rm -rf /\`" in body
    assert 'title: "../../x  script alert(1) /script  [click](javascript:a) https://evil.example"' in text
    assert "**Idea by @carol.**" in body


def test_write_never_overwrites_and_stays_in_folder(tmp_path):
    path = post.write(idea(), tmp_path, maintainer="alice")
    assert path.parent == tmp_path.resolve() and path.read_text(encoding="utf-8").startswith("---\n")
    with pytest.raises(post.PostExists):
        post.write(idea(summary="other"), tmp_path, maintainer="alice")
    assert "other" not in path.read_text(encoding="utf-8")
    assert post.write(idea(idea_id=8), tmp_path, maintainer="alice") != path
