"""RecordPrep GUI adapters; preparation choices never alter research settings."""
from __future__ import annotations

import os
from pathlib import Path

from .case_profiles import read_case_profile_ref, apply_case_profile
from .profile_contract import ProfileError, _json, read_file_at
from .profile_artifacts import preparation_provenance


def pending_profile(owner, root):
    pending = getattr(owner, "_pending_preparation_profile", None)
    return pending[1] if pending is not None and pending[0] == root else None


def new_case_profile(owner, root):
    """Only the explicit Create files flow calls this acceptance operation."""
    from .practice_profiles import profile_store, accept_new_context_default
    ref = pending_profile(owner, root)
    if ref is not None:
        profile_store().load_profile_snapshot(ref)
        return ref
    return accept_new_context_default()


def reference_label(ref) -> str:
    if ref is None:
        return "Legacy / unassigned"
    if not isinstance(ref, dict):
        from dataclasses import asdict
        ref = asdict(ref)
    return f"{ref['specialty_id']} · {ref['version']} · {ref['content_sha256'][:8]}"


def preview(snapshot, project_dir: Path):
    from .classification_profiles import CORE as CLASSIFICATION_CORE, KINDS, classifier_prompt
    from .document_naming import compile_naming_profile
    from .summary_profiles import CORE, compile_summary
    from .native_profiles import compile_native
    from .minute_summaries import profile_guidance
    sections = {"Application-owned record fidelity contract": CORE,
                "Application-owned classifier taxonomy": CLASSIFICATION_CORE}
    for kind in KINDS:
        sections[f"Classification: {kind} (core + subordinate guidance)"] = classifier_prompt(snapshot, kind)[0]
    for kind in ("report", "form"):
        sections[f"Naming: {kind} (core + catalog/guidance)"] = compile_naming_profile(snapshot, kind).prompt
    for kind in ("hearings", "reports"):
        for phase in ("extract", "synthesize"):
            sections[f"{kind}: {phase} (core + subordinate guidance)"] = compile_summary(snapshot, kind, phase).prompt
    sections["Minutes (core + declared attendance policy/guidance)"] = profile_guidance(snapshot)
    for stage in ("participants", "overview"):
        sections[f"{stage} (core + subordinate guidance; runtime paths omitted)"] = compile_native(snapshot, stage, project_dir)[0]
    return sections


def context_description(root):
    lines = ["Profile selection never regenerates output. Classification/naming and boundaries may require rerunning before later stages; model work may incur charges. Start runs explicitly."]
    if root is None or not root.exists():
        return "No existing case bundle. Choose a PDF first to set a new-case profile; that choice is held in memory until Create files. Defaults and authoring remain independent. No existing case is rebound."
    try:
        selected = read_case_profile_ref(root)
        lines.append("Selected preparation: " + reference_label(selected))
        if selected is not None:
            from .practice_profiles import profile_store
            try:
                profile_store().load_profile_snapshot(selected)
            except (ValueError, OSError):
                lines.append("Selected instructions unavailable. Explicitly restore/register the matching revision or choose an alternative before new preparation; browsing remains available.")
        path = root / "artifacts/practice_profile_provenance.json"
        published = None
        if path.exists() or path.is_symlink():
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                published = preparation_provenance(_json(read_file_at(fd, "artifacts/practice_profile_provenance.json"), "publication"))["profile_ref"]
            finally:
                os.close(fd)
        lines.append("Last published preparation: " + reference_label(published))
        lines.append("Existing readable artifacts keep their recorded provenance, independently of this selection.")
    except (ValueError, OSError):
        lines.append("Preparation metadata unavailable; it was not rewritten or substituted.")
    return "\n".join(lines)


def update_indicator(window):
    widget = getattr(window, "_practice_profile_button", None)
    if widget is None:
        return
    try:
        root = window._resolve_case_root()
        new_context = root is None or not root.exists()
        from .practice_profiles import default_profile_candidate, profile_store
        if new_context:
            pending = pending_profile(window, root)
            snapshot = profile_store().load_profile_snapshot(pending) if pending is not None else default_profile_candidate()
            ref = snapshot.ref
        else:
            ref = read_case_profile_ref(root)
            snapshot = profile_store().load_profile_snapshot(ref) if ref is not None else None
        short = snapshot.manifest["display_name"] if snapshot else "Legacy"
        widget.set_label(("New case: " if new_context else "Preparation: ") + (short if len(short) <= 24 else short[:23] + "…"))
        widget.set_tooltip_text("Practice Profiles — " + reference_label(ref))
    except (ValueError, OSError):
        widget.set_label("Preparation: unavailable")
        widget.set_tooltip_text("Choose an explicit available revision. Existing readable artifacts remain untouched.")


def open_manager(owner, project_dir: Path, parent=None):
    from .profile_manager_ui import ProfileManagerWindow
    root = owner._resolve_case_root()
    previous = read_case_profile_ref(root) if root and root.exists() else None
    def allowed():
        return not owner._pipeline_running and owner._resolve_case_root() == root
    def select(ref):
        nonlocal previous
        if not allowed() or root is None:
            raise ProfileError("choose_pdf_first_or_case_changed", "selection")
        if ref is None:
            raise ProfileError("choose_accepted_preparation_revision", "selection")
        if not root.exists():
            owner._pending_preparation_profile = (root, ref)
            update_indicator(owner)
            window.context_group.set_description(context_description(root) + "\nNew-case choice in memory: " + reference_label(ref))
            return "New-case choice held in memory. Create files to bind it; no case files or defaults changed."
        apply_case_profile(root, ref, expected_previous=previous)
        previous = ref
        owner._refresh_step_statuses_from_artifacts()
        update_indicator(owner)
        window.context_group.set_description(context_description(root))
    proposed = previous
    if root is None or not root.exists():
        from .practice_profiles import default_profile_candidate
        try:
            proposed = pending_profile(owner, root) or default_profile_candidate().ref
        except (ValueError, OSError):
            pass  # Show available alternatives, never silently select/use one.
    def customization():
        from .profile_customization import legacy_customization_editor, REVIEW_NOTICE
        from .summary_categories import load_category_descriptions
        from .ui.main_window import _read_config
        categories = {kind: load_category_descriptions(kind) for kind in ("hearings", "reports")}
        return legacy_customization_editor(_read_config(), categories=categories), REVIEW_NOTICE

    window = ProfileManagerWindow(parent or owner, can_modify=allowed,
                                  preview=lambda snapshot: preview(snapshot, project_dir),
                                  on_select=select, context_text=context_description(root),
                                  allow_legacy=False, selected_ref=proposed, customization=customization, can_select=lambda: root is not None)
    window.connect("close-request", lambda _window: (update_indicator(owner), False)[1])
    owner._practice_profiles_window = window
    window.present()
    return window
