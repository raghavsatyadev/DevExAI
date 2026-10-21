"""Steps 2-4: research, duplicate check, plan (Opus) and the resource lanes (README section 4)."""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..gate import safety
from ..gate.fetch import Page
from ..llm import LLMError, LLMProvider
from ..llm.quoting import Quoter
from ..store import Idea, Project

FREE, ESCALATION = "free", "escalation"
SIZES = ("small", "medium", "large")

SYSTEM = """You are the planner for DevExAI, a company bot that turns employees' ideas into small
developer tools for AI coding assistants (skills, slash commands, MCP servers, hooks, CLI helpers).
The idea already passed a safety check. Write a plan in plain language a non-expert can follow.

- Use the company project summaries so the tool fits what the teams really use.
- Check the list of earlier ideas and say if this one duplicates or overlaps one of them.
- Name existing public tools that already do this, if you know any, so we do not rebuild them.
- List every outside resource the tool needs (libraries, APIs, services, data, licences).
  For each, say honestly whether it is paid and whether it needs an account, login, API key
  or licence. Do not invent prices; say "unknown" if unsure. Do not list the AI assistant the
  tool runs in, the company's own code or data, or tools developers already have (git, the
  language toolchain, the build system); they are already approved.
- The build must include tests and a short README. Keep the scope small enough for one person.
{data_rule}"""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "assistants": {"type": "array", "items": {"type": "string"}},
        "deliverables": {"type": "array", "items": {"type": "string"}},
        "test_plan": {"type": "string"},
        "size": {"type": "string", "enum": list(SIZES)},
        "resources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "why": {"type": "string"},
                    "paid": {"type": "boolean"},
                    "needs_account_or_key": {"type": "boolean"},
                    "cost": {"type": "string"},
                },
                "required": ["name", "why", "paid", "needs_account_or_key", "cost"],
                "additionalProperties": False,
            },
        },
        "duplicate_of": {"type": "array", "items": {"type": "integer"}},
        "existing_tools": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary", "assistants", "deliverables", "test_plan", "size",
        "resources", "duplicate_of", "existing_tools", "questions",
    ],
    "additionalProperties": False,
}


def build_prompt(
    quoter: Quoter, idea: Idea, pages: list[Page], projects: list[Project], others: list[Idea]
) -> str:
    parts = [f"Idea #{idea.id}, titled {idea.title!r}, topic {idea.topic!r}:", quoter.quote("idea", idea.text)]
    for page in pages:
        if page.ok:
            parts += [f"Linked page {page.url}:", quoter.quote(page.url, page.text)]
    if projects:
        parts.append("Company projects (written by maintainers):")
        parts += [f"- {p.name}: {p.summary}" for p in projects]
    else:
        parts.append("No company project summaries are recorded yet.")
    if others:
        parts += ["Earlier ideas (for the duplicate check):", quoter.quote("earlier-ideas", safety.listing(others))]
    parts.append("Write the plan as JSON.")
    return "\n\n".join(parts)


def _lane(resource: dict[str, Any]) -> str:
    # Decided here, not by the model: anything paid or gated always goes to a human.
    return ESCALATION if resource.get("paid") or resource.get("needs_account_or_key") else FREE


def make_plan(
    llm: LLMProvider, settings: Settings, idea: Idea, pages: list[Page],
    projects: list[Project], others: list[Idea],
) -> dict[str, Any]:
    quoter = Quoter()
    out = llm.complete(
        "planner", SYSTEM.format(data_rule=quoter.rule),
        build_prompt(quoter, idea, pages, projects, others), SCHEMA,
    )
    if not isinstance(out.get("summary"), str) or not out["summary"].strip():
        raise LLMError("planner returned no summary")
    known = {o.id for o in others}
    resources = [{**r, "lane": _lane(r)} for r in out.get("resources", []) if isinstance(r, dict)]
    return {
        "summary": out["summary"].strip(),
        "assistants": [str(a) for a in out.get("assistants", [])],
        "deliverables": [str(d) for d in out.get("deliverables", [])],
        "test_plan": str(out.get("test_plan", "")),
        "size": out.get("size") if out.get("size") in SIZES else "medium",
        "resources": resources,
        "duplicate_of": [i for i in out.get("duplicate_of", []) if i in known],
        "existing_tools": [str(t) for t in out.get("existing_tools", [])],
        "questions": [str(q) for q in out.get("questions", [])],
    }


def needs_approval(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in plan.get("resources", []) if r.get("lane") == ESCALATION]


def format_plan(plan: dict[str, Any]) -> str:
    lines = [f"*Plan* ({plan['size']}): {plan['summary']}"]
    if plan["assistants"]:
        lines.append("For: " + ", ".join(plan["assistants"]))
    if plan["deliverables"]:
        lines.append("Will build:\n" + "\n".join(f"  - {d}" for d in plan["deliverables"]))
    if plan["test_plan"]:
        lines.append(f"Testing: {plan['test_plan']}")
    if plan["resources"]:
        lines.append("Resources:\n" + "\n".join(
            f"  - {r['name']} [{'free, used automatically' if r['lane'] == FREE else 'needs approval'}]"
            f": {r['why']}" + ("" if r["lane"] == FREE else f" (cost: {r['cost']})")
            for r in plan["resources"]
        ))
    if plan["duplicate_of"]:
        lines.append("Looks similar to: " + ", ".join(f"#{i}" for i in plan["duplicate_of"]))
    if plan["existing_tools"]:
        lines.append("Existing tools to check first: " + "; ".join(plan["existing_tools"]))
    if plan["questions"]:
        lines.append("Open questions:\n" + "\n".join(f"  - {q}" for q in plan["questions"]))
    return "\n".join(lines)
