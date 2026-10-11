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
