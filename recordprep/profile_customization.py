"""Read-only, allowlisted Dependency initialization; persistence is explicit.

Only public defaults and caller-supplied prose are used. Never retain the input
mapping, serialize it, or promote private initialization into bundled resources.
"""
from __future__ import annotations

from collections.abc import Mapping

from .practice_profiles import bundled_profile_directory, validate_profile_directory
from .profile_contract import ProfileError
from .profile_workflows import ProfileEditor

REVIEW_NOTICE = "Includes your previous Dependency settings."
TASK_KEYS = {
    "rt": ("classifier_rt_prompt", "DEFAULT_CLASSIFIER_PROMPT"),
    "ct": ("classifier_ct_prompt", "DEFAULT_CLASSIFIER_PROMPT"),
    "first_hearing": ("advanced_classify_hearing_prompt", "DEFAULT_ADVANCED_HEARING_PROMPT"),
    "first_minute": ("advanced_classify_minute_prompt", "DEFAULT_ADVANCED_MINUTE_PROMPT"),
    "first_form": ("advanced_classify_form_prompt", "DEFAULT_ADVANCED_FORM_PROMPT"),
    "date_hearing": ("classify_dates_hearing_prompt", "DEFAULT_CLASSIFY_HEARING_DATES_PROMPT"),
    "date_minute": ("classify_dates_minute_prompt", "DEFAULT_CLASSIFY_MINUTE_DATES_PROMPT"),
}
SUMMARY_KEYS = {
    "summarize_hearings_prompt": "hearing_extraction",
    "summarize_reports_prompt": "report_extraction",
    "summarize_hearings_synthesis_prompt": "hearing_synthesis",
    "summarize_reports_synthesis_prompt": "report_synthesis",
}


def legacy_customization_editor(config: Mapping[str, object], *, categories=None, base=None) -> ProfileEditor:
    from .ui import main_window as defaults
    from .summary_agents import resolve_phase_guidance
    from .minute_summaries import DEFAULT_MINUTES_PROMPT
    base = base or validate_profile_directory(bundled_profile_directory("california_dependency")).draft
    if base is None:
        raise ProfileError("invalid_bundled_profile", "initialization")
    editor = ProfileEditor(base)
    editor.review_notices = {}

    def custom(key, default, *, fallback=None):
        # Match the loader's missing-vs-empty precedence, but retain the raw
        # custom string rather than returning its stripped runtime form.
        value = config.get(key, fallback if fallback is not None else default)
        if not isinstance(value, str) or not value.strip() or value.strip() == default.strip():
            return None
        return value

    shared = config.get("classifier_prompt", defaults.DEFAULT_CLASSIFIER_PROMPT)
    for task, (key, default_name) in TASK_KEYS.items():
        value = custom(key, getattr(defaults, default_name), fallback=shared if task in ("rt", "ct") else None)
        if value is not None:
            editor.resources["classification_tasks"][task] = value
    value = custom("case_name_prompt", defaults.DEFAULT_CASE_NAME_PROMPT)
    if value is not None:
        editor.resources["case_name"] = value
    for key, resource in SUMMARY_KEYS.items():
        value = config.get(key)
        if isinstance(value, str):
            kind = "hearings" if resource.startswith("hearing_") else "reports"
            phase = "synthesize" if resource.endswith("synthesis") else "extract"
            if resolve_phase_guidance(kind, phase, value).custom_guidance:
                editor.resources[resource] = value
    value = custom("summarize_minutes_prompt", DEFAULT_MINUTES_PROMPT)
    if value is not None:
        editor.resources["minutes"] = value
    # Unassigned minute work historically used first-page parental attendance.
    editor.resources["policies"]["attendance"] = "legacy_first_page_parents"
    for kind, field, default_name in (
        ("report", "report_guidance", "DEFAULT_CLASSIFY_REPORT_NAMES_PROMPT"),
        ("form", "form_guidance", "DEFAULT_CLASSIFY_FORM_NAMES_PROMPT"),
    ):
        value = custom(f"classify_names_{kind}_prompt", getattr(defaults, default_name))
        if value is not None:
            naming = editor.resources["naming"]
            if naming.get("schema_version") == 3:
                # Preserve previous prose verbatim, without pretending arbitrary
                # prose supplies a machine-verifiable list of approved names.
                approved = naming[field].split("\n\n", 1)[0]
                naming[field] = approved + "\n\nPrevious naming instructions (review against the approved names above):\n" + value
            else:
                naming[field] = value
            editor.review_notices["naming"] = (
                "Your previous naming instructions are included. Review the approved names within those instructions."
            )
    if categories is not None:
        for kind in ("hearings", "reports"):
            supplied = categories.get(kind, {})
            for entry in editor.resources[kind]:
                value = supplied.get(entry["id"])
                # This exact shipped predecessor is not a personal override.
                # Do not reattach the retired proposal exclusion on fresh installs.
                if kind == "reports" and entry["id"] == "agency_recommendations" and value == (
                    "The agency's substantive recommendations to the court, stated apart from\n"
                    "any formal proposed-findings-and-orders template, with accurate agency\n"
                    "attribution."
                ):
                    continue
                if isinstance(value, str) and value.strip():
                    entry["guidance"] = value
    return editor


def initial_candidate(base, *, config=None, categories=None):
    if base.ref.specialty_id != "california-juvenile-dependency":
        return None
    if config is None:
        from .ui.main_window import _read_config
        config = _read_config()
    if categories is None:
        from .summary_categories import load_category_descriptions
        categories = {kind: load_category_descriptions(kind) for kind in ("hearings", "reports")}
    editor = legacy_customization_editor(config, categories=categories, base=base)
    snapshot = editor.snapshot()
    return (snapshot, REVIEW_NOTICE) if snapshot.ref != base.ref else None
