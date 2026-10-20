from .db import Database
from .people import PeopleRepo, Person
from .repos import AuditLog, Idea, IdeaRepo, Meta, Project, ProjectRepo


class Store:
    """All persistence behind one object."""

    def __init__(self, path):
        self.db = Database(path)
        self.ideas = IdeaRepo(self.db)
        self.audit = AuditLog(self.db)
        self.projects = ProjectRepo(self.db)
        self.meta = Meta(self.db)
        self.people = PeopleRepo(self.db)


__all__ = ["AuditLog", "Database", "Idea", "IdeaRepo", "Meta", "PeopleRepo", "Person", "Project", "ProjectRepo", "Store"]
