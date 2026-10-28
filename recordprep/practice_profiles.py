"""RecordPrep-owned profile API. No activation or settings migration on import."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .profile_contract import (
    CompiledStage, ProfileError, ProfileRef, ProfileSnapshot, ValidationResult,
    compile_stage_profile, identity_descriptor, json_bytes, parse_identity_descriptor,
    validate_profile_directory as _validate, validation_report,
)
from .profile_store import ProfileStore

APPLICATION = "recordprep"
BUNDLED_PROFILES = ("california_dependency",)
DEFAULT_PROFILE_ID = "california-juvenile-dependency"
# Retired identities remain readable, but never appear as choices or bases.
RETIRED_PROFILE_IDS = frozenset({"general-court-record"})
# Reviewed, exact prior bundled snapshots; ordinary acceptance is not ownership.
KNOWN_BASELINES = (
    "8b451694685162200a99c342c501b770fba61c976721322bec2c416a13f366d8",
    "32da44dd71053b9abef31cf991550bf28803ec05b90e27fcc8b37c54e37dee51",
    "a215bd81feb4aacf6aa1bbc16e30fb952e52fa5028a141afa0cfb2530be168ef",
    "1de6857de38358bcbd6d204f70f4e6457e2bfa943a71304e41a1ed9877bda24b",
    "13e1314252cdcbd978466d489e858108bdee4711bdf27f27f3119be79e0f9f47",
    "d97e2ce3ebbb408aca055d1b2f6081e872ded8937939789ce616081a1e0a4f0a",
    "555959531be83a38dd90b8e577a49c6126775dc8e07a5bc3fbd8e1f3e2d2a0ee",
    "7959a9f50f14b53705f423a4278152b4ff8303c8b45885ac1ad458c43009f472",
    "1396a9dff51149a63ae343e9613b8168f55cd5c5398762e493ca62f1683c19b3",
    "22c34043d3bb4f17af259a3316b67f521ee454381c3a3e0232618559f2e89ead",
    "037c2353ba58dbaad2e37d4e1cda4e7b37bec4a81fa32f84ee6bbb6f69289e20",
    "25d33985b4b14ef70e1308ce4f630277ea17af5ef40d07fb6c499fb8577da2c9",
    "fca78671abcd14c0ad7e96c26af0ebb53285e983f74fed8660f899d617c01b14",
)


def profile_catalog(*, store=None, customization=None):
    from .profile_workflows import current_catalog
    from .profile_customization import initial_candidate
    bundled = []
    for name in BUNDLED_PROFILES:
        snapshot = validate_profile_directory(bundled_profile_directory(name)).draft
        if snapshot is None:
            raise ProfileError("invalid_bundled_profile", "profiles")
        bundled.append(snapshot)
    return current_catalog(store or profile_store(), bundled, known_baselines=KNOWN_BASELINES,
                           customization=initial_candidate if customization is None else customization,
                           excluded_identities=RETIRED_PROFILE_IDS)


def bundled_profile_for_identity(application: str, specialty_id: str) -> ProfileSnapshot | None:
    """Read-only, validated shipped counterpart, never a personal catalog override.

    Fail closed on a corrupt bundle; legacy archives and creation bases are not
    candidates. Call again before publishing a target frozen for confirmation.
    """
    if application != APPLICATION or specialty_id in RETIRED_PROFILE_IDS:
        return None
    matches = []
    for name in BUNDLED_PROFILES:
        result = validate_profile_directory(bundled_profile_directory(name))
        if result.draft is None:
            raise ProfileError("invalid_bundled_profile", "profiles")
        snapshot = result.draft
        if (snapshot.ref.application, snapshot.ref.specialty_id) == (application, specialty_id):
            matches.append(snapshot)
    if len(matches) > 1:
        raise ProfileError("duplicate_bundled_identity", "profiles")
    return matches[0] if matches else None


def bundled_profile_directory(name: str) -> Path:
    # Compatibility-only lookup for old minute defaults, schema-1 editing and
    # historical fixtures. This archive is not part of the selectable catalog.
    if name == "general":
        return Path(__file__).resolve().parent / "resources" / "legacy_practice_profiles" / name
    if name not in BUNDLED_PROFILES:
        raise ProfileError("unknown_bundled_profile", "profile")
    return Path(__file__).resolve().parent / "resources" / "practice_profiles" / name


def validate_profile_directory(path: Path) -> ValidationResult:
    return _validate(path, APPLICATION)


def profile_store() -> ProfileStore:
    """Explicit portable settings root, or unchanged private XDG storage.

    Nothing is copied, migrated or created by resolving a store. A portable root
    contains only registry/snapshots; locks remain in machine-local state.
    """
    from .profile_portability import selected_directory, portable_store
    selected = selected_directory()
    if selected is not None:
        return portable_store(selected)
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return ProfileStore(APPLICATION, config_root=config / APPLICATION / "practice-profiles",
                        data_root=data / APPLICATION / "practice-profiles")


def default_profile_candidate(*, store: ProfileStore | None = None) -> ProfileSnapshot:
    """Read-only application selection used for every new preparation run."""
    store = store or profile_store()
    if store.application != APPLICATION:
        raise ProfileError("wrong_application", "default")
    registry = store.read_registry()
    if registry["default"] is not None and registry["default"]["specialty_id"] not in RETIRED_PROFILE_IDS:
        return store.load_profile_snapshot(ProfileRef.from_dict(registry["default"]))
    # A retired selection falls back in memory only. Never rewrite the registry
    # or its immutable snapshots merely by opening the application.
    return next(candidate.snapshot for candidate in profile_catalog(store=store, customization=lambda _base: None)
                if candidate.snapshot.ref.specialty_id == DEFAULT_PROFILE_ID)


def accept_new_context_default(*, store: ProfileStore | None = None) -> ProfileRef:
    """Explicit creation action only. Existing bindings never call this function."""
    from dataclasses import asdict
    store = store or profile_store()
    snapshot = default_profile_candidate(store=store)
    registry = store.read_registry()
    if any(entry["ref"] == asdict(snapshot.ref) for entry in registry["accepted"]):
        store.load_profile_snapshot(snapshot.ref)
        return snapshot.ref
    return store.accept_profile(snapshot, expected_previous_digest=registry["heads"].get(snapshot.ref.specialty_id))


def _cmd_validate(args: argparse.Namespace) -> int:
    result = validate_profile_directory(args.path)
    if args.json:
        print(json_bytes(validation_report(result)).decode("utf-8"), end="")
    elif result.draft:
        ref = result.draft.ref
        print(f"Valid {ref.application} profile: {ref.specialty_id} ({ref.content_sha256})")
    else:
        for issue in result.issues:
            print(f"{issue.code}: {issue.location}")
    return 0 if result.draft else 1


def add_profile_parser(subparsers) -> None:
    parser = subparsers.add_parser("profiles", help="read-only practice-profile diagnostics")
    actions = parser.add_subparsers(dest="profile_command", required=True)
    validate = actions.add_parser("validate", help="validate an explicitly supplied profile folder; never accept it")
    validate.add_argument("path", type=Path)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=_cmd_validate)
