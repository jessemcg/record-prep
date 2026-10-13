"""RecordPrep profile adapters; selection never regenerates or renames a case."""
from __future__ import annotations

from pathlib import Path
from .case_profiles import read_case_profile_ref, apply_case_profile
from .profile_contract import ProfileError


def pending_profile(owner, root):
    pending = getattr(owner, "_pending_preparation_profile", None)
    return pending[1] if pending is not None and pending[0] in (None, root) else None


def new_case_profile(owner, root):
    from .practice_profiles import profile_store, accept_new_context_default
    ref = pending_profile(owner, root)
    if ref is not None:
        profile_store().load_profile_snapshot(ref)
        return ref
    return accept_new_context_default()


def reference_label(ref):
    if ref is None:
        return "Existing settings"
    from .practice_profiles import profile_store
    try:
        return profile_store().load_profile_snapshot(ref).manifest["display_name"]
    except (ValueError, OSError):
        return "Unavailable profile"


def preview(snapshot, project_dir: Path):
    from .classification_profiles import KINDS, classifier_prompt
    from .document_naming import compile_naming_profile
    from .summary_profiles import compile_summary
    from .native_profiles import compile_native
    from .minute_summaries import profile_guidance
    from .case_name_profiles import compile_case_name
    sections = {}
    for kind in KINDS:
        sections[f"Classification: {kind}"] = classifier_prompt(snapshot, kind)[0]
    for kind in ("report", "form"):
        sections[f"Naming: {kind}"] = compile_naming_profile(snapshot, kind).prompt
    for kind in ("hearings", "reports"):
        for phase in ("extract", "synthesize"):
            sections[f"{kind}: {phase}"] = compile_summary(snapshot, kind, phase).prompt
    sections["Minutes"] = profile_guidance(snapshot)
    for stage in ("participants", "overview"):
        sections[stage] = compile_native(snapshot, stage, project_dir)[0]
    name = compile_case_name(snapshot)
    if name:
        sections["Case naming"] = name[0]
    return sections


def context_description(root):
    if root is None or not root.exists():
        return "Choose a profile for the new case. Create files will use that choice."
    from .practice_profiles import profile_store
    selected = read_case_profile_ref(root)
    if selected:
        try:
            profile_store().load_profile_snapshot(selected)
        except (ValueError, OSError):
            return "Selected instructions unavailable. Browsing existing output remains available."
    return "Saving settings does not change this case or regenerate existing summaries."


def update_indicator(window):
    widget = getattr(window, "_title_widget", None)
    if widget is None:
        return
    from .practice_profiles import default_profile_candidate, profile_store, profile_catalog
    try:
        root = window._resolve_case_root()
        new_context = root is None or not root.exists()
        if new_context:
            ref = pending_profile(window, root)
            snapshot = profile_store().load_profile_snapshot(ref) if ref else default_profile_candidate()
        else:
            ref = read_case_profile_ref(root)
            snapshot = profile_store().load_profile_snapshot(ref) if ref else None
        name = snapshot.manifest["display_name"] if snapshot else "Existing settings"
        text = name
        notice = ""
        if not new_context and snapshot:
            current = next((item.snapshot for item in profile_catalog() if item.snapshot.ref.specialty_id == snapshot.ref.specialty_id), None)
            if current and current.ref != snapshot.ref:
                notice = "This case uses earlier settings."
        widget.set_subtitle(text)
        widget.set_tooltip_text(name + ("\n" + notice if notice else ""))
    except (ValueError, OSError):
        widget.set_subtitle("Unavailable profile")


def open_manager(owner, project_dir: Path, parent=None):
    from .profile_manager_ui import ProfileManagerWindow
    from .practice_profiles import default_profile_candidate
    root = owner._resolve_case_root()
    from .profile_editor_ui import unavailable
    try:
        previous = read_case_profile_ref(root) if root and root.exists() else None
    except (ValueError, OSError):
        unavailable(parent or owner)
        return None
    identity = (root.stat().st_dev, root.stat().st_ino) if root and root.exists() else None
    generation = getattr(owner, "_case_generation", 0)
    def allowed():
        current_identity = (root.stat().st_dev, root.stat().st_ino) if root and root.exists() else None
        return (not owner._pipeline_running and owner._resolve_case_root() == root and current_identity == identity
                and getattr(owner, "_case_generation", 0) == generation)
    def select(ref):
        nonlocal previous
        if not allowed() or ref is None:
            raise ProfileError("case_changed_or_active", "selection")
        if root is None or not root.exists():
            owner._pending_preparation_profile = (root, ref)
        else:
            apply_case_profile(root, ref, expected_previous=previous)
            previous = ref
            try:
                owner._refresh_step_statuses_from_artifacts()
            except (ValueError, OSError):
                owner.show_toast("Profile selected. Preparation statuses could not be refreshed; reopen the case.")
        update_indicator(owner)
    proposed = previous
    if root is None or not root.exists():
        try:
            proposed = pending_profile(owner, root) or default_profile_candidate().ref
        except (ValueError, OSError):
            pass  # Never silently choose an alternative to an unavailable default.
    try:
        window = ProfileManagerWindow(parent or owner, can_modify=allowed,
                                      preview=lambda snapshot: preview(snapshot, project_dir), on_select=select,
                                      allow_legacy=False, selected_ref=proposed,
                                      case_ref=proposed if root is None or not root.exists() else previous,
                                      has_case=root is not None and root.exists(), settings=parent is not None)
    except (ValueError, OSError):
        unavailable(parent or owner)
        return None
    owner._practice_profiles_window = window
    return window
