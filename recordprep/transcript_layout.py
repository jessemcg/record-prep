"""Canonical case-local transcript-layout artifact for RecordPrep.

Owns loading, validation, freshness checks, manual overrides, and downstream
range resolution for ``artifacts/transcript_layout.json`` (schema version 1).

A layout answers one question per case bundle: is the record RT-only,
CT-only, or RT followed by CT, and where is the boundary? All RecordPrep
routing (text cleanup, classification, boundaries, numbering, source map)
must read the validated artifact, never the retired global config value or
the legacy manifest compatibility mirrors.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ARTIFACT_NAME = "recordprep-transcript-layout"
SCHEMA_VERSION = 1
TRANSCRIPT_LAYOUT_RELATIVE = "artifacts/transcript_layout.json"

MODES = ("rt_only", "ct_only", "split")
STATUSES = ("resolved", "needs_review")
DECISION_SOURCES = ("pi-agent", "manual")
CONFIDENCE_LEVELS = ("high", "medium", "low", "manual")

# A PI agent result is automatically accepted only at high confidence with
# supporting search evidence.
AUTO_RESOLVE_CONFIDENCE = "high"


class TranscriptLayoutError(ValueError):
    """Raised when the layout artifact or its inputs are invalid."""


@dataclass(frozen=True)
class LayoutDiagnostic:
    """Canonical transcript-layout state for UI and prerequisite messages."""

    code: str
    message: str
    mode: str | None = None


@dataclass(frozen=True)
class LayoutRebindGuard:
    """Immutable authority for one RecordPrep-owned text normalization pass."""

    root: Path
    artifact_bytes: bytes
    text_pages: tuple[tuple[str, int], ...]
    image_pages: tuple[tuple[str, int], ...]


def transcript_layout_path(root: Path) -> Path:
    return root.resolve(strict=False) / TRANSCRIPT_LAYOUT_RELATIVE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _page_number_from_name(name: str) -> int | None:
    match = re.search(r"(\d+)", Path(name).stem)
    return int(match.group(1)) if match else None


def _natural_sort_key(value: str | Path) -> list[object]:
    name = value.name if isinstance(value, Path) else Path(str(value)).name
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", name)
    ]


def text_page_names(text_dir: Path) -> list[str]:
    """Return the ordered, deduplicated text page file names for a bundle."""
    if not text_dir.is_dir():
        return []
    names = sorted(
        {
            path.name
            for path in text_dir.glob("[0-9][0-9][0-9][0-9].txt")
            if path.is_file()
        },
        key=_natural_sort_key,
    )
    return names


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def _text_page_inventory(root: Path) -> tuple[tuple[str, int], ...]:
    text_dir = root / "text_pages"
    return tuple(
        (name, _file_size(text_dir / name)) for name in text_page_names(text_dir)
    )


def _image_page_inventory(root: Path) -> tuple[tuple[str, int], ...]:
    image_dir = root / "image_pages"
    if not image_dir.is_dir():
        return ()
    paths = sorted(
        (
            path
            for path in image_dir.glob("[0-9][0-9][0-9][0-9].png")
            if path.is_file()
        ),
        key=_natural_sort_key,
    )
    return tuple((path.name, _file_size(path)) for path in paths)


def input_signature(root: Path) -> str:
    """Derive a stable signature from ordered text contents and paired images.

    The signature covers the ordered text-page contents and each paired
    image's name and byte size. It is intentionally cheap: it does not hash
    image bytes, only names and sizes, which change whenever pages are
    regenerated.
    """
    root = root.resolve(strict=False)
    text_dir = root / "text_pages"
    image_dir = root / "image_pages"
    digest = hashlib.sha256()
    digest.update(b"recordprep-transcript-layout-signature-v1\n")
    for name in text_page_names(text_dir):
        digest.update(name.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\n")
        try:
            content = (text_dir / name).read_bytes()
        except OSError:
            content = b""
        digest.update(str(len(content)).encode("ascii"))
        digest.update(b"\n")
        image_path = image_dir / (Path(name).stem + ".png")
        size = 0
        try:
            if image_path.is_file():
                size = image_path.stat().st_size
        except OSError:
            size = 0
        digest.update(image_path.name.encode("utf-8", errors="surrogateescape"))
        digest.update(b":")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _safe_paths(root: Path, evidence: Any) -> list[str]:
    """Return only case-root-relative evidence paths, dropping unsafe entries."""
    root = root.resolve(strict=False)
    result: list[str] = []
    if not isinstance(evidence, list):
        return result
    for item in evidence:
        if not isinstance(item, dict):
            continue
        raw = item.get("path") or item.get("text_path") or item.get("image_path")
        if not isinstance(raw, str) or not raw.strip():
            continue
        candidate = Path(raw)
        resolved = candidate if candidate.is_absolute() else root / candidate
        try:
            resolved.resolve(strict=False).relative_to(root)
        except ValueError:
            continue
        result.append(str(candidate))
    return result


def _evidence_unsafe_path_issues(root: Path, evidence: Any) -> list[str]:
    """Flag evidence entries whose paths escape the case root."""
    root = root.resolve(strict=False)
    issues: list[str] = []
    if not isinstance(evidence, list):
        return ["evidence must be a list."]
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            issues.append(f"evidence[{index}] must be an object.")
            continue
        raw = item.get("path") or item.get("text_path") or item.get("image_path")
        if not isinstance(raw, str) or not raw.strip():
            continue
        candidate = Path(raw)
        resolved = candidate if candidate.is_absolute() else root / candidate
        try:
            resolved.resolve(strict=False).relative_to(root)
        except ValueError:
            issues.append(
                f"evidence[{index}] has an unsafe path outside the case root."
            )
    return issues


def _sanitize_evidence(root: Path, evidence: Any) -> list[dict[str, Any]]:
    """Return evidence entries with safe case-relative paths only."""
    root = root.resolve(strict=False)
    if not isinstance(evidence, list):
        return []
    result: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        raw = item.get("path") or item.get("text_path") or item.get("image_path")
        if not isinstance(raw, str) or not raw.strip():
            continue
        candidate = Path(raw)
        resolved = candidate if candidate.is_absolute() else root / candidate
        try:
            resolved.resolve(strict=False).relative_to(root)
        except ValueError:
            continue
        result.append(item)
    return result


def validate_payload(payload: Any) -> list[str]:
    """Validate a transcript-layout payload; return a list of issues."""
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["transcript_layout.json must be an object."]
    if payload.get("artifact") != ARTIFACT_NAME:
        issues.append(f"artifact must be {ARTIFACT_NAME}.")
    if int(payload.get("schema_version") or 0) != SCHEMA_VERSION:
        issues.append(f"schema_version must be {SCHEMA_VERSION}.")
    status = _as_str(payload.get("status"))
    if status not in STATUSES:
        issues.append("status must be resolved or needs_review.")
    source = _as_str(payload.get("decision_source"))
    if source not in DECISION_SOURCES:
        issues.append("decision_source must be pi-agent or manual.")
    mode = payload.get("mode")
    if mode is not None and mode not in MODES:
        issues.append("mode must be rt_only, ct_only, split, or null.")
    if status == "resolved" and mode is None:
        issues.append("a resolved layout must declare a mode.")
    input_count = _as_int(payload.get("input_page_count"))
    if input_count is None or input_count < 0:
        issues.append("input_page_count must be a nonnegative integer.")
    if not _as_str(payload.get("input_signature")):
        issues.append("input_signature is required.")
    rt_end = _as_int(payload.get("rt_end_file_page"))
    ct_start = _as_int(payload.get("ct_start_file_page"))
    confidence = _as_str(payload.get("confidence"))
    if confidence not in CONFIDENCE_LEVELS:
        issues.append(
            "confidence must be high, medium, low, or manual."
        )
    if not _as_str(payload.get("method")):
        issues.append("method is required.")

    if status == "resolved" and input_count is not None:
        if mode == "rt_only":
            if rt_end != input_count:
                issues.append(
                    "RT-only requires rt_end_file_page to equal input_page_count."
                )
            if ct_start is not None:
                issues.append("RT-only must not declare ct_start_file_page.")
        elif mode == "ct_only":
            if ct_start != 1:
                issues.append("CT-only requires ct_start_file_page to be 1.")
            if rt_end is not None:
                issues.append("CT-only must not declare rt_end_file_page.")
        elif mode == "split":
            if (
                rt_end is None
                or ct_start is None
                or not 1 <= rt_end < input_count
                or ct_start != rt_end + 1
            ):
                issues.append(
                    "split requires 1 <= rt_end_file_page < input_page_count "
                    "and ct_start_file_page == rt_end_file_page + 1."
                )
        if source == "pi-agent" and confidence != AUTO_RESOLVE_CONFIDENCE:
            issues.append(
                "a pi-agent decision resolves only at high confidence."
            )
        if not isinstance(payload.get("evidence"), list) or not payload.get("evidence"):
            issues.append("a resolved layout must include supporting evidence.")
        if not _as_str(payload.get("search_summary")):
            issues.append("a resolved layout must include a search_summary.")
    elif status == "needs_review":
        unresolved_warnings = payload.get("warnings")
        if not isinstance(unresolved_warnings, list) or not unresolved_warnings:
            issues.append("needs_review requires at least one warning.")
    if not isinstance(payload.get("warnings"), list):
        issues.append("warnings must be a list.")
    return list(dict.fromkeys(issues))


def _reject_stale(
    payload: dict[str, Any],
    root: Path,
    input_count: int,
    signature: str,
    issues: list[str],
) -> None:
    if int(payload.get("input_page_count") or -1) != input_count:
        issues.append(
            "transcript_layout.json is stale: input_page_count does not match "
            "the current text pages."
        )
    if _as_str(payload.get("input_signature")) != signature:
        issues.append(
            "transcript_layout.json is stale: input_signature does not match "
            "the current pages."
        )


def load_layout(root: Path) -> dict[str, Any] | None:
    """Load and validate the artifact, or return None when missing/invalid."""
    path = transcript_layout_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def diagnose_layout(root: Path) -> LayoutDiagnostic:
    """Distinguish missing, malformed, review-required, and stale layouts."""
    root = root.resolve(strict=False)
    path = transcript_layout_path(root)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return LayoutDiagnostic(
            "missing",
            "Run Detect transcript layout before starting this step.",
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        return LayoutDiagnostic(
            "malformed",
            "Transcript layout artifact is malformed; rerun Detect transcript layout.",
        )
    mode = payload.get("mode") if payload.get("mode") in MODES else None
    issues = list(validate_payload(payload))
    issues.extend(_evidence_unsafe_path_issues(root, payload.get("evidence")))
    if issues:
        return LayoutDiagnostic(
            "malformed",
            "Transcript layout artifact is malformed; rerun Detect transcript layout.",
            mode,
        )
    input_count = len(text_page_names(root / "text_pages"))
    if int(payload.get("input_page_count") or -1) != input_count:
        return LayoutDiagnostic(
            "page_count_stale",
            "Transcript layout is stale because numbered text pages changed; "
            "rerun Detect transcript layout.",
            mode,
        )
    if _as_str(payload.get("input_signature")) != input_signature(root):
        return LayoutDiagnostic(
            "signature_stale",
            "Transcript layout is stale because page text or images changed; "
            "rerun Detect transcript layout.",
            mode,
        )
    if payload.get("status") == "needs_review":
        return LayoutDiagnostic(
            "needs_review",
            "Transcript layout needs review: choose a manual layout to continue.",
            mode,
        )
    return LayoutDiagnostic("resolved", "Transcript layout is resolved and fresh.", mode)


def capture_layout_rebind_guard(root: Path) -> LayoutRebindGuard:
    """Capture authority to rebind a fresh resolved layout after normalization."""
    root = root.resolve(strict=False)
    diagnostic = diagnose_layout(root)
    if diagnostic.code != "resolved":
        raise TranscriptLayoutError(diagnostic.message)
    path = transcript_layout_path(root)
    try:
        artifact_bytes = path.read_bytes()
    except OSError as exc:
        raise TranscriptLayoutError(
            "Transcript layout changed while text processing was starting."
        ) from exc
    return LayoutRebindGuard(
        root=root,
        artifact_bytes=artifact_bytes,
        text_pages=_text_page_inventory(root),
        image_pages=_image_page_inventory(root),
    )


def finalize_layout_rebind(
    guard: LayoutRebindGuard,
    rewritten_text_sizes: Mapping[str, int],
) -> Path:
    """Rebind an unchanged decision after guarded RecordPrep text rewrites.

    Every text-size change must be named by the normalization loop, while page
    and image identity and the artifact itself must remain unchanged.
    """
    root = guard.root.resolve(strict=False)
    path = transcript_layout_path(root)
    try:
        if path.read_bytes() != guard.artifact_bytes:
            raise TranscriptLayoutError(
                "Transcript layout artifact changed during text processing."
            )
    except OSError as exc:
        raise TranscriptLayoutError(
            "Transcript layout artifact changed during text processing."
        ) from exc

    current_text = _text_page_inventory(root)
    old_names = tuple(name for name, _size in guard.text_pages)
    current_names = tuple(name for name, _size in current_text)
    if current_names != old_names:
        raise TranscriptLayoutError(
            "Numbered text pages were added, removed, or renamed during text processing."
        )
    if _image_page_inventory(root) != guard.image_pages:
        raise TranscriptLayoutError(
            "Paired page images changed during text processing."
        )

    reported: dict[str, int] = {}
    for raw_name, raw_size in rewritten_text_sizes.items():
        name = Path(str(raw_name)).name
        if name != str(raw_name) or name not in old_names:
            raise TranscriptLayoutError(
                "Text processing reported an unknown numbered page rewrite."
            )
        try:
            size = int(raw_size)
        except (TypeError, ValueError) as exc:
            raise TranscriptLayoutError(
                "Text processing reported an invalid rewritten page size."
            ) from exc
        if size < 0:
            raise TranscriptLayoutError(
                "Text processing reported an invalid rewritten page size."
            )
        reported[name] = size

    old_sizes = dict(guard.text_pages)
    current_sizes = dict(current_text)
    changed = {name for name in old_names if old_sizes[name] != current_sizes[name]}
    if not changed.issubset(reported):
        raise TranscriptLayoutError(
            "Unreported text-page changes occurred during text processing."
        )
    if any(current_sizes[name] != size for name, size in reported.items()):
        raise TranscriptLayoutError(
            "A rewritten text page changed after RecordPrep normalized it."
        )

    try:
        payload = json.loads(guard.artifact_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TranscriptLayoutError("Transcript layout artifact is malformed.") from exc
    if not isinstance(payload, dict) or payload.get("status") != "resolved":
        raise TranscriptLayoutError(
            "Only a resolved transcript layout can be rebound."
        )
    payload["input_page_count"] = len(current_text)
    payload["input_signature"] = input_signature(root)
    issues = list(validate_payload(payload))
    issues.extend(_evidence_unsafe_path_issues(root, payload.get("evidence")))
    if issues:
        raise TranscriptLayoutError(
            "transcript-layout rebinding failed: " + "; ".join(issues)
        )
    try:
        if path.read_bytes() != guard.artifact_bytes:
            raise TranscriptLayoutError(
                "Transcript layout artifact changed during text processing."
            )
    except OSError as exc:
        raise TranscriptLayoutError(
            "Transcript layout artifact changed during text processing."
        ) from exc
    _atomic_write_json(path, payload)
    return path


def read_resolved_layout(root: Path) -> dict[str, Any] | None:
    """Return the validated, fresh, resolved layout for pipeline routing.

    Returns None when the artifact is missing, invalid, stale, or marked
    needs_review. This is the only function downstream stages may use to
    resolve RT/CT routing.
    """
    root = root.resolve(strict=False)
    payload = load_layout(root)
    if payload is None:
        return None
    input_count = len(text_page_names(root / "text_pages"))
    issues = list(validate_payload(payload))
    issues.extend(_evidence_unsafe_path_issues(root, payload.get("evidence")))
    _reject_stale(payload, root, input_count, input_signature(root), issues)
    if issues:
        return None
    if payload.get("status") != "resolved" or payload.get("mode") is None:
        return None
    return payload


def is_detection_pending(root: Path) -> bool:
    return read_resolved_layout(root) is None


def detection_status(root: Path) -> tuple[str, str | None]:
    """Return (status, mode) for UI display: resolved, pending, needs_review."""
    diagnostic = diagnose_layout(root)
    if diagnostic.code == "resolved":
        return "resolved", diagnostic.mode
    if diagnostic.code == "needs_review":
        return "needs_review", diagnostic.mode
    return "pending", diagnostic.mode


def layout_display_summary(root: Path) -> str:
    """Human summary used by the transcript expander source row."""
    status, mode = detection_status(root)
    if status == "pending":
        return "Detection pending"
    if status == "needs_review":
        return "Needs review"
    payload = load_layout(root) or {}
    source = (
        " manual"
        if payload.get("decision_source") == "manual"
        else " automatic"
    )
    suffix = f"•{source} detection"
    if mode == "rt_only":
        return "Reporter's transcript only" + suffix
    if mode == "ct_only":
        return "Clerk's transcript only" + suffix
    rt_end = _as_int(payload.get("rt_end_file_page"))
    page = f" through page {rt_end}" if rt_end else ""
    return f"RT + CT • RT{page}{suffix}"


def is_resolved(root: Path) -> bool:
    return read_resolved_layout(root) is not None


# Explicit skip label shown by the UI and runner when the resolved layout is
# CT-only: participant indexing was not performed and cannot be.
CT_ONLY_SKIP_LABEL = "Skipped — Clerk’s transcript only"


def is_ct_only(root: Path) -> bool:
    """Whether the CT-only participant-index exemption applies right now.

    True only for a current (resolved, fresh, structurally valid) artifact
    whose mode is ct_only — read through ``read_resolved_layout`` so manual
    and automatically resolved layouts receive identical treatment. Missing,
    malformed, stale, needs-review, or unresolved layouts never authorize the
    exemption; RT-only and split layouts never match.
    """
    payload = read_resolved_layout(root)
    return payload is not None and str(payload.get("mode") or "") == "ct_only"


def ct_only_skip_message(root: Path) -> str:
    """The explicit skip reason logged for an applicable CT-only record."""
    return (
        f"Build participant and witness index: {CT_ONLY_SKIP_LABEL}. "
        "Participant and witness attribution is unavailable because the bundle "
        "contains only a clerk's transcript; this is not a finding that no "
        "participants or witnesses appeared."
    )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def draft_layout_payload(
    *,
    mode: str | None,
    status: str,
    decision_source: str,
    confidence: str,
    method: str,
    rt_end_file_page: int | None = None,
    ct_start_file_page: int | None = None,
    search_summary: str = "",
    evidence: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    marker_pages: dict[str, Any] | None = None,
    inspected_pages: dict[str, Any] | None = None,
    additional: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete payload carrying the current bundle signature."""
    payload: dict[str, Any] = {
        "artifact": ARTIFACT_NAME,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "decision_source": decision_source,
        "mode": mode,
        "input_page_count": 0,
        "input_signature": "",
        "rt_end_file_page": rt_end_file_page,
        "ct_start_file_page": ct_start_file_page,
        "confidence": confidence,
        "method": method,
        "search_summary": search_summary,
        "evidence": list(evidence or []),
        "warnings": list(warnings or []),
    }
    if additional:
        payload.update(additional)
    return payload


