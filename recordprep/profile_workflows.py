"""Explicit profile-authoring transactions, vendored independently in both apps.

No discovery, launch-time writes, case selection, or default changes. Editors keep
complete frozen drafts in memory; Save publishes a new folder, never overwrites a
user folder, and accepts only after all bytes have been validated and published.
"""
from __future__ import annotations

import ctypes
import errno
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .profile_contract import (
    ProfileError, ProfileRef, ProfileSnapshot, RESOURCE_TYPES, _manifest, _require,
    identity_descriptor, json_bytes, parse_identity_descriptor, validate_contents,
    validate_profile_directory,
)
from .profile_store import ProfileStore, _check_directory, _fsync_directory


@dataclass(frozen=True)
class ProfileCandidate:
    snapshot: ProfileSnapshot
    personal: bool = False
    notice: str = ""


def current_catalog(store, bundled, *, known_baselines=(), customization=None):
    """Read-only: one current entry per identity, no revision discovery in UI.

    Exact known bundled bytes distinguish old ordinary acceptance from personal
    edits. Optional ownership metadata is only written by an explicit action.
    Existing personal settings never receive a second legacy overlay.
    """
    registry = store.read_registry()
    baselines = set(known_baselines) | {snapshot.ref.content_sha256 for snapshot in bundled}
    result = []
    seen = set()
    accepted = {entry["ref"]["content_sha256"]: entry["ref"] for entry in registry["accepted"]}
    for snapshot in bundled:
        identity = snapshot.ref.specialty_id
        head = registry["heads"].get(identity)
        personal = identity in registry.get("personal", []) or (head is not None and head not in baselines)
        if personal:
            snapshot = store.load_profile_snapshot(ProfileRef.from_dict(accepted[head]))
        notice = ""
        if not personal and identity not in registry.get("initialized", []) and customization:
            candidate = customization(snapshot)
            if candidate is not None:
                snapshot, notice = candidate
                personal = snapshot.ref.content_sha256 not in baselines
        result.append(ProfileCandidate(snapshot, personal, notice))
        seen.add(identity)
    for identity, head in registry["heads"].items():
        if identity not in seen and identity not in registry.get("deleted", []):
            result.append(ProfileCandidate(store.load_profile_snapshot(ProfileRef.from_dict(accepted[head])), True))
    return result


def checked_folder(path: Path, application: str) -> ProfileSnapshot:
    result = validate_profile_directory(path, application)
    if result.draft is None:
        issue = result.issues[0]
        raise ProfileError(issue.code, issue.location)
    return result.draft


def _destination(path: Path) -> None:
    _require(path.is_absolute() and path.name not in ("", ".", ".."),
             "absolute_destination_required", "export")
    _check_directory(path.parent)
    _require(not path.exists() and not path.is_symlink(), "destination_exists", "export")


def _publish_new_directory(pending: Path, destination: Path) -> None:
    """Linux atomic no-replace rename, including when the target is empty."""
    rename = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    _require(rename is not None, "atomic_export_unavailable", "export")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if rename(fd, os.fsencode(pending.name), fd, os.fsencode(destination.name), 1):
            code = ctypes.get_errno()
            if code == errno.EEXIST:
                raise ProfileError("destination_exists", "export")
            raise ProfileError("export_publication_failed", "export")
        os.fsync(fd)
    finally:
        os.close(fd)


def export_profile(snapshot: ProfileSnapshot, destination: Path) -> None:
    validated = validate_contents(snapshot.files, snapshot.ref.application)
    _require(validated.ref == snapshot.ref, "snapshot_hash_mismatch", "export")
    _destination(destination)
    pending = Path(tempfile.mkdtemp(prefix=".profile-export-", dir=destination.parent))
    try:
        for relative, data in validated.files:
            target = pending / relative
            current = pending
            for part in Path(relative).parts[:-1]:
                current /= part
                current.mkdir(mode=0o700, exist_ok=True)
            with target.open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        _require(checked_folder(pending, snapshot.ref.application).ref == snapshot.ref,
                 "snapshot_hash_mismatch", "export")
        for directory, _dirs, _files in os.walk(pending, topdown=False):
            _fsync_directory(Path(directory))
        _publish_new_directory(pending, destination)
    finally:
        if pending.exists():
            shutil.rmtree(pending)


