"""Explicit, allowlisted legacy-guidance copy. Never serialize runtime settings."""
from __future__ import annotations

from collections.abc import Mapping

from .practice_profiles import bundled_profile_directory, validate_profile_directory
from .profile_contract import ProfileError
from .profile_workflows import ProfileEditor

# These keys contain prose, not credentials, models, budgets, endpoints or paths.
# Case-name formatting remains an application setting outside practice profiles.
CLASSIFICATION_KEYS = (
    "classifier_prompt", "classifier_rt_prompt", "classifier_ct_prompt",
    "advanced_classify_hearing_prompt", "advanced_classify_minute_prompt",
    "advanced_classify_form_prompt", "classify_dates_hearing_prompt", "classify_dates_minute_prompt",
)
SUMMARY_KEYS = {
    "summarize_hearings_prompt": "hearing_extraction",
    "summarize_reports_prompt": "report_extraction",
    "summarize_hearings_synthesis_prompt": "hearing_synthesis",
    "summarize_reports_synthesis_prompt": "report_synthesis",
    "summarize_minutes_prompt": "minutes",
}
REVIEW_NOTICE = (
    "Private legacy-guidance copy, not a migration. Original settings and cases remain untouched. "
    "Prompt text is preserved literally beneath application-owned contracts; review conflicting historical "
    "output instructions in Preview. Review naming catalogs and policies explicitly: prose does not "
    "automatically change structured catalogs. Case-name formatting and all runtime settings remain "
    "outside this profile. Review for private matter details before sharing. Save/Accept does not select "
    "this profile for a case or make it the default."
)


def legacy_customization_editor(config: Mapping[str, object], *, categories=None) -> ProfileEditor:
    """Caller reads real settings only after an explicit GUI copy action.

    Tests supply synthetic mappings. No file is read/written here and the mapping
    is never retained. Unknown keys cannot leak into a draft or exported folder.
    """
    base = validate_profile_directory(bundled_profile_directory("california_dependency")).draft
    if base is None:
        raise ProfileError("invalid_bundled_profile", "legacy_copy")
    editor = ProfileEditor.create(base, "Private legacy customization")
    editor.manifest["description"] = "Private copy for explicit review; not selected automatically."

    def append(resource, key, *, field=None):
        value = config.get(key)
        if not isinstance(value, str) or not value:
            return
        # Never strip or normalize actual custom prompt text.
        addition = "\n\n## Copied legacy prompt: " + key + "\n\n" + value
        if field:
            editor.resources[resource][field] += addition
        else:
            editor.resources[resource] += addition

    for key in CLASSIFICATION_KEYS:
        append("classification", key)
    append("naming", "classify_names_report_prompt", field="report_guidance")
    append("naming", "classify_names_form_prompt", field="form_guidance")
    from .summary_agents import resolve_phase_guidance
    for key, resource in SUMMARY_KEYS.items():
        value = config.get(key)
        if resource != "minutes" and isinstance(value, str):
            kind = "hearings" if resource.startswith("hearing_") else "reports"
            phase = "synthesize" if resource.endswith("synthesis") else "extract"
            if not resolve_phase_guidance(kind, phase, value).custom_guidance:
                continue  # Historical built-ins are not personal overrides.
        append(resource, key)
    if categories is not None:
        for kind in ("hearings", "reports"):
            supplied = categories.get(kind, {})
            for entry in editor.resources[kind]:
                value = supplied.get(entry["id"])
                if isinstance(value, str) and value.strip():
                    entry["guidance"] = value
    return editor
