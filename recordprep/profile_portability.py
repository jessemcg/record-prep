"""Explicit settings-save flows for portable profiles; never migrate on launch."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from .profile_contract import ProfileError, ProfileRef, _json, _require, json_bytes
from .profile_store import PortableProfileStore, _atomic_json, _check_directory, _ensure_root, _private_file


def locator_path() -> Path:
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return state / "recordprep" / "profile-storage.json"


def selected_directory() -> Path | None:
    explicit = os.environ.get("RECORDPREP_PROFILE_DIR", "")
    if explicit:
        root = Path(explicit)
    else:
        locator = locator_path()
        if not locator.exists() and not locator.is_symlink():
            return None
        _check_directory(locator.parent, private=True)
        _private_file(locator)
        value = _json(locator.read_bytes(), "profile_storage")
        _require(isinstance(value, dict) and set(value) == {"directory"} and
                 isinstance(value["directory"], str), "invalid_fields", "profile_storage")
        root = Path(value["directory"])
    _require(root.is_absolute() and ".." not in root.parts, "absolute_store_required", "storage")
    # A configured portable folder disappearing must not silently reset guidance.
    _require(root.is_dir() and (root / "registry.json").is_file(),
             "portable_store_unavailable", "storage")
    return root


def portable_store(root: Path) -> PortableProfileStore:
    key = hashlib.sha256(str(root).encode()).hexdigest()
    return PortableProfileStore("recordprep", config_root=root, data_root=root,
                               lock_root=locator_path().parent / "profile-locks" / key)


def use_directory(root: Path, *, can_modify=lambda: True) -> None:
    """Explicit UI action only: validate the whole store before selecting it."""
    from .practice_profiles import default_profile_candidate, profile_store
    _require(not os.environ.get("RECORDPREP_PROFILE_DIR"), "profile_storage_override", "storage")
    _require(can_modify(), "work_active_or_case_changed", "storage")
    store = portable_store(root)
    _require(store.registry_path.is_file(), "portable_store_unavailable", "storage")
    registry = store.read_registry()
    for entry in registry["accepted"]:
        store.load_profile_snapshot(ProfileRef.from_dict(entry["ref"]))
    default_profile_candidate(store=store)
    # A storage switch is a settings change too: serialize it with publishers
    # holding the old selection's registry lock, not merely with other exports.
    with profile_store()._locked():
        _require(can_modify(), "work_active_or_case_changed", "storage")
        locator = locator_path()
        _ensure_root(locator.parent)
        if locator.exists() or locator.is_symlink():
            _private_file(locator)
        _atomic_json(locator, {"directory": str(root)})


def save_portable_profiles(source, destination: Path, *, can_modify=lambda: True) -> None:
    """Save current guidance to a NEW folder; retain the original private store.

    Historical revisions are not dependencies of bundles. Export current catalog
    entries and the active snapshot, without credentials or old source paths.
    Publication is no-replace, and selection is a separate explicit UI action.
    """
    from .practice_profiles import default_profile_candidate, profile_catalog
    from .profile_workflows import _destination, _publish_new_directory
    _destination(destination)
    _require(can_modify(), "work_active_or_case_changed", "storage")
    before = json_bytes(source.read_registry())
    selected = default_profile_candidate(store=source)
    candidates = profile_catalog(store=source)
    pending = Path(tempfile.mkdtemp(prefix=".profile-export-", dir=destination.parent))
    try:
        target = portable_store(pending)
        for candidate in candidates:
            registry = target.read_registry()
            target.managed_save(candidate.snapshot,
                                expected_head=registry["heads"].get(candidate.snapshot.ref.specialty_id),
                                expected_default=registry["default"], personal=candidate.personal,
                                can_modify=can_modify)
        registry = target.read_registry()
        if not any(entry["ref"]["content_sha256"] == selected.ref.content_sha256 for entry in registry["accepted"]):
            target.accept_profile(selected, expected_previous_digest=registry["heads"].get(selected.ref.specialty_id))
        target.set_default(selected.ref)
        with source._locked():
            _require(can_modify() and json_bytes(source.read_registry()) == before,
                     "stale_profile_revision", "storage")
            _publish_new_directory(pending, destination)
    finally:
        if pending.exists():
            shutil.rmtree(pending)
