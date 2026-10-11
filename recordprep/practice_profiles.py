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
BUNDLED_PROFILES = ("general", "california_dependency")


def bundled_profile_directory(name: str) -> Path:
    if name not in BUNDLED_PROFILES:
        raise ProfileError("unknown_bundled_profile", "profile")
    return Path(__file__).resolve().parent / "resources" / "practice_profiles" / name


def validate_profile_directory(path: Path) -> ValidationResult:
    return _validate(path, APPLICATION)


def profile_store() -> ProfileStore:
    """Machine-local XDG storage, never the source checkout's private config."""
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return ProfileStore(APPLICATION, config_root=config / APPLICATION / "practice-profiles",
                        data_root=data / APPLICATION / "practice-profiles")


def default_profile_candidate(*, store: ProfileStore | None = None) -> ProfileSnapshot:
    """Read-only proposal for a new context; never rebind an existing case."""
    store = store or profile_store()
    if store.application != APPLICATION:
        raise ProfileError("wrong_application", "default")
    registry = store.read_registry()
    if registry["default"] is not None:
        return store.load_profile_snapshot(ProfileRef.from_dict(registry["default"]))
    result = validate_profile_directory(bundled_profile_directory("general"))
    if result.draft is None:
        raise ProfileError("invalid_bundled_default", "default")
    return result.draft


def accept_new_context_default(*, store: ProfileStore | None = None) -> ProfileRef:
    """Explicit creation action only. Existing bindings never call this function."""
    from dataclasses import asdict
    store = store or profile_store()
    snapshot = default_profile_candidate(store=store)
    registry = store.read_registry()
    if any(entry["ref"] == asdict(snapshot.ref) for entry in registry["accepted"]):
        store.load_profile_snapshot(snapshot.ref)
        return snapshot.ref
    # A local same-identity revision is a conflict requiring explicit review,
    # not permission for a new-case default to replace its accepted head.
    if snapshot.ref.specialty_id in registry["heads"]:
        raise ProfileError("review_default_revision_first", "default")
    return store.accept_profile(snapshot, expected_previous_digest=None)


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
