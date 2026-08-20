#!/usr/bin/env python3
"""Prepare, validate, and publish RecordPrep transcript_layout.json.

A thin deterministic wrapper around the canonical
``recordprep.transcript_layout`` module. The PI detection skill uses this
script's helpers to prepare a draft, validate drafts before anything is
written, and atomically publish the final artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# The skill runs inside a staged project workspace; the canonical module is
# available from the RecordPrep project root either through PYTHONPATH
# (runner) or through a direct invocation where the project root is passed
# via RECORDPREP_PI_PROJECT_DIR (the parent of the staged .pi directory).
try:
    from recordprep.transcript_layout import (
        TranscriptLayoutError,
        draft_layout_payload,
        finalize_layout_draft,
        input_signature,
        load_layout,
        text_page_names,
        validate_payload,
    )
except ImportError:  # pragma: no cover - defensive fallback for direct runs
    configured = str(
        __import__("os").environ.get("RECORDPREP_PI_PROJECT_DIR", "") or ""
    ).strip()
    if configured:
        project_root = Path(configured).expanduser().resolve(strict=False).parent
    else:
        project_root = Path(__file__).resolve().parents[4]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from recordprep.transcript_layout import (  # noqa: F811
        TranscriptLayoutError,
        draft_layout_payload,
        finalize_layout_draft,
        input_signature,
        load_layout,
        text_page_names,
        validate_payload,
    )


def prepare_draft(
    root: Path,
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
) -> dict[str, Any]:
    """Prepare a validated draft carrying the current bundle signature."""
    root = root.resolve(strict=False)
    if not (root / "text_pages").is_dir():
        raise ValueError(
            "Run Create files first: text_pages is missing for "
            f"{root}."
        )
    page_count = len(text_page_names(root / "text_pages"))
    if page_count <= 0:
        raise ValueError(
            "Run Create files first: text_pages contains no numbered pages."
        )
    payload = draft_layout_payload(
        mode=mode,
        status=status,
        decision_source=decision_source,
        confidence=confidence,
        method=method,
        rt_end_file_page=rt_end_file_page,
        ct_start_file_page=ct_start_file_page,
        search_summary=search_summary,
        evidence=evidence,
        warnings=warnings,
        marker_pages=marker_pages,
        inspected_pages=inspected_pages,
    )
    payload["input_page_count"] = len(text_page_names(root / "text_pages"))
    payload["input_signature"] = input_signature(root)
    issues = validate_payload(payload)
    if issues:
        raise TranscriptLayoutError(
            "transcript-layout draft validation failed: " + "; ".join(issues)
        )
    return payload


def publish_draft(root: Path, draft: dict[str, Any]) -> Path:
    """Atomically publish a prepared draft after revalidation."""
    output = finalize_layout_draft(root, draft)
    return output


def validate(root: Path) -> list[str]:
    root = root.resolve(strict=False)
    path = root / "artifacts" / "transcript_layout.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"transcript_layout.json is missing or invalid: {exc}"]
    if not isinstance(payload, dict):
        return ["transcript_layout.json must be an object."]
    issues = list(validate_payload(payload))
    input_count = len(text_page_names(root / "text_pages"))
    if int(payload.get("input_page_count") or -1) != input_count:
        issues.append(
            "transcript_layout.json input_page_count does not match the "
            "current text pages."
        )
    if payload.get("input_signature") != input_signature(root):
        issues.append(
            "transcript_layout.json input_signature is stale."
        )
    return list(dict.fromkeys(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "publish", "validate"))
    parser.add_argument("case_bundle", type=Path)
    parser.add_argument("--draft", type=Path, default=None)
    parser.add_argument("--mode", default=None)
    parser.add_argument("--status", default="resolved")
    parser.add_argument("--decision-source", default="pi-agent")
    parser.add_argument("--confidence", default="high")
    parser.add_argument("--method", default="skill workflow")
    parser.add_argument("--rt-end", type=int, default=None)
    parser.add_argument("--ct-start", type=int, default=None)
    parser.add_argument("--search-summary", default="")
    parser.add_argument("--evidence", default="[]")
    parser.add_argument("--warnings", default="[]")
    parser.add_argument("--marker-pages", default="{}")
    parser.add_argument("--inspected-pages", default="{}")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    try:
        if args.command == "validate":
            issues = validate(args.case_bundle)
            if issues:
                for issue in issues:
                    print(f"transcript-layout validation: {issue}", file=sys.stderr)
                return 1
            print("transcript_layout.json is valid.")
            return 0
        if args.command == "publish":
            if args.draft is None:
                print("publish requires --draft", file=sys.stderr)
                return 1
            try:
                draft = json.loads(args.draft.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"unable to read draft: {exc}", file=sys.stderr)
                return 1
            if not isinstance(draft, dict):
                print("draft must be an object", file=sys.stderr)
                return 1
            output = publish_draft(args.case_bundle, draft)
            print(f"Wrote {output}")
            return 0
        # prepare
        try:
            evidence = json.loads(args.evidence)
        except json.JSONDecodeError:
            evidence = []
        try:
            warnings = json.loads(args.warnings)
        except json.JSONDecodeError:
            warnings = []
        try:
            marker_pages = json.loads(args.marker_pages)
        except json.JSONDecodeError:
            marker_pages = {}
        try:
            inspected_pages = json.loads(args.inspected_pages)
        except json.JSONDecodeError:
            inspected_pages = {}
        draft = prepare_draft(
            args.case_bundle,
            mode=args.mode,
            status=args.status,
            decision_source=args.decision_source,
            confidence=args.confidence,
            method=args.method,
            rt_end_file_page=args.rt_end,
            ct_start_file_page=args.ct_start,
            search_summary=args.search_summary,
            evidence=evidence if isinstance(evidence, list) else [],
            warnings=warnings if isinstance(warnings, list) else [],
            marker_pages=marker_pages if isinstance(marker_pages, dict) else {},
            inspected_pages=inspected_pages if isinstance(inspected_pages, dict) else {},
        )
        print(json.dumps(draft, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TranscriptLayoutError) as exc:
        print(f"transcript-layout failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
