"""Explicit app-owned preparation bindings; opening a case is read-only."""
from __future__ import annotations

import fcntl
import os
from dataclasses import asdict
from contextlib import contextmanager
from pathlib import Path

from .practice_profiles import profile_store
from .profile_artifacts import preparation_selection
from .profile_contract import ProfileError, ProfileRef, ProfileSnapshot, _json, read_file_at
from .profile_store import ProfileStore, _atomic_json, _check_directory, _private_file


def read_case_profile_ref(root: Path) -> ProfileRef | None:
    directory = root / ".recordprep"
    path = directory / "practice-profile.json"
    if not directory.exists() and not directory.is_symlink():
        return None
    _check_directory(directory)
    if not path.exists() and not path.is_symlink():
        return None
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            return preparation_selection(_json(read_file_at(fd, "practice-profile.json"), "case_selection"))
        finally:
            os.close(fd)
    except OSError as exc:
        raise ProfileError("unreadable_case_selection", "case") from exc


def resolve_case_profile(root: Path, *, store: ProfileStore | None = None) -> ProfileSnapshot | None:
    ref = read_case_profile_ref(root)
    if ref is None:
        return None  # Explicitly unassigned legacy behavior, never inferred General.
    return (store or profile_store()).load_profile_snapshot(ref)


@contextmanager
def case_profile_publication(root: Path, expected: ProfileRef | None):
    """Serialize final publication against explicit binding changes, not model work.

    Creating a lock during an explicit generation action never creates a binding.
    Read-only case opening and freshness checks do not call this function.
    """
    directory = root / ".recordprep"
    directory.mkdir(mode=0o700, exist_ok=True)
    _check_directory(directory, private=True)
    lock = directory / ".practice-profile.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        _private_file(lock)
        fcntl.flock(fd, fcntl.LOCK_EX)
        if read_case_profile_ref(root) != expected:
            raise ProfileError("stale_case_selection", "publication")
        yield
    finally:
        os.close(fd)


def apply_case_profile(root: Path, ref: ProfileRef, *, expected_previous: ProfileRef | None,
                       store: ProfileStore | None = None) -> None:
    """Settings/apply action only. Select accepted bytes; never process sources.

    The expected old ref detects competing app instances. Changing the default
    does not call this function and therefore cannot change any existing case.
    """
    store = store or profile_store()
    if ref.application != "recordprep" or store.application != "recordprep":
        raise ProfileError("wrong_application", "case")
    store.load_profile_snapshot(ref)  # Fail before any case mutation if unavailable.
    _check_directory(root)
    directory = root / ".recordprep"
    directory.mkdir(mode=0o700, exist_ok=True)
    _check_directory(directory, private=True)
    lock = directory / ".practice-profile.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        _private_file(lock)
        fcntl.flock(fd, fcntl.LOCK_EX)
        if read_case_profile_ref(root) != expected_previous:
            raise ProfileError("stale_case_selection", "case")
        store.load_profile_snapshot(ref)
        _atomic_json(directory / "practice-profile.json", {"schema_version": 1, "profile_ref": asdict(ref)})
    finally:
        os.close(fd)
