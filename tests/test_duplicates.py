import test_flow
from test_flow import gate, say

from devexai.stages import Stage

make_bot = test_flow.make_bot  # the fixture


def by_id(bot, idea_id):
    return bot.store.ideas.get(idea_id)


def test_exact_repost_makes_no_new_idea(make_bot):
    bot = make_bot()
    say(bot, "carol", "Run ktlint before commit")
    say(bot, "dave", "  run KTLINT before commit! ")
    assert len(bot.store.ideas.list()) == 1
    assert any("same as idea #1" in t for t in bot.chat.texts())
    assert sum(c.role == "gate" for c in bot.llm.calls) == 1  # no AI spent on the repost


def test_repost_after_a_stop_is_a_new_idea(make_bot):
    bot = make_bot()
    say(bot, "carol", "Run ktlint before commit")
    say(bot, "carol", "/devex-stop 1 not now")
    say(bot, "carol", "Run ktlint before commit")
    assert len(bot.store.ideas.list()) == 2


def test_gate_puts_a_same_tool_idea_on_hold(make_bot):
    bot = make_bot(gate_reply=lambda system, prompt: gate() | {"duplicate_of": 1 if "#1" in prompt else 0})
    say(bot, "carol", "Run ktlint before commit")
    say(bot, "dave", "A pre-commit hook that lints Kotlin")
    first, second = by_id(bot, 1), by_id(bot, 2)
    assert first.stage is Stage.PLAN_READY and second.stage is Stage.POSSIBLE_DUPLICATE
    assert sum(c.role == "planner" for c in bot.llm.calls) == 1  # no plan for the duplicate
    say(bot, "alice", "/devex-approve 2")  # not a duplicate after all
    assert by_id(bot, 2).stage is Stage.PLAN_READY


def test_closing_a_duplicate_stops_it(make_bot):
    bot = make_bot(gate_reply=lambda system, prompt: gate() | {"duplicate_of": 1 if "#1" in prompt else 0})
    say(bot, "carol", "Run ktlint before commit")
    say(bot, "dave", "A pre-commit hook that lints Kotlin")
    say(bot, "alice", "/devex-deny 2 duplicate of #1")
    assert by_id(bot, 2).stage is Stage.STOPPED and by_id(bot, 2).stop_reason == "duplicate of #1"


def test_safety_beats_duplicate_and_unknown_numbers_are_ignored(make_bot):
    bot = make_bot(gate_reply=lambda system, prompt: gate("reject" if "#1" in prompt else "pass")
                   | {"duplicate_of": 1 if "#1" in prompt else 99})
    say(bot, "carol", "Run ktlint before commit")
    assert by_id(bot, 1).stage is Stage.PLAN_READY  # 99 is not an earlier idea
    say(bot, "dave", "A pre-commit hook that lints Kotlin")
    assert by_id(bot, 2).stage is Stage.REJECTED


def test_gate_compares_only_with_older_ideas_that_passed(make_bot):
    bot = make_bot(gate_reply=lambda system, prompt: gate("reject" if "malware" in prompt else "pass"))
    say(bot, "carol", "write malware")
    say(bot, "dave", "Run ktlint before commit")
    last_gate = [c for c in bot.llm.calls if c.role == "gate"][-1]
    assert "malware" not in last_gate.prompt  # a rejected idea never reaches the prompt
