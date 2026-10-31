"""Exact public-resource adapters. No settings access, writes or heuristic splitting."""
from __future__ import annotations

import json
from pathlib import Path

_BASE = Path(__file__).parent / "resources/profile_baselines/dependency-1.6.0"


def effective_resource(value: dict, resource: str) -> dict:
    """Recognize only the complete allowlisted resource, independently of snapshot."""
    classification = resource == "classification_tasks"
    target = "classification-v2.json" if classification else "naming-v4.json"
    original = "classification-tasks.json" if classification else "naming.json"
    # Parsed-object equality ignores storage whitespace/key order, not prose bytes.
    sources = [_BASE / original, _BASE.parent / "dependency-1.7.0-initial" / target]
    if classification:
        sources += [_BASE / target, _BASE.parent / "dependency-1.7.0-shared" / target,
                    _BASE.parent / "dependency-1.8.0/classification-v3.json"]
    if any(value == json.loads(source.read_bytes()) for source in sources):
        output = (_BASE.parent / "dependency-1.8.0/classification-v3-unwrapped.json") if classification else _BASE / target
        return json.loads(output.read_bytes())
    return value


def structured_resources(resources: dict) -> tuple[dict, dict, bool]:
    tasks = effective_resource(resources["classification_tasks"], "classification_tasks")
    naming = effective_resource(resources["naming"], "naming")
    from .classifier_prompts import REPORT_FIRST_CLUES
    if "schema_version" not in tasks:
        tasks = tasks | {"schema_version": 3, "first_report": REPORT_FIRST_CLUES}
    elif tasks.get("schema_version") == 2:
        # Explicit editing adds the new field only; every old custom description
        # remains literal. Runtime uses the same fixed fallback without writes.
        tasks = tasks | {"schema_version": 3,
                         "first_pages": tasks["first_pages"] | {"first_report": REPORT_FIRST_CLUES}}
    return tasks, naming, tasks.get("schema_version") == 3 and naming.get("schema_version") == 4


def legacy_policy_warning(text: str) -> str:
    import re
    return ("Compatibility guidance contains ordering language. The application's best-fit policy controls; "
            "review this legacy prose before new work. Stored text has not been rewritten."
            if re.search(r"apply in order|decision rule.*in order|else if|first match", text, re.I) else "")
