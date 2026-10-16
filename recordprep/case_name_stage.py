"""Bounded native-Pi caption inference; only Python publishes case_name.txt."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from pathlib import Path

from .case_name_prompt import CASE_NAME_PROMPT
from .paths import pi_settings_path, effective_pi_settings
from .case_profiles import case_profile_publication, read_case_profile_ref
from .profile_contract import read_file_at
from .profile_store import _check_directory
from .summary_agents import _atomic_write

SKILL = "recordprep-infer-case"
EXTENSION = "recordprep-case-name-tools.ts"
METADATA = "artifacts/case_name_profile.json"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path, limit=4 * 1024 * 1024):
    _check_directory(path.parent)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return read_file_at(fd, path.name, limit=limit)
    finally:
        os.close(fd)


def _prior(root):
    path = root / "case_name.txt"
    return _sha(_read(path, 4096)) if path.exists() or path.is_symlink() else None


def _model_settings(project_dir):
    # Record inherited model preferences too; never load credentials or models.json.
    agent = Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi/agent")
    keys = ("defaultProvider", "defaultModel", "defaultThinkingLevel", "modelThinkingLevels", "thinkingBudgets")
    result = []
    for path in (agent / "settings.json", pi_settings_path(project_dir)):
        try:
            value = (effective_pi_settings(project_dir) if path == pi_settings_path(project_dir)
                     else json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            value = {}
        if not isinstance(value, dict):
            raise ValueError("PI model settings are invalid.")
        result.append({key: value[key] for key in keys if key in value})
    return result


def capture(root, project_dir):
    """Capture the inventory again on every call, never reuse the initial list."""
    _check_directory(root)
    _check_directory(root / "text_pages")
    if (root / "artifacts").exists() or (root / "artifacts").is_symlink():
        _check_directory(root / "artifacts")
    paths = sorted((p for p in (root / "text_pages").iterdir() if re.fullmatch(r"[0-9]{4,}\.txt", p.name)),
                   key=lambda p: (int(p.stem), p.name))[:3]
    if not paths:
        raise ValueError("Run Create files before inferring the case name.")
    pages = [(path.name, _read(path)) for path in paths]
    resources = [project_dir / "SYSTEM.md", project_dir / "skills" / SKILL / "SKILL.md",
                 project_dir / "extensions" / EXTENSION, project_dir / "extensions/recordprep-auto-exit.ts"]
    signature = {"sources": {name: _sha(data) for name, data in pages},
                 "contract": _sha(CASE_NAME_PROMPT.encode()),
                 "runtime": [_sha(_read(path)) for path in resources],
                 "model": _model_settings(project_dir)}
    ref = read_case_profile_ref(root)
    stat = root.stat()
    guard = {"root": [stat.st_dev, stat.st_ino], "profile": asdict(ref) if ref else None,
             "prior": _prior(root), "inputs": signature}
    return pages, guard, ref


def stage_inputs(root, project_dir, workspace):
    pages, guard, ref = capture(root, project_dir)
    reads = []
    for index, (_name, data) in enumerate(pages, 1):
        path = workspace / f"source-{index}.txt"
        path.write_bytes(data)
        path.chmod(0o600)
        reads.append(str(path))
    candidate = workspace / "case-name-candidate.txt"
    spec = workspace / "case-name-access.json"
    spec.write_text(json.dumps({"reads": reads, "candidate": str(candidate)}), encoding="utf-8")
    spec.chmod(0o600)
    prompt = (f"/skill:{SKILL}\n" + CASE_NAME_PROMPT + "\n"
              + "Read only these staged source pages, in order:\n" + "\n".join(reads)
              + f"\nWrite the candidate only to: {candidate}\n"
              + "Python owns validation and publication. Do not modify the case bundle or rename anything.")
    return guard, ref, candidate, spec, prompt


def validate_candidate(data):
    try:
        text = data.decode("utf-8").strip()
    except UnicodeError as exc:
        raise ValueError("Case-name candidate is invalid; prior name preserved.") from exc
    if not text:
        raise ValueError("Caption is unclear in the first three pages; prior name preserved.")
    # Reject rather than repair paths, explanations, multiline answers or truncation.
    normalized = text.lower().replace("_", " ")
    if (len(text) > 120 or any(c in text for c in '\n\r/\\:*?"<>|`')
            or any(not c.isprintable() for c in text)
            or not any(c.isalpha() for c in text) or text.startswith(".")
            or normalized in {"unknown", "unclear", "none", "null", "undetermined"}
            or any(normalized.startswith(word) for word in
                   ("unable to", "case name is", "the case name", "first three pages", "cannot determine"))):
        raise ValueError("Case-name candidate is invalid; prior name preserved.")
    name = re.sub(r"[ _]+", "_", text).strip("_")
    if not name:
        raise ValueError("Case-name candidate is empty; prior name preserved.")
    return name


def publish(root, project_dir, guard, ref, candidate, *, check_stop=lambda: None):
    name = validate_candidate(_read(candidate, 4096))
    check_stop()
    with case_profile_publication(root, ref):
        if capture(root, project_dir)[1] != guard:
            raise ValueError("Case or inputs changed; prior name preserved.")
        check_stop()
        artifacts = root / "artifacts"
        artifacts.mkdir(mode=0o700, exist_ok=True)
        _check_directory(artifacts)
        metadata = {"schema_version": 2, "inputs": guard["inputs"], "output": _sha(name.encode())}
        _atomic_write(root / "case_name.txt", name)
        _atomic_write(root / METADATA, json.dumps(metadata, sort_keys=True) + "\n")
    return name


def is_current(root, project_dir):
    try:
        metadata = json.loads(_read(root / METADATA, 65536))
        return (isinstance(metadata, dict) and metadata.get("schema_version") == 2
                and metadata["inputs"] == capture(root, project_dir)[1]["inputs"]
                and metadata["output"] == _prior(root)
                and bool(validate_candidate(_read(root / "case_name.txt", 4096))))
    except (OSError, ValueError, KeyError, TypeError):
        return False
