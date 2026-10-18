"""Application-selected preparation guidance; bundles never authorize instructions.

Historical pins remain readable as provenance only. Compatibility function names
are retained for stage callers, but current selection belongs to the profile store.
"""
from __future__ import annotations

import fcntl
import os
import stat
from dataclasses import asdict
from contextlib import contextmanager
from pathlib import Path

from .practice_profiles import profile_store
from .profile_artifacts import preparation_selection
from .profile_contract import ProfileError, ProfileRef, ProfileSnapshot, _json, _require, read_file_at
from .profile_store import ProfileStore, _atomic_json, _check_directory


def _case_directory(path: Path) -> None:
    """Case metadata may sync with 0755/0775 modes; private stores stay strict."""
    _check_directory(path)
    info = path.stat()
    _require(info.st_uid == os.getuid() and not info.st_mode & 0o002,
             "unsafe_case_profile_directory", "case")


def _case_file(path: Path) -> None:
    info = path.lstat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
             and info.st_uid == os.getuid() and not info.st_mode & 0o113,
             "unsafe_case_profile_file", "case")


def read_historical_case_profile_ref(root: Path) -> ProfileRef | None:
    directory = root / ".recordprep"
    path = directory / "practice-profile.json"
    if not directory.exists() and not directory.is_symlink():
        return None
    _case_directory(directory)
    if not path.exists() and not path.is_symlink():
        return None
    _case_file(path)
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            return preparation_selection(_json(read_file_at(fd, "practice-profile.json"), "case_selection"))
        finally:
            os.close(fd)
    except OSError as exc:
        raise ProfileError("unreadable_case_selection", "case") from exc


def resolve_case_profile(root: Path, *, store: ProfileStore | None = None) -> ProfileSnapshot:
    """Freeze the application selection, ignoring even malformed historical pins."""
    from .practice_profiles import default_profile_candidate
    return default_profile_candidate(store=store or profile_store())


def read_case_profile_ref(root: Path) -> ProfileRef | None:
    """Current generation selection (the root is not an instruction source)."""
    profile = resolve_case_profile(root)
    return profile.ref if profile is not None else None


@contextmanager
def case_profile_publication(root: Path, expected: ProfileRef | None):
    """Serialize publishers and current settings changes, never model work.

    The historical lock filename is retained for concurrent-publisher safety.
    Creating this lock never creates a profile pin; read-only checks do not call it.
    """
    directory = root / ".recordprep"
    directory.mkdir(mode=0o700, exist_ok=True)
    _case_directory(directory)
    lock = directory / ".practice-profile.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        _case_file(lock)
        opened, current = os.fstat(fd), lock.stat()
        _require((opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino),
                 "unsafe_case_profile_file", "case")
        fcntl.flock(fd, fcntl.LOCK_EX)
        # Serialize publication against local settings saves/selections as well
        # as other publishers. A synchronized store is single-writer across hosts.
        store = profile_store()
        with store._locked():
            profile = resolve_case_profile(root, store=store)
            if (profile.ref if profile is not None else None) != expected:
                raise ProfileError("stale_case_selection", "publication")
            yield
    finally:
        os.close(fd)


def apply_case_profile(root: Path, ref: ProfileRef, *, expected_previous: ProfileRef | None,
                       store: ProfileStore | None = None) -> None:
    """Compatibility selection API: update application settings, never the bundle."""
    store = store or profile_store()
    if ref.application != "recordprep" or store.application != "recordprep":
        raise ProfileError("wrong_application", "case")
    with store._locked():
        store.load_profile_snapshot(ref)
        registry = store.read_registry()
        previous = ProfileRef.from_dict(registry["default"]) if registry["default"] else None
        if previous != expected_previous:
            raise ProfileError("stale_case_selection", "selection")
        _require(ref.specialty_id not in registry.get("deleted", []), "deleted_profile", "selection")
        registry["default"] = asdict(ref)
        _atomic_json(store.registry_path, registry)
