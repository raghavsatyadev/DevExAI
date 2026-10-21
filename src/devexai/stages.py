"""Idea stages (README section 5) and the transitions allowed between them."""

from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    RECEIVED = "received"
    SAFETY_CHECK = "safety_check"
    SAFETY_UNSURE = "safety_unsure"          # maintainer must decide (Step 1 "Unsure")
    POSSIBLE_DUPLICATE = "possible_duplicate"  # the gate thinks an earlier idea asks for the same tool
    RESEARCHING = "researching"              # research + planning (Steps 2-3)
    PLAN_READY = "plan_ready"
    WAITING_APPROVAL = "waiting_approval"    # escalation-lane resources (Step 4)
    BUILDING = "building"                    # Phase 1: a human builds it
    UNDER_REVIEW = "under_review"            # waiting for the maintainer's release yes
    PUBLISHED = "published"
    REJECTED = "rejected"                    # safety gate said no
    STOPPED = "stopped"                      # poster/maintainer stopped it, or a step failed


TERMINAL = frozenset({Stage.PUBLISHED, Stage.REJECTED, Stage.STOPPED})

# Stages where the idea waits on its assigned maintainer (subject to timeout reassignment).
WAITING_ON_MAINTAINER = frozenset(
    {Stage.SAFETY_UNSURE, Stage.POSSIBLE_DUPLICATE, Stage.PLAN_READY, Stage.WAITING_APPROVAL, Stage.UNDER_REVIEW}
)

_NEXT: dict[Stage, frozenset[Stage]] = {
    Stage.RECEIVED: frozenset({Stage.SAFETY_CHECK}),
    Stage.SAFETY_CHECK: frozenset({Stage.RESEARCHING, Stage.SAFETY_UNSURE, Stage.POSSIBLE_DUPLICATE, Stage.REJECTED}),
    # POSSIBLE_DUPLICATE -> RESEARCHING: a maintainer said it is not a duplicate (-> STOPPED: it is one).
    Stage.POSSIBLE_DUPLICATE: frozenset({Stage.RESEARCHING}),
    Stage.SAFETY_UNSURE: frozenset({Stage.RESEARCHING, Stage.REJECTED}),
    Stage.RESEARCHING: frozenset({Stage.PLAN_READY}),
    # PLAN_READY/WAITING_APPROVAL -> RESEARCHING: a maintainer suggested an alternative, so re-plan.
    Stage.PLAN_READY: frozenset({Stage.WAITING_APPROVAL, Stage.BUILDING, Stage.RESEARCHING}),
    Stage.WAITING_APPROVAL: frozenset({Stage.BUILDING, Stage.RESEARCHING}),
    Stage.BUILDING: frozenset({Stage.UNDER_REVIEW}),
    Stage.UNDER_REVIEW: frozenset({Stage.PUBLISHED, Stage.BUILDING}),
}

LABELS: dict[Stage, str] = {
    Stage.RECEIVED: "Received",
    Stage.SAFETY_CHECK: "Safety check",
    Stage.SAFETY_UNSURE: "Safety check unsure: waiting for maintainer",
    Stage.POSSIBLE_DUPLICATE: "Possible duplicate: waiting for maintainer",
    Stage.RESEARCHING: "Researching and planning",
    Stage.PLAN_READY: "Plan ready: waiting for maintainer",
    Stage.WAITING_APPROVAL: "Waiting for resource approval",
    Stage.BUILDING: "Building",
    Stage.UNDER_REVIEW: "Under review",
    Stage.PUBLISHED: "Published",
    Stage.REJECTED: "Rejected by safety check",
    Stage.STOPPED: "Stopped",
}


class InvalidTransition(ValueError):
    pass


def can_move(src: Stage, dst: Stage) -> bool:
    if dst is Stage.STOPPED:
        return src not in TERMINAL
    return dst in _NEXT.get(src, frozenset())


def check_move(src: Stage, dst: Stage) -> None:
    if not can_move(src, dst):
        raise InvalidTransition(f"cannot move from {src} to {dst}")