def finalize_layout_draft(root: Path, draft: dict[str, Any]) -> Path:
    """Stamp the draft with the current page count/signature and publish it.

    Evidence entries with paths outside the case root are dropped, and a
    draft that still contains them is rejected. Raises
    TranscriptLayoutError when the draft is structurally invalid.
    """
    root = root.resolve(strict=False)
    input_count = len(text_page_names(root / "text_pages"))
    draft["input_page_count"] = input_count
    draft["input_signature"] = input_signature(root)
    issues = list(validate_payload(draft))
    issues.extend(_evidence_unsafe_path_issues(root, draft.get("evidence")))
    issues = list(dict.fromkeys(issues))
    if issues:
        raise TranscriptLayoutError(
            "transcript-layout validation failed: " + "; ".join(issues)
        )
    draft["evidence"] = _sanitize_evidence(root, draft.get("evidence"))
    output = transcript_layout_path(root)
    _atomic_write_json(output, draft)
    return output


_LEGACY_MANUAL_MIRRORS = ("rt_ct_split_page", "rt_ct_split_mode")


def _read_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest_path = root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_name(f".{manifest_path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)


def legacy_manifest_split(root: Path) -> tuple[str, int | None]:
    """Return the legacy manifest compatibility mirror, if present."""
    manifest = _read_manifest(root)
    mode = _as_str(manifest.get("rt_ct_split_mode"))
    normalized_mode = mode if mode in MODES else "split"
    return normalized_mode, _as_int(manifest.get("rt_ct_split_page"))


def _mirror_legacy_manifest(root: Path, mode: str, rt_end: int | None) -> None:
    if not (root / "manifest.json").is_file():
        return
    manifest = _read_manifest(root)
    manifest["rt_ct_split_mode"] = mode
    manifest["rt_ct_split_page"] = rt_end
    try:
        _write_manifest(root, manifest)
    except OSError:
        return


def _manual_rt_end(mode: str, input_count: int, rt_end: int | None) -> int | None:
    if mode == "rt_only":
        return input_count if input_count else None
    if mode == "ct_only":
        return None
    if rt_end is None or not 1 <= rt_end < input_count:
        raise TranscriptLayoutError(
            "Manual RT + CT requires a positive RT end page strictly less "
            "than the combined PDF page count."
        )
    return rt_end


def apply_manual_override(
    root: Path,
    *,
    mode: str,
    rt_end_file_page: int | None = None,
    method: str = "manual override",
    note: str = "",
) -> Path:
    """Atomically apply a manual layout choice to the artifact and mirrors.

    The mode and combined-PDF page value are validated against the current
    page inventory before anything is written. Only the case-local artifact
    and the legacy manifest compatibility mirrors are touched.
    """
    root = root.resolve(strict=False)
    if mode not in MODES:
        raise TranscriptLayoutError(f"Unsupported manual layout mode: {mode}")
    input_count = len(text_page_names(root / "text_pages"))
    if input_count <= 0:
        raise TranscriptLayoutError(
            "Run Create files before setting a manual transcript layout."
        )
    rt_end = _manual_rt_end(mode, input_count, rt_end_file_page)
    if mode == "split":
        ct_start = rt_end + 1
    else:
        ct_start = 1 if mode == "ct_only" else None
    evidence: list[dict[str, Any]] = [
        {
            "path": "manifest.json",
            "kind": "manual",
            "note": note or "User-selected transcript layout override.",
        }
    ]
    draft = draft_layout_payload(
        mode=mode,
        status="resolved",
        decision_source="manual",
        confidence="manual",
        method=method,
        rt_end_file_page=rt_end,
        ct_start_file_page=ct_start,
        search_summary=(note or "Manual override"),
        evidence=evidence,
        warnings=[],
    )
    output = finalize_layout_draft(root, draft)
    _mirror_legacy_manifest(root, mode, rt_end)
    return output


def range_for_mode(
    root: Path,
    *,
    mode: str,
    rt_end: int | None,
    ct_start: int | None,
    input_count: int,
) -> tuple[int, int, bool, bool]:
    """Return (rt_end_file_page, ct_start_file_page, need_rt, need_ct)."""
    if mode == "rt_only":
        return input_count, 0, True, False
    if mode == "ct_only":
        return 0, 1, False, True
    if (
        rt_end is None
        or ct_start is None
        or not 1 <= rt_end < input_count
        or ct_start != rt_end + 1
    ):
        raise TranscriptLayoutError(
            "A resolved RT + CT layout requires an adjacent boundary "
            "inside the current page count."
        )
    return rt_end, ct_start, True, True


def resolve_rt_ct_split(root: Path, text_dir: Path) -> tuple[int, int, bool, bool, str]:
    """Resolve downstream RT/CT routing exclusively from the artifact.

    Returns (rt_end_file_page, ct_start_file_page, need_rt, need_ct, mode).
    Raises TranscriptLayoutError when the layout is unresolved, needs review,
    stale, or out of range.
    """
    root = root.resolve(strict=False)
    payload = read_resolved_layout(root)
    if payload is None:
        status, _mode = detection_status(root)
        if status == "needs_review":
            raise TranscriptLayoutError(
                "Transcript layout needs review: open the transcript expander "
                "and choose a manual layout before continuing."
            )
        raise TranscriptLayoutError(diagnose_layout(root).message)
    mode = str(payload.get("mode") or "")
    input_count = len(text_page_names(root / "text_pages"))
    if input_count <= 0:
        raise TranscriptLayoutError(
            "Run Create files to generate text pages first."
        )
    rt_end, ct_start, need_rt, need_ct = range_for_mode(
        root,
        mode=mode,
        rt_end=_as_int(payload.get("rt_end_file_page")),
        ct_start=_as_int(payload.get("ct_start_file_page")),
        input_count=input_count,
    )
    return rt_end, ct_start, need_rt, need_ct, mode


ARTIFACT_RELATIVE = TRANSCRIPT_LAYOUT_RELATIVE
__all__ = (
    "ARTIFACT_NAME",
    "ARTIFACT_RELATIVE",
    "AUTO_RESOLVE_CONFIDENCE",
    "CONFIDENCE_LEVELS",
    "DECISION_SOURCES",
    "MODES",
    "SCHEMA_VERSION",
    "STATUSES",
    "TRANSCRIPT_LAYOUT_RELATIVE",
    "LayoutDiagnostic",
    "LayoutRebindGuard",
    "TranscriptLayoutError",
    "apply_manual_override",
    "capture_layout_rebind_guard",
    "detection_status",
    "diagnose_layout",
    "draft_layout_payload",
    "finalize_layout_draft",
    "finalize_layout_rebind",
    "CT_ONLY_SKIP_LABEL",
    "input_signature",
    "is_ct_only",
    "is_detection_pending",
    "is_resolved",
    "layout_display_summary",
    "legacy_manifest_split",
    "load_layout",
    "read_resolved_layout",
    "range_for_mode",
    "resolve_rt_ct_split",
    "text_page_names",
    "transcript_layout_path",
    "validate_payload",
)
