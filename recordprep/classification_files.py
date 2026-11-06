"""One classification filename/routing contract; legacy reads never migrate files."""
from pathlib import Path

SIDES = ("RT", "CT")
SUFFIXES = {"basic": "basic", "advanced": "basic_advanced", "dates": "basic_advanced_dates",
            "names": "basic_advanced_dates_names", "final": "basic_advanced_dates_names_corrected"}
LEGACY = {"basic": "basic", "advanced": "basic_advanced", "dates": "basic_advanced_corrected_dates",
          "names": "basic_advanced_corrected_dates_names", "final": "basic_advanced_corrected_dates_names"}
WORKFLOW = "classification/workflow-v2.json"
REVIEW_REQUIRED = "classification/review-required"
RECEIPT = "classification/agent-review.json"
PENDING = ".recordprep/classification-review-pending.json"


def names(stage, *, legacy=False):
    suffix = (LEGACY if legacy else SUFFIXES)[stage]
    return tuple(f"{side}_{suffix}.jsonl" for side in SIDES)


def new_workflow(root):
    directory = root / "classification"
    return ((root / WORKFLOW).exists() or (root / REVIEW_REQUIRED).exists()
            or any((directory / n).exists() for stage in ("dates", "names", "final") for n in names(stage)))


def require_review(root):
    """Explicit generation only. Preserve old results but revoke their readiness."""
    from .profile_store import _check_directory
    from .summary_agents import _atomic_write
    directory = root / "classification"
    directory.mkdir(exist_ok=True)
    _check_directory(directory)
    # Required first: even a crash writing workflow metadata must prevent fallback.
    _atomic_write(root / REVIEW_REQUIRED, "Agent classification review required.\n")
    _atomic_write(root / WORKFLOW, '{"schema_version":2}\n')


def stage_paths(root, stage):
    """Saved intermediate inputs, one filename family for the entire stage."""
    directory = root / "classification"
    use_new = any((directory / n).exists() for n in names(stage))
    return tuple(directory / n for n in names(stage, legacy=not use_new))


def final_paths(root):
    """Return one family, never new RT with legacy CT or stale legacy fallback.

    Presence only here; consumers validate their actual contents. Saved manual
    edits remain usable and do not need historical model/profile/hash freshness.
    """
    if (root / PENDING).exists() or (root / PENDING).is_symlink():
        raise ValueError("Interrupted classification review publication requires recovery.")
    modern = new_workflow(root)
    if modern and ((root / REVIEW_REQUIRED).exists() or not (root / RECEIPT).is_file()):
        raise ValueError("Run Correct classification with agent to publish final classifications.")
    directory = root / "classification"
    paths = tuple(directory / n for n in names("final", legacy=not modern))
    inputs = stage_paths(root, "names")
    sides = [i for i, side in enumerate(SIDES) if inputs[i].is_file()
             or (directory / f"{side}_basic.jsonl").is_file()]
    if not modern and not any(p.is_file() for p in paths):
        return paths  # Historical participant navigation allowed absent classification.
    if any(not paths[i].is_file() for i in sides) or (modern and not any(p.is_file() for p in paths)):
        raise ValueError("Final classifications are incomplete; run Correct classification with agent.")
    return paths


def navigation_paths(root):
    paths = list(final_paths(root))
    if not new_workflow(root):
        paths.extend(root / "classification" / n for n in ("final.jsonl", "final_classification.jsonl", "combined.jsonl"))
    return paths
