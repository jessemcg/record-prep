"""One literal name/description catalog, with no stage-specific matching rules."""
from __future__ import annotations

import json

from .profile_contract import naming_prompt_titles
from .structured_guidance import effective_resource


def catalog_entries(naming: dict, kind: str) -> list[dict[str, str]]:
    """Project stored catalogs without copying first-page task instructions.

    Historical prose is not heuristically split into per-name descriptions. Its
    explicitly declared names remain usable; the original prose stays in naming.
    Stable IDs identify matched rules in source-title responses, never display names.
    """
    if kind not in ("report", "form"):
        raise ValueError("Unsupported catalog kind")
    naming = effective_resource(naming, "naming")
    version = naming.get("schema_version", 1)
    if version in (4, 5):
        entries = naming[kind + "s"]
        dynamic = any(entry.get("naming_mode") == "source_title" for entry in entries)
        return [{"name": entry["name"], "description": entry["guidance"],
                 **({"rule_id": entry["id"], "naming_mode": entry.get("naming_mode", "fixed")}
                    if dynamic else {})} for entry in entries]
    if version == 3:
        return [{"name": name, "description": ""}
                for name in naming_prompt_titles(naming[kind + "_guidance"])]
    if version in (1, 2):
        if kind == "form" and version == 2:
            return [{"name": rule["name"],
                     "description": f'Heading: {rule["title"]}. Form code: {rule["code"]}.'}
                    for rule in naming["form_rules"]]
        return [{"name": name, "description": ""}
                for name in naming[kind + "_titles"]]
    raise ValueError("Unsupported naming resource")


def catalog_text(naming: dict, kind: str) -> str:
    return json.dumps(catalog_entries(naming, kind), ensure_ascii=False, indent=2)
