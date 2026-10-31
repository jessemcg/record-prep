"""Explicit Pi skill commands shared by native, caption and summary launches."""
from __future__ import annotations

# Generation identity: changing delivery must not silently reuse older work.
SKILL_DELIVERY_CONTRACT = "slash-skill-space-v1"


def skill_launch(skill_name: str, request: str) -> str:
    # Pi separates the skill name from arguments at the first literal space,
    # not at a newline. Keep the remaining request, including returns, literal.
    return f"/skill:{skill_name} {request}"
