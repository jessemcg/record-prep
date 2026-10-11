"""Explicit, private, app-owned profile acceptance; no launch-time writes.

Vendored identically in both applications. Store construction and snapshot reads
are read-only. Only accept_profile and set_default publish application state.
"""
from __future__ import annotations

import fcntl
import os
import shutil
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .profile_contract import (
    MAX_FILE_BYTES, ProfileError, ProfileRef, ProfileSnapshot, RESOURCE_TYPES,
    _json, _object, _require, json_bytes, read_file_at, validate_contents,
    validate_profile_directory,
)


def _check_directory(path: Path, *, private: bool = False) -> None:
    """Reject symlink ancestors too; never chmod an existing user directory."""
    for parent in (*reversed(path.parents), path):
        info = parent.lstat()
        _require(stat.S_ISDIR(info.st_mode), "unsafe_store_directory", "storage")
    if private:
        info = path.stat()
        _require(info.st_uid == os.getuid() and not info.st_mode & 0o077,
                 "store_permissions", "storage")


def _private_directory(path: Path) -> None:
    if not path.exists():
        _check_directory(path.parent)
        path.mkdir(mode=0o700, exist_ok=True)
    _check_directory(path, private=True)


def _ensure_root(path: Path) -> None:
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    _check_directory(current)
    for directory in reversed(missing):
        _private_directory(directory)
    _check_directory(path, private=True)


