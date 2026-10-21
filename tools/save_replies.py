"""Save one idea's real gate and plan replies so later test runs replay them ([llm] provider = "replay").

    uv run python tools/save_replies.py <devexai.db> <idea id> [out dir, default data/llm-replies]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from devexai.store import Store


def main(db: str, idea_id: str, out: str = "data/llm-replies") -> None:
    idea = Store(db).ideas.get(int(idea_id))
    if not idea.gate or not idea.plan:
        sys.exit(f"idea #{idea.id} has no gate and plan reply yet")
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    gate = {k: v for k, v in idea.gate.items() if k != "links"}
    for role, reply in (("gate", gate), ("planner", idea.plan)):
        (folder / f"{role}.json").write_text(json.dumps(reply, indent=2), encoding="utf-8")
    print(f"saved gate.json and planner.json from idea #{idea.id} in {folder}")


if __name__ == "__main__":
    main(*sys.argv[1:])
