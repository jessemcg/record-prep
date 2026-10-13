"""Frozen native-stage profile composition and participant freshness."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .profile_contract import ProfileSnapshot, compile_stage_profile
from .summary_profiles import CORE

PARTICIPANT_CORE = """\nPARTICIPANTS
Index one hearing at a time from original single source pages. Keep counsel,
non-counsel participants and witnesses separate. Identify anyone established as
present, appearing remotely or speaking, and preserve expressly recorded absences.
Use source-supported descriptive role_label text and, for counsel, represents text;
there is no specialty role catalog or role_id. Preserve observed names and speaker
aliases, including unnamed speakers with unresolved identity. Do not assume an area
of law, party structure, parentage, custody or legal status. Organizations are not
aliases. Do not carry roles across hearings without evidence. Counsel representation
is not proof of personal attendance; an omitted name is not proof of absence.
Q/A alone is not sworn testimony. Preserve attendance, speaking, sworn and witness
uncertainty. Mere references to a person do not establish participation.
Verified witnesses require source-backed examinations within the hearing. Counsel
as a witness requires explicit conflict treatment. Retain source citations and
safe text_pages paths. Do not concatenate whole transcripts. Validate incrementally.
Only the runner publishes the final artifact after independent validation.
"""
OVERVIEW_CORE = """\nOVERVIEW
Use the fixed practice-neutral orientation method in the loaded skill. Read every
current validated summary completely, continuing after truncated reads. Substantive
facts come only from those summaries; participant metadata is for identity, roles
and representation only. Identify central parties, the posture as of the latest
supplied materials, material chronological events, neutrally attributed disputes and
record scope/gaps. Distinguish allegations, party positions, evidence and actual
rulings; never assume an appeal or infer nonoccurrence from silence. No outside
knowledge, legal analysis, outcome prediction, word cap or event quota. Do not infer
attendance or testimony from a missing participant index in CT-only records. Source
pages remain factual authority; this overview is never evidence. Preserve the
existing overview frontmatter, disclaimer and five headings.
Only the runner publishes after validating the private candidate.
"""


def compile_native(profile: ProfileSnapshot, stage: str, project_dir: Path):
    if stage not in ("participants", "overview"):
        raise ValueError("Unsupported native profile stage.")
    core = CORE + (PARTICIPANT_CORE if stage == "participants" else OVERVIEW_CORE)
    template = project_dir / "resources" / f"profile-{stage}.md"
    dependencies = [template, project_dir / "extensions/recordprep-profile-native-tools.ts"]
    if stage == "participants":
        dependencies.append(project_dir / "skills/recordprep-build-participant-index/scripts/participant_index.py")
    core_bytes = core.encode() + b"\0" + b"\0".join(path.read_bytes() for path in dependencies)
    compiled = compile_stage_profile(profile, stage, core_contract=core_bytes)
    prompt = core
    if compiled.resources:
        prompt += "\nPRACTICE GUIDANCE (subordinate):\n" + "\n\n".join(
            name + "\n" + data.decode("utf-8") for name, data in compiled.resources)
    provenance = {"schema_version": 1, "profile_ref": asdict(profile.ref), "components": {stage: compiled.component_sha256}}
    return prompt, provenance


def prepare_participant_context(profile: ProfileSnapshot, root: Path, project_dir: Path, workspace: Path):
    """Run only the application's own helper, never a case/profile executable."""
    import importlib.util
    path = project_dir / "skills/recordprep-build-participant-index/scripts/participant_index.py"
    spec = importlib.util.spec_from_file_location("_recordprep_owned_participant_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate = workspace / "participant-candidate.json"
    worklist = workspace / "participant-worklist.json"
    module.prepare(root, profile=profile, candidate_path=candidate, project_dir=project_dir)
    module.worklist(root, output_path=worklist)
    candidate.chmod(0o600)
    worklist.chmod(0o600)
    return candidate, worklist


def participant_input_paths(root: Path) -> list[Path]:
    paths = [root / "artifacts/hearing_boundaries.json", root / "artifacts/transcript_page_numbers.json",
             root / "artifacts/transcript_layout.json"]
    # Worklist index scoping reads the first nonempty recognized classifier file.
    # Include each examined candidate so changing this navigation input cannot
    # reuse an old participant result merely because boundary bytes stayed equal.
    for name in ("RT_basic_advanced_corrected_dates_names.jsonl", "CT_basic_advanced_corrected_dates_names.jsonl",
                 "final.jsonl", "final_classification.jsonl", "combined.jsonl"):
        path = root / "classification" / name
        if not path.is_file():
            continue
        paths.append(path)
        found = False
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                found = found or isinstance(json.loads(line), dict)
            except json.JSONDecodeError:
                pass
        if found:
            break
    # Numbering owns source identity; include all reporter pages, including RT indexes.
    transcript = json.loads(paths[1].read_text(encoding="utf-8"))
    for entry in transcript.get("entries", []):
        if isinstance(entry, dict) and str(entry.get("record_type", "")).upper() == "RT":
            number = entry.get("file_page")
            if type(number) is not int or number < 1:
                raise ValueError("Invalid reporter page identity.")
            paths.append(root / "text_pages" / f"{number:04d}.txt")
    for boundary in json.loads(paths[0].read_text(encoding="utf-8")):
        start = int(str(boundary["start_page"]).removesuffix(".txt"))
        end = int(str(boundary["end_page"]).removesuffix(".txt"))
        if start < 1 or end < start:
            raise ValueError("Invalid hearing source range.")
        paths.extend(root / "text_pages" / f"{number:04d}.txt" for number in range(start, end + 1))
    return sorted(set(paths))


def participant_input_digest(root: Path) -> str:
    digest = hashlib.sha256(b"recordprep-participant-inputs-v1\0")
    for path in participant_input_paths(root):
        data = path.read_bytes()
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def native_runtime_digest(project_dir: Path) -> str:
    from .pi_runtime import resolve_stage_model_identity
    from .minute_summaries import _global_settings_path
    from .summary_agents import _resource_sha256, sha256_json
    identity = resolve_stage_model_identity({}, "native", project_dir / "settings.json")
    return sha256_json({"provider": identity.provider, "model": identity.model_id, "thinking": identity.thinking,
                       "inherited": _resource_sha256(_global_settings_path()) if not all((identity.provider, identity.model_id, identity.thinking)) else None,
                       "system": _resource_sha256(project_dir / "SYSTEM.md"),
                       "auto_exit": _resource_sha256(project_dir / "extensions/recordprep-auto-exit.ts"),
                       "application": {name: _resource_sha256(Path(__file__).parent / name) for name in
                                       ("native_profiles.py", "pi_bundle.py", "profile_artifacts.py", "profile_contract.py", "boundary_profiles.py")},
                       "runner": _resource_sha256(project_dir / "scripts/run_recordprep_skill.py")})


def participant_metadata(profile: ProfileSnapshot, root: Path, project_dir: Path) -> dict:
    from .boundary_profiles import require_current_boundaries
    require_current_boundaries(root, profile, project_dir)
    return {"schema_version": 4,
            "profile_provenance": compile_native(profile, "participants", project_dir)[1],
            "input_sha256": participant_input_digest(root), "runtime_sha256": native_runtime_digest(project_dir)}


def participant_freshness_issues(root: Path, profile: ProfileSnapshot, project_dir: Path) -> list[str]:
    try:
        payload = json.loads((root / "artifacts/participant_index.json").read_text(encoding="utf-8"))
        expected = participant_metadata(profile, root, project_dir)
        if (payload.get("schema_version") != 4 or "role_catalog" in payload
                or payload.get("input_sha256") != expected["input_sha256"]
                or payload.get("runtime_sha256") != expected["runtime_sha256"]
                or payload.get("profile_provenance", {}).get("components") != expected["profile_provenance"]["components"]):
            return ["Participant index requires regeneration for the selected profile/source inputs."]
    except (OSError, ValueError, AttributeError):
        return ["Participant index freshness is unproven for the selected profile."]
    return []


def overview_input_digest(root: Path) -> str:
    from . import summary_agents as sa, minute_summaries as minutes
    from .transcript_layout import is_ct_only
    paths = [root / "artifacts/transcript_layout.json"]
    for kind in ("hearings", "reports", "minutes"):
        paths.append(sa.summary_final_path(root, kind))
        paths.append(minutes.meta_path(root) if kind == "minutes" else sa.summary_final_meta_path(root, kind))
    if not is_ct_only(root):
        paths.append(root / "artifacts/participant_index.json")
    digest = hashlib.sha256(b"recordprep-overview-inputs-v1\0")
    for path in paths:
        data = path.read_bytes()
        digest.update(str(path.relative_to(root)).encode() + b"\0" + len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def overview_metadata(profile: ProfileSnapshot, root: Path, project_dir: Path, text: str) -> dict:
    return {"schema_version": 1, "profile_provenance": compile_native(profile, "overview", project_dir)[1],
            "input_sha256": overview_input_digest(root), "overview_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "runtime_sha256": native_runtime_digest(project_dir)}


def overview_freshness_issues(root: Path, profile: ProfileSnapshot, project_dir: Path) -> list[str]:
    try:
        text = (root / "artifacts/case_overview.md").read_text(encoding="utf-8")
        metadata = json.loads((root / "artifacts/case_overview.profile.json").read_text(encoding="utf-8"))
        expected = overview_metadata(profile, root, project_dir, text)
        if (metadata.get("schema_version") != 1 or metadata.get("input_sha256") != expected["input_sha256"]
                or metadata.get("overview_sha256") != expected["overview_sha256"]
                or metadata.get("runtime_sha256") != expected["runtime_sha256"]
                or metadata.get("profile_provenance", {}).get("components") != expected["profile_provenance"]["components"]):
            return ["Case overview requires regeneration for the selected profile or prepared inputs."]
    except (OSError, ValueError, AttributeError):
        return ["Case overview profile freshness is unproven."]
    return []
