import pytest
from test_flow import FREE_LIB, gate, only_idea, plan, say

from devexai.builder import files as tool_files
from devexai.chat.fake import FakeChat
from devexai.config import BlogSettings, Maintainer, Settings
from devexai.flow import post
from devexai.flow.bot import Bot
from devexai.llm import LLMError
from devexai.llm.replay import ReplayLLM
from devexai.llm.samples import SAMPLES
from devexai.llm.stub import StubLLM
from devexai.stages import Stage
from devexai.store import Store
from devexai.web.pages import idea_page

BUILT = {"files": [{"path": "SKILL.md", "content": "Run ktlint <b>now</b>"},
                   {"path": "tests/test_skill.py", "content": "def test_x():\n    assert True\n"},
                   {"path": "README.md", "content": "# Lint skill"}],
         "summary": "A ktlint skill.", "install": "copy SKILL.md", "test_command": "pytest"}
OK = {"verdict": "ok", "safe": True, "safety_issues": [], "findings": []}
UNSAFE = {"verdict": "ok", "safe": True, "safety_issues": ["sends the repo to a web server"], "findings": []}


@pytest.fixture
def make_bot(tmp_path):
    def factory(builder=None, reviewer=None):
        settings = Settings(maintainers=(Maintainer("alice", ("android",)),),
                            blog=BlogSettings(dir=tmp_path / "blog", base_url="https://blog.example/posts/"),
                            db_path=tmp_path / "devexai.db")
        llm = StubLLM({"gate": gate(), "planner": plan([FREE_LIB]), "builder": builder or BUILT,
                       "reviewer": reviewer or OK})
        return Bot(settings, Store(":memory:"), FakeChat(), llm, inline_jobs=True)
    return factory


def approved(bot):
    say(bot, "carol", "Run ktlint before commit")
    idea = only_idea(bot)
    say(bot, "alice", "/devex-approve", thread=idea.thread_ref)
    return only_idea(bot)


def test_approval_builds_reviews_and_publishes(make_bot, tmp_path):
    bot = make_bot()
    idea = approved(bot)
    assert idea.stage is Stage.UNDER_REVIEW and not idea.build["pending"]
    folder = tmp_path / "builds" / str(idea.id)
    assert (folder / "SKILL.md").read_text(encoding="utf-8") == "Run ktlint <b>now</b>"
    assert (folder / "tests" / "test_skill.py").exists()
    last = bot.chat.in_thread(idea.thread_ref)[-1]
    assert "SKILL.md" in last and "not run" in last and "Run ktlint" not in last  # files stay off chat
    say(bot, "alice", f"/devex-built {idea.id}")  # it is already in review
    say(bot, "alice", f"/devex-publish {idea.id}")
    idea = only_idea(bot)
    assert idea.stage is Stage.PUBLISHED
    text = next((tmp_path / "blog").glob("*.md")).read_text(encoding="utf-8")
    assert "## Files" in text and "- SKILL.md" in text and "copy SKILL.md" in text


def test_untrusted_text_stays_out_of_system_prompts(make_bot):
    bot = make_bot()
    approved(bot)
    calls = [c for c in bot.llm.calls if c.role in ("builder", "reviewer")]
    assert {c.role for c in calls} == {"builder", "reviewer"}
    for c in calls:
        assert "Run ktlint before commit" in c.prompt and "Run ktlint before commit" not in c.system
    assert "Run ktlint <b>now</b>" in calls[-1].prompt  # the reviewer sees the files


def test_reviewer_changes_get_one_fix_round(make_bot):
    reviews = iter([{**OK, "verdict": "changes", "findings": ["add a test for errors"]}, OK])
    bot = make_bot(reviewer=lambda s, p: next(reviews))
    idea = approved(bot)
    builds = [c for c in bot.llm.calls if c.role == "builder"]
    assert len(builds) == 2 and "add a test for errors" in builds[1].prompt
    assert idea.stage is Stage.UNDER_REVIEW and idea.build["rounds"] == 2


def test_listed_safety_issue_keeps_it_in_building(make_bot):
    bot = make_bot(reviewer=UNSAFE)
    idea = approved(bot)
    assert idea.stage is Stage.BUILDING and idea.build["review"]["safe"] is False
    assert "sends the repo to a web server" in bot.chat.in_thread(idea.thread_ref)[-1]
    say(bot, "alice", f"/devex-built {idea.id} checked by hand")  # a person can still send it on
    assert only_idea(bot).stage is Stage.UNDER_REVIEW


