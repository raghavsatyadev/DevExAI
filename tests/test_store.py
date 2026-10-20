import pytest

from devexai.stages import InvalidTransition, Stage
from devexai.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


def test_move_follows_state_machine(store):
    idea = store.ideas.create("carol", "an idea", "#ai-ideas")
    assert idea.stage is Stage.RECEIVED
    store.ideas.move(idea.id, Stage.SAFETY_CHECK)
    with pytest.raises(InvalidTransition):
        store.ideas.move(idea.id, Stage.PUBLISHED)
    with pytest.raises(InvalidTransition):
        store.ideas.move(idea.id, Stage.RESEARCHING, expect=Stage.RECEIVED)


def test_waiting_since_set_only_while_waiting(store):
    idea = store.ideas.create("carol", "x", "#ai-ideas")
    for dst in (Stage.SAFETY_CHECK, Stage.SAFETY_UNSURE):
        idea = store.ideas.move(idea.id, dst)
    assert idea.waiting_since and store.ideas.waiting_on_maintainer()[0].id == idea.id
    idea = store.ideas.move(idea.id, Stage.RESEARCHING)
    assert idea.waiting_since is None


def test_terminal_stages_cannot_stop(store):
    idea = store.ideas.create("carol", "x", "#ai-ideas")
    store.ideas.move(idea.id, Stage.STOPPED)
    with pytest.raises(InvalidTransition):
        store.ideas.move(idea.id, Stage.STOPPED)


def test_update_json_fields_and_thread_lookup(store):
    idea = store.ideas.create("carol", "x", "#ai-ideas")
    store.ideas.update(idea.id, thread_ref="t9", plan={"steps": [1]}, title="Tool")
    found = store.ideas.find_by_thread("t9")
    assert found.plan == {"steps": [1]} and found.label == f"#{idea.id} Tool"
    with pytest.raises(ValueError):
        store.ideas.update(idea.id, stage="published")


def test_projects_crud(store):
    assert store.projects.upsert("app", "Kotlin app", "alice") is True
    assert store.projects.upsert("app", "Kotlin + Compose", "bob") is False
    assert store.projects.get("app").summary == "Kotlin + Compose"
    assert store.projects.remove("app") and not store.projects.remove("app")


def test_people_seed_once_and_check_passwords():
    from devexai.config import Maintainer
    from devexai.store.people import PeopleError

    store = Store(":memory:")
    store.people.seed((Maintainer("raghav", ("ai",)), Maintainer("priya", ("android",), "Priya@Example.com")))
    store.people.seed((Maintainer("someone-else"),))  # second start: settings no longer matter
    assert [p.name for p in store.people.list()] == ["raghav", "priya"]
    assert store.people.get("raghav").is_admin and store.people.get("priya").email == "priya@example.com"
    assert not store.people.anyone_can_sign_in()
    with pytest.raises(PeopleError):
        store.people.set_password("raghav", "long enough pw")  # no email yet
    store.people.update("raghav", email="raghav@example.com")
    store.people.set_password("raghav", "long enough pw")
    assert store.people.anyone_can_sign_in()
    assert store.people.check_login("RAGHAV@example.com", "long enough pw").name == "raghav"
    assert store.people.check_login("raghav@example.com", "wrong") is None
    assert store.people.check_login("nobody@example.com", "long enough pw") is None
    with pytest.raises(PeopleError, match="already used"):
        store.people.update("priya", email="raghav@example.com")


def test_live_column_is_added_to_an_old_database(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as c:  # an ideas table from before the live column existed
        c.execute("CREATE TABLE ideas (id INTEGER PRIMARY KEY AUTOINCREMENT, poster TEXT NOT NULL, text TEXT NOT NULL,"
                  " channel TEXT NOT NULL, thread_ref TEXT, stage TEXT NOT NULL, maintainer TEXT, topic TEXT,"
                  " title TEXT, gate_json TEXT, plan_json TEXT, blog_url TEXT, stop_reason TEXT, waiting_since TEXT,"
                  " created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    store = Store(path)
    idea = store.ideas.create("carol", "x", "#ai-ideas")
    assert store.ideas.update(idea.id, live="yes").live == "yes"
