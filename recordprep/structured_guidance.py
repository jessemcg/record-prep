"""Exact public-resource adapters. No settings access, writes or heuristic splitting."""
from __future__ import annotations

import json
from pathlib import Path

_BASE = Path(__file__).parent / "resources/profile_baselines/dependency-1.6.0"


def _active_classification(value: dict) -> dict:
    """Exact active projection, never split or partially replace custom prose.

    Dates are inert in flat resources. The lossless v3 editing wrapper adds only
    an application fallback report task; a custom report task must not match.
    All other keys and every active prose byte participate in recognition.
    """
    if "page_types" in value:
        return value
    result = {key: text for key, text in value.items() if key not in {"date_hearing", "date_minute"}}
    if result.get("schema_version") == 3:
        from .classifier_prompts import REPORT_FIRST_CLUES
        if result.get("first_report") == REPORT_FIRST_CLUES:
            result.pop("schema_version")
            result.pop("first_report")
    return result


def _classification_sources():
    return [_BASE / "classification-tasks.json", _BASE / "classification-v2.json",
            _BASE.parent / "dependency-1.7.0-initial/classification-v2.json",
            _BASE.parent / "dependency-1.7.0-shared/classification-v2.json",
            _BASE.parent / "dependency-1.8.0/classification-v3.json"]


def classification_task_resource(value: dict, kind: str) -> dict:
    """Exact whole-task runtime matching, independent of unrelated task edits.

    A known RT/CT description map or complete legacy task string can use its
    public equivalent. Unknown task prose is never split, partially replaced or
    combined with a substitute. This projection is not an editable resource.
    """
    if kind not in {"rt", "ct", "first_hearing", "first_minute", "first_form", "first_report"}:
        return value
    def task(resource):
        if "page_types" in resource:
            return resource["page_types"].get(kind) if kind in {"rt", "ct"} else resource["first_pages"].get(kind)
        return resource.get(kind)
    selected = task(value)
    if selected is not None:
        for source in _classification_sources():
            if selected == task(json.loads(source.read_bytes())):
                return json.loads((_BASE.parent / "dependency-1.8.0/classification-v3-unwrapped.json").read_bytes())
    return value


def effective_resource(value: dict, resource: str) -> dict:
    """Recognize complete allowlisted active content, independently of snapshot."""
    classification = resource == "classification_tasks"
    target = "classification-v2.json" if classification else "naming-v4.json"
    original = "classification-tasks.json" if classification else "naming.json"
    # Parsed-object equality ignores storage whitespace/key order, not prose bytes.
    sources = [_BASE / original, _BASE.parent / "dependency-1.7.0-initial" / target]
    if classification:
        sources = _classification_sources()
    project = _active_classification if classification else lambda resource: resource
    if any(project(value) == project(json.loads(source.read_bytes())) for source in sources):
        output = (_BASE.parent / "dependency-1.8.0/classification-v3-unwrapped.json") if classification else _BASE / target
        return json.loads(output.read_bytes())
    return value


def structured_resources(resources: dict) -> tuple[dict, dict, bool]:
    original = resources["classification_tasks"]
    tasks = effective_resource(original, "classification_tasks")
    if tasks != original and "date_hearing" in original:
        baseline = json.loads((_BASE / "classification-tasks.json").read_bytes())
        if any(original.get(key) != baseline[key] for key in ("date_hearing", "date_minute")):
            # Runtime projection is not an editable-format decision. Keep the
            # lossless draft when cards would discard retained archival prose.
            tasks = original
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