def test_builder_failure_keeps_it_in_building(make_bot, tmp_path):
    bot = make_bot(builder=LLMError("model down"))
    idea = approved(bot)
    assert idea.stage is Stage.BUILDING and "model down" in idea.build["error"]
    assert "could not build it" in bot.chat.in_thread(idea.thread_ref)[-1]
    assert not (tmp_path / "builds").exists()


def test_unsafe_file_name_is_refused(make_bot, tmp_path):
    bot = make_bot(builder={**BUILT, "files": [{"path": "../evil.py", "content": "x"}]})
    idea = approved(bot)
    assert idea.stage is Stage.BUILDING and "error" in idea.build
    assert not (tmp_path / "evil.py").exists()


def test_send_back_rebuilds_with_the_changes(make_bot, tmp_path):
    seen = []

    def builder(system, prompt):
        seen.append(prompt)
        files = BUILT["files"] if len(seen) == 1 else [{"path": "SKILL.md", "content": "v2"}]
        return {**BUILT, "files": files}
    bot = make_bot(builder=builder)
    idea = approved(bot)
    say(bot, "alice", f"/devex-deny {idea.id} use the gradle plugin")
    idea = only_idea(bot)
    assert idea.stage is Stage.UNDER_REVIEW and len(seen) == 2
    assert "use the gradle plugin" in seen[1] and "Run ktlint <b>now</b>" in seen[1]  # previous files sent
    folder = tmp_path / "builds" / str(idea.id)
    assert sorted(p.name for p in folder.rglob("*")) == ["SKILL.md"]  # stale files are gone


def test_busy_build_blocks_built_and_delete(make_bot):
    bot = make_bot()
    say(bot, "carol", "Run ktlint before commit")
    idea = only_idea(bot)
    bot.pipeline.submit = lambda job: None  # the build job never runs
    say(bot, "alice", "/devex-approve", thread=idea.thread_ref)
    idea = only_idea(bot)
    assert idea.stage is Stage.BUILDING and idea.build["pending"]
    say(bot, "alice", f"/devex-built {idea.id}")
    assert only_idea(bot).stage is Stage.BUILDING
    with pytest.raises(ValueError):
        bot.delete_idea(idea, "alice")
    queued = []
    bot.pipeline.submit = queued.append
    bot.resume()
    assert [j.idea_id for j in queued] == [idea.id]


def test_delete_removes_the_files(make_bot, tmp_path):
    bot = make_bot()
    idea = approved(bot)
    bot.delete_idea(idea, "alice")
    assert not (tmp_path / "builds" / str(idea.id)).exists()


def test_page_shows_files_escaped(make_bot):
    bot = make_bot()
    idea = approved(bot)
    html = idea_page(idea, [], csrf="x", maintainers=["alice"], build_folder="C:/b/1")
    assert "Run ktlint &lt;b&gt;now&lt;/b&gt;" in html and "<b>now</b>" not in html
    assert "not run" in html and "C:/b/1" in html


def test_post_lists_files(make_bot):
    bot = make_bot(builder={**BUILT, "files": [{"path": "a_b-c.md", "content": ""}]})
    idea = approved(bot)
    assert "- a\\_b-c.md" in post.render(idea, maintainer="alice")


@pytest.mark.parametrize("path", ["../x", "/abs", "C:/x", "a/../b", "CON", "nul.txt", "a\\..\\b", "x.", "", "a//b"])
def test_bad_paths(path):
    with pytest.raises(tool_files.BadFiles):
        tool_files.clean([{"path": path, "content": ""}])


def test_case_clash_size_and_file_folder_clash():
    for files in ([{"path": "A.md", "content": ""}, {"path": "a.md", "content": ""}],
                  [{"path": "a", "content": ""}, {"path": "a/b", "content": ""}],
                  [{"path": "big", "content": "x" * (tool_files.MAX_FILE_BYTES + 1)}],
                  []):
        with pytest.raises(tool_files.BadFiles):
            tool_files.clean(files)


def test_replay_falls_back_to_samples(tmp_path):
    from devexai.builder.build import BUILD_SCHEMA, REVIEW_SCHEMA
    llm = ReplayLLM(tmp_path)
    assert llm.complete("builder", "", "", BUILD_SCHEMA) == SAMPLES["builder"]
    assert llm.complete("reviewer", "", "", REVIEW_SCHEMA) == SAMPLES["reviewer"]
    tool_files.clean(SAMPLES["builder"]["files"])  # the sample passes the name checks
    with pytest.raises(LLMError):
        llm.complete("gate", "", "", {})