def export_identity(snapshot: ProfileSnapshot, destination: Path) -> None:
    data = identity_descriptor(snapshot)
    _destination(destination)
    # Exclusive creation deliberately refuses overwriting even an empty file.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(destination.parent)


@dataclass(frozen=True)
class ReviewedFolder:
    draft: ProfileSnapshot
    source: Path
    expected_head: str | None

    @classmethod
    def inspect(cls, store: ProfileStore, source: Path) -> ReviewedFolder:
        draft = checked_folder(source, store.application)
        return cls(draft, source, store.read_registry()["heads"].get(draft.ref.specialty_id))

    def accept(self, store: ProfileStore) -> ProfileRef:
        current = checked_folder(self.source, store.application)
        _require(current.ref == self.draft.ref, "external_profile_changed", "review")
        return store.accept_profile(self.draft, expected_previous_digest=self.expected_head,
                                    source_path=self.source)


class ProfileEditor:
    """Toolkit-independent editable values; cancellation has no storage effects."""

    def __init__(self, base: ProfileSnapshot, *, source: Path | None = None):
        self.base = validate_contents(base.files, base.ref.application)
        _require(self.base.ref == base.ref, "snapshot_hash_mismatch", "editor")
        self.source = source
        self.manifest = base.manifest
        self.resources = {name: base.resource(name) for name in self.manifest["resources"]}

    @classmethod
    def create(cls, base: ProfileSnapshot, display_name: str, *, identity: bytes | None = None) -> ProfileEditor:
        editor = cls(base)
        descriptor = parse_identity_descriptor(identity) if identity is not None else None
        editor.manifest.update({"specialty_id": descriptor["specialty_id"] if descriptor else f"custom-{uuid.uuid4()}",
                                "display_name": descriptor["display_name"] if descriptor else display_name,
                                "description": descriptor["description"] if descriptor else base.manifest["description"],
                                "version": "1.0.0"})
        return editor

    def snapshot(self) -> ProfileSnapshot:
        originals = dict(self.base.files)
        manifest_bytes = (originals["profile.json"] if self.manifest == self.base.manifest
                          else json_bytes(self.manifest))
        _manifest(manifest_bytes, self.base.ref.application)
        files = {"profile.json": manifest_bytes}
        for name, relative in self.manifest["resources"].items():
            _require(name in self.resources, "missing_resource", name)
            value = self.resources[name]
            if RESOURCE_TYPES[self.base.ref.application][name] == "md":
                _require(isinstance(value, str), "invalid_text", name)
            if relative == self.base.manifest["resources"].get(name) and value == self.base.resource(name):
                files[relative] = originals[relative]
            else:
                files[relative] = json_bytes(value) if RESOURCE_TYPES[self.base.ref.application][name] == "json" else value.encode("utf-8")
        return validate_contents(tuple(files.items()), self.base.ref.application)

    def managed_save(self, store: ProfileStore, *, expected_head, expected_default,
                     validate, can_modify, use_for_new_cases=None, personal=True):
        draft = self.snapshot()
        validate(draft)  # Real application compilers, never validation-only UI.
        self._check_source()
        return store.managed_save(draft, expected_head=expected_head,
                                  expected_default=expected_default,
                                  use_for_new_cases=use_for_new_cases,
                                  personal=personal, can_modify=can_modify)

    def _check_source(self) -> None:
        if self.source is not None:
            _require(checked_folder(self.source, self.base.ref.application).ref == self.base.ref,
                     "external_profile_changed", "editor")

    def save(self, store: ProfileStore, destination: Path, *, expected_head: str | None) -> ProfileRef:
        draft = self.snapshot()
        _require(store.application == draft.ref.application, "wrong_application", "editor")
        self._check_source()
        _require(store.read_registry()["heads"].get(draft.ref.specialty_id) == expected_head,
                 "stale_profile_revision", "editor")
        export_profile(draft, destination)
        # A competing acceptance or external edit preserves the exported draft
        # for recovery, but must not authorize it, select it, or change defaults.
        self._check_source()
        reviewed = ReviewedFolder(draft, destination, expected_head)
        return reviewed.accept(store)
