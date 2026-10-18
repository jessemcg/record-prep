"""Deterministic profile-era source-map publication; no model or profile code runs."""
from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict
from pathlib import Path

from .case_profiles import read_case_profile_ref, case_profile_publication
from .classification_profiles import component, _digest
from .boundary_profiles import _read_metadata
from .profile_artifacts import source_map_profile_metadata
from .summary_profiles import compile_summary
from .native_profiles import compile_native
from . import summary_agents as sa, minute_summaries as minutes
from .transcript_layout import is_ct_only


def provenance(profile, root, project_dir):
    components = {"classification": component(profile, "basic"), "naming": component(profile, "names")}
    for kind in ("hearings", "reports"):
        for phase in ("extract", "synthesize"):
            components.update(compile_summary(profile, kind, phase).provenance["components"])
    components.update(minutes._profile_provenance(profile)["components"])
    components.update(compile_native(profile, "overview", project_dir)[1]["components"])
    if not is_ct_only(root):
        components.update(compile_native(profile, "participants", project_dir)[1]["components"])
    return {"schema_version": 1, "profile_ref": asdict(profile.ref), "components": components}


def prepared_input_issues(root, profile, project_dir):
    issues = []
    for name in ("hearing_boundaries.json", "report_boundaries.json", "minutes_boundaries.json"):
        try:
            if not isinstance(json.loads((root / "artifacts" / name).read_text()), list):
                raise ValueError("Expected a boundary list")
        except (OSError, ValueError):
            issues.append(f"{name} is missing or unreadable.")
    try:
        (root / "artifacts/toc.txt").read_text()
    except (OSError, ValueError):
        issues.append("toc.txt is missing or unreadable.")
    return issues


def input_digest(root, profile, project_dir, *, verify_source_bytes):
    paths = [root / "artifacts" / name for name in (
        "transcript_layout.json", "transcript_page_numbers.json", "transcript_page_number_series.md",
        "hearing_boundaries.json", "report_boundaries.json", "minutes_boundaries.json",
        "toc.txt", "case_overview.md")]
    paths.extend(sorted((root / "text_pages").glob("*.txt")))
    for kind in ("hearings", "reports", "minutes"):
        paths.append(sa.summary_final_path(root, kind))
    if not is_ct_only(root):
        paths.append(root / "artifacts/participant_index.json")
    if (root / "case_name.txt").exists():
        paths.append(root / "case_name.txt")
    return sa.sha256_json({"contract_version": 2,
                           "files": {str(path.relative_to(root)): _digest(path) for path in paths},
                           "publisher": _digest(project_dir / "skills/recordprep-build-source-map/scripts/build_source_map.py")})


def publication_issues(root, profile, project_dir):
    try:
        marker = _read_metadata(root, "source_map.profile.json")
        expected = provenance(profile, root, project_dir)
        if (marker.get("schema_version") != 1 or marker.get("input_sha256") != input_digest(root, profile, project_dir, verify_source_bytes=False)
                or marker.get("map_sha256") != _digest(root / "artifacts/source_map.json")
                or marker.get("components") != expected["components"]):
            raise ValueError("Publication inputs changed.")
        recorded = _read_metadata(root, "practice_profile_provenance.json")
        # Publication and consumed map provenance must agree exactly, even when
        # an unrelated selected revision may reuse identical stage components.
        source_map = json.loads((root / "artifacts/source_map.json").read_text())
        if source_map_profile_metadata(source_map) != recorded or recorded["components"] != expected["components"]:
            raise ValueError("Publication provenance disagrees with the consumed map.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ["Source map requires profile-aware publication for the current prepared inputs."]
    return []


def publish_source_map(root, profile, project_dir):
    from .pi_bundle import source_map_prerequisite_issues
    issues = source_map_prerequisite_issues(root, project_dir=project_dir)
    issues.extend(prepared_input_issues(root, profile, project_dir))
    if issues:
        raise ValueError("Source-map prerequisites failed: " + " ".join(dict.fromkeys(issues)))
    before = input_digest(root, profile, project_dir, verify_source_bytes=True)
    preparation = provenance(profile, root, project_dir)
    helper = project_dir / "skills/recordprep-build-source-map/scripts/build_source_map.py"
    spec = importlib.util.spec_from_file_location("recordprep_owned_source_map_publisher", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    empty = {"schema_version": 4, "source": "record-participant-index", "hearings": [],
             "profile_provenance": compile_native(profile, "participants", project_dir)[1],
             "applicability": "not_applicable_ct_only", "warnings": []}
    payload, manifest = module.build_source_map(root, preparation=preparation, empty_participants=empty)
    source_map_profile_metadata(payload)
    if (read_case_profile_ref(root) != profile.ref or input_digest(root, profile, project_dir, verify_source_bytes=True) != before
            or source_map_prerequisite_issues(root, project_dir=project_dir) or prepared_input_issues(root, profile, project_dir)):
        raise ValueError("Preparation selection or inputs changed; prior source map preserved.")
    output = root / "artifacts/source_map.json"
    with case_profile_publication(root, profile.ref):
        sa._atomic_write(output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        sa._atomic_write(root / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        sa._atomic_write(root / "artifacts/practice_profile_provenance.json", json.dumps(preparation, indent=2) + "\n")
        marker = {"schema_version": 1, "input_sha256": before, "map_sha256": _digest(output), "components": preparation["components"]}
        sa._atomic_write(root / "artifacts/source_map.profile.json", json.dumps(marker, indent=2) + "\n")
    # Never remove legacy artifacts as a side effect of adopting a profile.
    return payload