def _private_file(path: Path) -> None:
    info = path.lstat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
             and not info.st_mode & 0o177, "store_permissions", "storage")


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path: Path, value: dict) -> None:
    data = json_bytes(value)
    _require(len(data) <= MAX_FILE_BYTES, "registry_full", "registry")
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ProfileStore:
    def __init__(self, application: str, *, config_root: Path, data_root: Path):
        _require(application in RESOURCE_TYPES, "wrong_application", "application")
        _require(config_root.is_absolute() and data_root.is_absolute(), "absolute_store_required", "storage")
        self.application = application
        self.config_root = config_root
        self.data_root = data_root
        self.registry_path = config_root / "registry.json"

    def _empty_registry(self) -> dict:
        return {"schema_version": 1, "application": self.application, "accepted": [], "heads": {}, "default": None}

    def read_registry(self) -> dict:
        """Missing is empty; malformed or unsafe is an error, never reset."""
        if not self.config_root.exists():
            # A dangling symlink is not an absent store.
            _require(not self.config_root.is_symlink(), "unsafe_store_directory", "storage")
            return self._empty_registry()
        _check_directory(self.config_root, private=True)
        if not self.registry_path.exists():
            _require(not self.registry_path.is_symlink(), "store_permissions", "storage")
            return self._empty_registry()
        _private_file(self.registry_path)
        fd = os.open(self.config_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            value = _json(read_file_at(fd, "registry.json"), "registry")
        finally:
            os.close(fd)
        _object(value, {"schema_version", "application", "accepted", "heads", "default"}, "registry")
        _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
                 "unsupported_version", "registry")
        _require(value["application"] == self.application, "wrong_application", "registry")
        _require(isinstance(value["accepted"], list) and len(value["accepted"]) <= 256,
                 "invalid_registry", "registry")
        refs = {}
        for entry in value["accepted"]:
            _object(entry, {"ref", "source"}, "registry")
            ref = ProfileRef.from_dict(entry["ref"])
            _require(ref.application == self.application, "wrong_application", "registry")
            _require(ref.content_sha256 not in refs, "duplicate_revision", "registry")
            _require(entry["source"] is None or (isinstance(entry["source"], str) and
                     len(entry["source"]) <= 4096 and Path(entry["source"]).is_absolute()),
                     "invalid_registry", "registry")
            refs[ref.content_sha256] = ref
        _require(isinstance(value["heads"], dict), "invalid_registry", "registry")
        for specialty, digest in value["heads"].items():
            _require(isinstance(digest, str) and digest in refs and refs[digest].specialty_id == specialty,
                     "invalid_registry", "registry")
        _require(set(value["heads"]) == {ref.specialty_id for ref in refs.values()},
                 "invalid_registry", "registry")
        if value["default"] is not None:
            default = ProfileRef.from_dict(value["default"])
            _require(refs.get(default.content_sha256) == default, "unaccepted_reference", "registry")
        return value

    @contextmanager
    def _locked(self):
        _ensure_root(self.config_root)
        path = self.config_root / ".registry.lock"
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                     info.st_uid == os.getuid() and not info.st_mode & 0o177,
                     "store_permissions", "lock")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _read_snapshot(self, ref: ProfileRef) -> ProfileSnapshot:
        _require(ref.application == self.application, "wrong_application", "reference")
        path = self.data_root / "snapshots" / ref.content_sha256
        _check_directory(path, private=True)
        result = validate_profile_directory(path, self.application)
        if result.draft is None:
            raise ProfileError("invalid_snapshot", "snapshot")
        _require(result.draft.ref == ref, "snapshot_hash_mismatch", "snapshot")
        for relative, _ in result.draft.files:
            _check_directory((path / relative).parent, private=True)
            _private_file(path / relative)
        return result.draft

    def load_profile_snapshot(self, ref: ProfileRef) -> ProfileSnapshot:
        # Validate before using the digest in a path, even for directly
        # constructed dataclasses from a caller.
        ref = ProfileRef.from_dict(asdict(ref))
        registry = self.read_registry()
        _require(any(entry["ref"] == asdict(ref) for entry in registry["accepted"]),
                 "unaccepted_reference", "reference")
        try:
            return self._read_snapshot(ref)
        except OSError as exc:
            raise ProfileError("snapshot_unavailable", "snapshot") from exc

    def _publish_snapshot(self, draft: ProfileSnapshot) -> None:
        _ensure_root(self.data_root)
        snapshots = self.data_root / "snapshots"
        _private_directory(snapshots)
        destination = snapshots / draft.ref.content_sha256
        if destination.exists() or destination.is_symlink():
            self._read_snapshot(draft.ref)
            return
        pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=snapshots))
        try:
            for relative, data in draft.files:
                target = pending / relative
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                # mkdir(parents=True) uses default mode for intermediate dirs.
                for directory in target.parent.relative_to(pending).parents:
                    if str(directory) != ".":
                        (pending / directory).chmod(0o700)
                with target.open("xb") as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            for directory, _dirs, _files in os.walk(pending, topdown=False):
                _fsync_directory(Path(directory))
            os.rename(pending, destination)
            _fsync_directory(snapshots)
        finally:
            if pending.exists():
                shutil.rmtree(pending)

    def accept_profile(self, draft: ProfileSnapshot, *, expected_previous_digest: str | None,
                       source_path: Path | None = None) -> ProfileRef:
        """CAS the accepted head; snapshot publication precedes registry commit.

        On interruption, an unregistered immutable snapshot may remain but is
        not authorized. Existing selections and snapshots are never overwritten.
        This accepts frozen draft bytes, not future edits in the source folder.
        """
        validated = validate_contents(draft.files, self.application)
        _require(validated.ref == draft.ref, "snapshot_hash_mismatch", "profile")
        if source_path is not None:
            _require(source_path.is_absolute() and len(str(source_path)) <= 4096,
                     "absolute_source_required", "source")
        with self._locked():
            registry = self.read_registry()
            current = registry["heads"].get(draft.ref.specialty_id)
            _require(current == expected_previous_digest, "stale_profile_revision", "registry")
            self._publish_snapshot(validated)
            if not any(entry["ref"] == asdict(draft.ref) for entry in registry["accepted"]):
                _require(len(registry["accepted"]) < 256, "registry_full", "registry")
                registry["accepted"].append({"ref": asdict(draft.ref),
                                             "source": str(source_path) if source_path else None})
            elif source_path is not None:
                # Explicit re-registration may attach/repoint a reviewed source
                # folder; immutable bytes and existing case refs do not change.
                for entry in registry["accepted"]:
                    if entry["ref"] == asdict(draft.ref):
                        entry["source"] = str(source_path)
            registry["heads"][draft.ref.specialty_id] = draft.ref.content_sha256
            _atomic_json(self.registry_path, registry)
        return draft.ref

    def set_default(self, ref: ProfileRef) -> None:
        with self._locked():
            self.load_profile_snapshot(ref)
            registry = self.read_registry()
            registry["default"] = asdict(ref)
            _atomic_json(self.registry_path, registry)
