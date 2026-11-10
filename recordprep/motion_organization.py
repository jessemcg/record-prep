"""Zero-model, locked and guarded publisher of classification-continuity packets."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import stat
import inspect
import tempfile
from pathlib import Path

from . import motion_groups as groups
from .case_name_stage import _read, _sha
from .motion_pages import build_motion_boundaries, continuous_selection, motion_preparation_available
from .profile_contract import _json, read_file_at
from .profile_store import _check_directory


class MotionPreparationUnavailable(ValueError):
    """Historical absence is distinct from corrupt or unreadable source inputs."""


def classification_rows(root):
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
    return rows, {n: _sha(b) for n, b in blobs.items()}


def selected_inventory(root, *, continuous=False, rows=None):
    """Named-only by default for historical readers; new work opts in explicitly."""
    classification = {}
    if rows is None:
        rows, classification = classification_rows(root)
    boundaries = continuous_selection(rows)[0] if continuous else build_motion_boundaries(rows, -1)
    return groups.inventory_from_boundaries(boundaries, allow_unnamed=continuous), classification


@contextmanager
def lock(root):
    _check_directory(root)
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


def capture(root, project_dir=None):
    _check_directory(root)
    rows, classification = classification_rows(root)
    boundaries, packets, findings = continuous_selection(rows)
    inventory = groups.inventory_from_boundaries(boundaries, allow_unnamed=True)
    source_digest, sources = groups.source_fingerprint(root, inventory)
    groups.load(root)  # Corruption is not legacy absence.
    resources = [Path(__file__).with_name(name) for name in (
        "motion_organization.py", "motion_pages.py", "motion_groups.py", "profile_artifacts.py",
        "classification_files.py", "report_pages.py")]
    from . import case_name_stage
    safety = {function.__name__: _sha(inspect.getsource(function).encode())
              for function in (case_name_stage._read, read_file_at, _check_directory)}
    inputs = {"source_sha256": source_digest, "classification": classification, "sources": sources,
              "organization_contract": groups.ORGANIZATION_CONTRACT,
              "resources": {p.name: _sha(_read(p, 8 * 1024 * 1024)) for p in resources},
              "safety": safety}
    info = root.stat()
    guard = {"root": [info.st_dev, info.st_ino], "inputs": inputs,
             "prior": groups.output_fingerprint(root)}
    result = groups.canonical_packets(inventory, packets, findings, source_digest, inputs=inputs)
    return result, guard


def is_current(root, project_dir=None):
    result, _ = capture(root, project_dir)
    return groups.load(root) == result


def _atomic_write(path, text, before_replace):
    """Unique O_EXCL temporary file: never follow a pre-existing temp link."""
    fd, name = tempfile.mkstemp(prefix=".motion-groups-", dir=path.parent)
    pending = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        before_replace()
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def publish(root, project_dir, guard, result, *, check_stop=lambda: None):
    check_stop()
    if capture(root, project_dir)[1] != guard:
        raise ValueError("Motion inputs or prior output changed; prior grouping preserved.")
    directory = root / "artifacts"
    directory.mkdir(mode=0o700, exist_ok=True)
    _check_directory(directory)
    check_stop()
    if capture(root, project_dir)[1] != guard:
        raise ValueError("Motion inputs changed before publication; prior grouping preserved.")
    check_stop()
    def before_replace():
        check_stop()
        if capture(root, project_dir)[1] != guard:
            raise ValueError("Motion inputs changed during publication; prior grouping preserved.")
        check_stop()

    _atomic_write(root / groups.PATH, json.dumps(result, ensure_ascii=True, indent=2) + "\n", before_replace)
    return result


def run_stage(root, project_dir=None, *, check_stop=lambda: None, log=lambda message: None):
    """No Pi discovery, candidate workspace, model settings, credentials or calls."""
    with lock(root):
        check_stop()
        log("Reading final classifications and selected motion source pages (Python).")
        result, guard = capture(root, project_dir)
        check_stop()
        if groups.load(root) == result:
            log("Motion organization unchanged; saved result reused, no model calls.")
            return 0
        publish(root, project_dir, guard, result, check_stop=check_stop)
        if not result["inventory"]:
            log("No usable named motion lead; classified fragments omitted (see grouping findings)." if result["findings"]
                else "Checked-zero motion selection; empty organization saved, no model calls.")
        else:
            log(f"Motion organization complete: {len(result['groups'])} packets / {len(result['inventory'])} physical papers; no model calls.")
        return 0
