"""Profile-era boundary publication and provenance, independent of GUI state."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .case_profiles import read_case_profile_ref, case_profile_publication
from .classification_profiles import _digest, component
from .summary_agents import _atomic_write
from .profile_contract import read_file_at, _json

FILES = ("hearing_boundaries.json", "report_boundaries.json", "minutes_boundaries.json")


def boundary_inputs(root, profile, settings, *, verify_source_bytes=True):
    if profile is None:
        return None
    # Freeze actual inputs for this run, not the settings that created them.
    # Old markers and filesystem timestamps never authorize or block a new run.
    from .classification_profiles import prepared_classification_digest
    return {"contract_version": 3,
            "classification_sha256": prepared_classification_digest(root, "names"),
            "classification_component": component(profile, "basic"),
            "naming_component": component(profile, "names")}


def publish_boundaries(root: Path, profile, expected_inputs, settings: dict, payloads: dict):
    if set(payloads) != set(FILES) or any(not isinstance(value, list) for value in payloads.values()):
        raise ValueError("Invalid application boundary publication contract.")
    if profile is not None:
        if read_case_profile_ref(root) != profile.ref or boundary_inputs(root, profile, settings) != expected_inputs:
            raise ValueError("Preparation selection or classifier inputs changed; prior boundaries preserved.")
    outputs = {name: json.dumps(payloads[name], indent=2) for name in FILES}
    with case_profile_publication(root, profile.ref if profile is not None else None):
        for name, text in outputs.items():
            _atomic_write(root / "artifacts" / name, text)
        if profile is not None:
            metadata = {"schema_version": 1, "profile_ref": asdict(profile.ref), "inputs": expected_inputs,
                        "outputs": {name: _digest(root / "artifacts" / name) for name in FILES}}
            _atomic_write(root / "artifacts/profile-boundaries.json", json.dumps(metadata, sort_keys=True) + "\n")


def _read_metadata(root, filename):
    fd = os.open(root / "artifacts", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        value = _json(read_file_at(fd, filename, limit=65536), "derived_profile_metadata")
        if not isinstance(value, dict):
            raise ValueError("Invalid derived profile metadata.")
        return value
    finally:
        os.close(fd)


def boundary_issues(root: Path, profile, settings: dict) -> list[str]:
    try:
        value = _read_metadata(root, "profile-boundaries.json")
        expected = boundary_inputs(root, profile, settings, verify_source_bytes=False)
        if value.get("schema_version") != 1 or value.get("inputs") != expected or set(value.get("outputs", {})) != set(FILES):
            raise ValueError("Boundary profile inputs changed.")
        if any(_digest(root / "artifacts" / name) != digest for name, digest in value["outputs"].items()):
            raise ValueError("Boundary output changed.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ["Document boundaries require regeneration for the selected profile and classifier outputs."]
    return []


def preparation_watch_paths(root):
    paths = [root / "artifacts/profile-boundaries.json", root / "artifacts/profile-toc.json"]
    for name in ("classification", "image_pages", "text_pages"):
        directory = root / name
        paths.append(directory)
        if directory.is_dir() and not directory.is_symlink():
            paths.extend(path for path in directory.iterdir() if path.is_file() and not path.is_symlink())
    return paths


def require_current_boundaries(root, profile, project_dir, *, verify_source_bytes=False):
    """Compatibility hook: historical freshness is not a downstream prerequisite.

    Each consumer loads and validates its own actual boundary/source inputs. Do not
    require classification, profile-boundaries metadata, old models or timestamps
    here, nor unrelated boundary kinds (hearing work does not need report inputs).
    The runner's frozen input fingerprints still protect publication and row reuse.
    """
    return


def publish_toc(root, profile, expected_inputs, settings, text):
    if profile is not None and (read_case_profile_ref(root) != profile.ref or boundary_inputs(root, profile, settings) != expected_inputs):
        raise ValueError("Preparation selection or classifier inputs changed; prior TOC preserved.")
    with case_profile_publication(root, profile.ref if profile is not None else None):
        _atomic_write(root / "artifacts/toc.txt", text)
        if profile is not None:
            metadata = {"schema_version": 1, "profile_ref": asdict(profile.ref), "inputs": expected_inputs,
                        "toc_sha256": _digest(root / "artifacts/toc.txt")}
            _atomic_write(root / "artifacts/profile-toc.json", json.dumps(metadata, sort_keys=True) + "\n")


def toc_issues(root, profile, settings):
    try:
        metadata = _read_metadata(root, "profile-toc.json")
        if (metadata.get("schema_version") != 1
                or metadata.get("inputs") != boundary_inputs(root, profile, settings, verify_source_bytes=False)
                or metadata.get("toc_sha256") != _digest(root / "artifacts/toc.txt")):
            raise ValueError("TOC metadata is stale.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ["TOC requires regeneration or explicit review for the selected profile and classifier outputs."]
    return []
