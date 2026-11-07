"""One resumable native organization run, restricted inputs/private candidate.

The runner owns child execution/Stop. This module freezes and rechecks selection,
source bytes, contract, model and prior output, and publishes atomically under its
own lock. No manifest or physical-boundary writes.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import stat
from pathlib import Path

from . import motion_groups as groups
from .case_name_stage import _read, _sha, _model_settings
from .case_profiles import read_case_profile_ref, case_profile_publication
from .motion_guidance import ORGANIZATION_GUIDANCE, ORGANIZATION_CONTRACT
from .motion_pages import build_motion_boundaries, motion_preparation_available
from .profile_contract import _json
from .profile_store import _check_directory
from .skill_commands import skill_launch
from .summary_agents import _atomic_write

SKILL = "recordprep-organize-motion-papers"
EXTENSION = "recordprep-motion-organization-tools.ts"


class MotionPreparationUnavailable(ValueError):
    """Historical absence is distinct from corrupt or unreadable source inputs."""


def selected_inventory(root):
    from .classification_files import final_paths
    paths = [p for p in final_paths(root) if p.exists() or p.is_symlink()]
    if not paths:
        raise MotionPreparationUnavailable("Run final classification before Organize motion papers.")
    blobs = {str(p.relative_to(root)): _read(p, 32 * 1024 * 1024) for p in paths}
    rows = []
    for data in blobs.values():
        for line in data.decode("utf-8").splitlines():
            if line.strip():
                row = _json(line.encode(), "motion_inventory")
                if not isinstance(row, dict):
                    raise ValueError("Invalid final classification.")
                rows.append(row)
    if not motion_preparation_available(root, rows):
        raise MotionPreparationUnavailable("Motion preparation unavailable. Explicitly run motion recognition and naming before organization.")
    return groups.inventory_from_boundaries(build_motion_boundaries(rows, -1)), {n: _sha(b) for n, b in blobs.items()}


@contextmanager
def lock(root):
    directory = root / ".recordprep"
    directory.mkdir(mode=0o700, exist_ok=True)
    _check_directory(directory)
    path = directory / "motion-organization.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o077:
            raise ValueError("Unsafe motion organization lock.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Motion organization is already running; prior output preserved.") from None
        yield
    finally:
        os.close(fd)


def capture(root, project_dir):
    _check_directory(root)
    inventory, classification = selected_inventory(root)
    source_digest, sources = groups.source_fingerprint(root, inventory)
    prior = groups.load(root)  # Corruption is not legacy absence.
    resources = [project_dir / "SYSTEM.md", project_dir / "skills" / SKILL / "SKILL.md",
                 project_dir / "extensions" / EXTENSION, project_dir / "extensions/recordprep-auto-exit.ts",
                 Path(__file__), Path(groups.__file__), Path(__file__).with_name("motion_guidance.py"),
                 Path(__file__).with_name("skill_commands.py")]
    inputs = {"source_sha256": source_digest, "classification": classification,
              "sources": sources, "model": _model_settings(project_dir),
              "organization_contract": ORGANIZATION_CONTRACT, "guidance_sha256": _sha(ORGANIZATION_GUIDANCE.encode()),
              "resources": {str(p): _sha(_read(p, 8 * 1024 * 1024)) for p in resources}}
    stat = root.stat()
    ref = read_case_profile_ref(root)
    guard = {"root": [stat.st_dev, stat.st_ino], "inputs": inputs,
             "prior": groups.digest(prior) if prior is not None else None}
    return inventory, guard, ref


def is_current(root, project_dir):
    inventory, guard, _ = capture(root, project_dir)
    prior = groups.load(root)
    return prior is not None and prior["inventory"] == inventory and prior["inputs"] == guard["inputs"]


def stage_inputs(root, project_dir, workspace):
    inventory, guard, ref = capture(root, project_dir)
    reads = []
    inventory_path = workspace / "motion-inventory.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    inventory_path.chmod(0o600)
    reads.append(str(inventory_path))
    pages = []
    for paper in inventory:
        for number in range(paper["start_page"], paper["end_page"] + 1):
            path = workspace / f"source-{number:04d}.txt"
            path.write_bytes(_read(root / f"text_pages/{number:04d}.txt", 16 * 1024 * 1024))
            path.chmod(0o600)
            reads.append(str(path))
            pages.append({"paper_id": paper["paper_id"], "source_page": number, "path": str(path)})
    skill = workspace / ".pi/skills" / SKILL / "SKILL.md"
    reads.append(str(skill))
    candidate = workspace / "motion-organization-candidate.json"
    spec = workspace / "motion-organization-access.json"
    spec.write_text(json.dumps({"reads": reads, "candidate": str(candidate)}), encoding="utf-8")
    spec.chmod(0o600)
    prompt = skill_launch(SKILL, ORGANIZATION_GUIDANCE + "\nAPPLICATION INPUT MANIFEST (data):\n" +
                          json.dumps({"inventory": str(inventory_path), "pages": pages, "candidate": str(candidate)}, ensure_ascii=True) +
                          "\nRead only these exact paths, continuing offsets after truncation. Write only the private candidate.")
    if capture(root, project_dir)[1] != guard:
        raise ValueError("Motion inputs changed during staging; no model work started.")
    return guard, ref, candidate, spec, prompt


def publish(root, project_dir, guard, ref, candidate=None, *, check_stop=lambda: None):
    inventory, current, _ = capture(root, project_dir)
    if current != guard:
        raise ValueError("Motion inputs or prior output changed; prior grouping preserved.")
    proposal = None
    if candidate is not None:
        try:
            candidate_bytes = _read(candidate, 16 * 1024 * 1024)
        except ValueError as exc:
            if not isinstance(exc.__cause__, FileNotFoundError) or candidate.is_symlink():
                raise
        else:
            try:
                proposal = _json(candidate_bytes, "motion_candidate")
            except (UnicodeError, ValueError):
                pass  # Successful child, unusable JSON: honest singleton fallback.
        # Unsafe paths/unreadable source are genuine failures, not model quality.
    result = groups.normalize_candidate(proposal, inventory, guard["inputs"]["source_sha256"], inputs=guard["inputs"])
    check_stop()
    with case_profile_publication(root, ref):
        if capture(root, project_dir)[1] != guard:
            raise ValueError("Motion inputs changed before publication; prior grouping preserved.")
        check_stop()
        directory = root / "artifacts"
        directory.mkdir(mode=0o700, exist_ok=True)
        _check_directory(directory)
        _atomic_write(root / groups.PATH, json.dumps(result, ensure_ascii=True, indent=2) + "\n")
    return result


def run_stage(root, project_dir, execute, *, check_stop=lambda: None, log=lambda message: None):
    with lock(root):
        inventory, guard, ref = capture(root, project_dir)
        if is_current(root, project_dir):
            log("Motion organization unchanged; saved result reused, no model call.")
            return 0
        if not inventory:
            publish(root, project_dir, guard, ref, check_stop=check_stop)
            log("No selected motion papers; empty organization saved, no model call.")
            return 0
        return execute()
