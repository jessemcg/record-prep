"""Model identity resolution and honest capacity accounting for summaries.

This module composes capacity estimates from the components the model can
actually see — system prompt, expanded skill guidance, tool schemas (proxied
by the staged extension source), the runtime prompt, extraction source
payloads, synthesis digest blocks — and reports clearly labeled estimate
ranges using UTF-8-aware three/four-chars-per-token approximations. These
are estimates, never tokenization guarantees.

Policy:

- A known oversized individual source/block request fails before its paid
  call with the item id and actionable capacity information.
- An aggregate synthesis-history estimate above the 80% safety margin warns
  and proceeds with agent-managed incremental work; it never forces batching
  or rejects an otherwise manageable run.
- Unknown model metadata is visibly reported as unknown, never treated as
  verified capacity.

The command-line entry point (``python -m recordprep.summary_preflight``)
is a read-only diagnostic: it makes no paid calls, acquires no publishing
lock, and writes no project, bundle, or configuration files. This module
intentionally has no GTK imports.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from recordprep import pi_runtime
from recordprep.summary_agents import (
    SUMMARY_KINDS,
    build_work_items,
    load_digest_markdown,
    load_digest_meta,
)

ARTIFACT = "recordprep-summary-preflight"
SCHEMA_VERSION = 1

# Safety margin applied to the model context window.
CAPACITY_FRACTION = pi_runtime.SUMMARY_CONTEXT_CAPACITY_FRACTION

# Explicit estimate assumptions (characters). The staged extension source is
# the proxy for the enabled tool schemas; the envelope constant covers the
# JSON-RPC/message scaffolding around prompts and tool results.
ENVELOPE_OVERHEAD_CHARS = 2_000
EXTRACTION_OUTPUT_ALLOWANCE_CHARS = 6_000
# Per synthesized document: expected narrative plus the tool-call/result
# exchange history that accumulates in the long-lived synthesis session.
SYNTHESIS_SECTION_ALLOWANCE_CHARS = 2_500
SYNTHESIS_TOOL_EXCHANGE_ALLOWANCE_CHARS = 1_500
# Reasoning tokens are invisible context in some providers; allow headroom.
REASONING_ALLOWANCE_CHARS = 10_000


class PreflightError(ValueError):
    pass


@dataclass(frozen=True)
class ModelIdentity:
    """Effective provider, full model id, and thinking level with sources."""

    provider: str
    model_id: str
    thinking: str
    provider_source: str
    model_source: str
    thinking_source: str

    def payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "thinking": self.thinking,
            "provider_source": self.provider_source,
            "model_source": self.model_source,
            "thinking_source": self.thinking_source,
        }


@dataclass(frozen=True)
class StageCapacity:
    """Resolved model identity plus discovered metadata, or honest unknowns."""

    identity: ModelIdentity
    context_window: int | None = None
    max_output_tokens: int | None = None
    matched: bool = False
    discovery_error: str = ""
    model_name: str = ""

    @property
    def known(self) -> bool:
        return self.matched and bool(self.context_window and self.context_window > 0)

    @property
    def headroom_tokens(self) -> int | None:
        if not self.known:
            return None
        return int(int(self.context_window or 0) * CAPACITY_FRACTION)

    def payload(self) -> dict[str, Any]:
        return {
            **self.identity.payload(),
            "model_name": self.model_name,
            "matched": self.matched,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "capacity_fraction": CAPACITY_FRACTION,
            "headroom_tokens": self.headroom_tokens,
            "capacity_known": self.known,
            "discovery_error": self.discovery_error,
        }


def resolve_stage_identity(
    settings: dict[str, Any],
    phase: str,
    project_settings_path: Path,
) -> ModelIdentity:
    """Resolve one phase's effective model identity once per stage.

    Explicit per-stage overrides win; empty values inherit the staged
    project PI settings environment (the runner stages a byte-identical copy
    of the project ``.pi/settings.json`` next to the child). Matching is
    provider-qualified: the full model id is never reduced to a basename.
    """
    settings = settings if isinstance(settings, dict) else {}
    override_provider = str(settings.get(f"{phase}_provider") or "").strip()
    override_model = str(settings.get(f"{phase}_model") or "").strip()
    override_thinking = str(settings.get(f"{phase}_thinking") or "").strip()

    project_provider = ""
    project_model = ""
    project_thinking = ""
    try:
        project_provider, project_model = pi_runtime.current_project_pi_model(
            project_settings_path
        ) or ("", "")
    except pi_runtime.PiSettingsError:
        project_provider, project_model = "", ""
    try:
        project_thinking = (
            pi_runtime.current_project_pi_thinking_level(project_settings_path) or ""
        )
    except pi_runtime.PiSettingsError:
        project_thinking = ""

    return ModelIdentity(
        provider=override_provider or project_provider,
        model_id=override_model or project_model,
        thinking=override_thinking or project_thinking,
        provider_source="override" if override_provider else "project-settings",
        model_source="override" if override_model else "project-settings",
        thinking_source="override" if override_thinking else "project-settings",
    )


def match_model(
    identity: ModelIdentity,
    models: Iterable[pi_runtime.PiModel],
) -> pi_runtime.PiModel | None:
    """Match provider plus full model id; ambiguous ids never match silently."""
    for model in models:
        if (
            model.provider.casefold() == identity.provider.casefold()
            and model.model_id.casefold() == identity.model_id.casefold()
        ):
            return model
    return None


def resolve_stage_capacity(
    settings: dict[str, Any],
    phase: str,
    project_settings_path: Path,
    *,
    pi_command: Sequence[str] | None = None,
    models: Sequence[pi_runtime.PiModel] | None = None,
) -> StageCapacity:
    """Resolve identity once, then match against discovery results.

    ``models`` lets a caller reuse one discovery result for many
    kind/phase combinations instead of launching discovery repeatedly.
    """
    identity = resolve_stage_identity(settings, phase, project_settings_path)
    if not identity.provider or not identity.model_id:
        return StageCapacity(
            identity=identity,
            discovery_error=(
                "no effective provider/model id resolved for this phase; "
                "set a project default model or a per-stage override."
            ),
        )
    if models is None:
        if not pi_command:
            try:
                pi_command = pi_runtime.resolve_pi_agent_argv(
                    pi_runtime.discover_pi_agent_command()
                )
            except (pi_runtime.PiRuntimeError, OSError) as exc:
                return StageCapacity(identity=identity, discovery_error=str(exc))
        try:
            models = pi_runtime.available_pi_models(pi_command)
        except (pi_runtime.PiRuntimeError, OSError, subprocess.SubprocessError) as exc:
            return StageCapacity(identity=identity, discovery_error=str(exc))
    model = match_model(identity, models)
    if model is None:
        return StageCapacity(
            identity=identity,
            discovery_error=(
                "the effective provider/model id was not found among PI's "
                "available models; metadata stays unknown."
            ),
        )
    return StageCapacity(
        identity=identity,
        context_window=model.context_window,
        max_output_tokens=model.max_output_tokens,
        matched=True,
        model_name=model.name,
    )


def estimate_token_range(text_or_chars: str | int) -> tuple[int, int]:
    """UTF-8-aware three/four-units-per-token estimate range.

    Text is measured in UTF-8 bytes. The low bound divides bytes by four
    (dense scripts), the high bound by three (conservative). The result is
    an estimate, not tokenization.
    """
    if isinstance(text_or_chars, str):
        data = len(text_or_chars.encode("utf-8"))
    else:
        data = max(0, int(text_or_chars))
    return data // 4, data // 3


@dataclass(frozen=True)
class CapacityDecision:
    level: str  # "ok" | "warn" | "fail" | "unknown"
    message: str
    estimate_tokens: tuple[int, int]
    headroom_tokens: int | None

    def payload(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "message": self.message,
            "estimate_tokens_low": self.estimate_tokens[0],
            "estimate_tokens_high": self.estimate_tokens[1],
            "headroom_tokens": self.headroom_tokens,
        }


def _headroom_exceeded(low_tokens: int, headroom: int | None) -> bool:
    return headroom is not None and low_tokens > headroom


def _normalized_capacity(capacity: "StageCapacity | None") -> StageCapacity:
    if capacity is None:
        return StageCapacity(
            identity=ModelIdentity("", "", "", "unresolved", "unresolved", "unresolved"),
            discovery_error="model identity was not resolved for this phase",
        )
    return capacity


def check_individual_request(
    capacity: StageCapacity | None,
    request_chars: int,
    *,
    label: str,
    output_chars: int = EXTRACTION_OUTPUT_ALLOWANCE_CHARS,
) -> CapacityDecision:
    """Fail a known-oversized individual request before its paid call."""
    capacity = _normalized_capacity(capacity)
    total_chars = int(request_chars) + int(output_chars)
    low, high = estimate_token_range(total_chars)
    headroom = capacity.headroom_tokens
    if not capacity.known:
        return CapacityDecision(
            "unknown",
            (
                f"{label}: model capacity metadata is unavailable"
                + (f" ({capacity.discovery_error})" if capacity.discovery_error else "")
                + "; PI will enforce its own limit."
            ),
            (low, high),
            headroom,
        )
    if _headroom_exceeded(low, headroom):
        raise PreflightError(
            f"{label} does not fit conservatively within {CAPACITY_FRACTION:.0%} of "
            f"{capacity.identity.provider}/{capacity.identity.model_id}'s context "
            f"window (estimated {low}-{high} tokens vs headroom {headroom}). "
            "Choose a larger-context model for this stage in Settings."
        )
    if _headroom_exceeded(high, headroom):
        return CapacityDecision(
            "warn",
            (
                f"{label} estimate ({low}-{high} tokens) reaches the safety "
                f"headroom ({headroom}) at its upper bound; monitor for PI "
                "compaction."
            ),
            (low, high),
            headroom,
        )
    return CapacityDecision("ok", "", (low, high), headroom)


def check_aggregate_history(
    capacity: StageCapacity | None,
    history_chars: int,
    *,
    label: str,
) -> CapacityDecision:
    """Warn and proceed when the aggregate synthesis history estimate is high.

    An aggregate estimate above the 80% margin warns; it never forces
    batching, rejects the run, or alters compaction settings — the agent
    manages incremental work with its scratchpad and retrievable sections.
    """
    capacity = _normalized_capacity(capacity)
    low, high = estimate_token_range(int(history_chars))
    headroom = capacity.headroom_tokens
    if not capacity.known:
        return CapacityDecision(
            "unknown",
            (
                f"{label}: model capacity metadata is unavailable"
                + (f" ({capacity.discovery_error})" if capacity.discovery_error else "")
                + "; the run proceeds and PI enforces its own limit."
            ),
            (low, high),
            headroom,
        )
    if _headroom_exceeded(low, headroom):
        return CapacityDecision(
            "warn",
            (
                f"{label}: aggregate history estimate ({low}-{high} tokens) "
                f"exceeds the {CAPACITY_FRACTION:.0%} safety headroom "
                f"({headroom}). The run proceeds; expect PI compaction and "
                "rely on the scratchpad and submitted-section reads."
            ),
            (low, high),
            headroom,
        )
    return CapacityDecision("ok", "", (low, high), headroom)


# --- Model-visible component composition ---


def stage_static_components(
    project_pi_dir: Path,
    skill_name: str,
) -> dict[str, int]:
    """Character counts of the fixed, model-visible stage components."""
    system_chars = _file_chars(project_pi_dir / "SYSTEM.md")
    skill_chars = _file_chars(project_pi_dir / "skills" / skill_name / "SKILL.md")
    # The staged extension source proxies the enabled tool schemas: schemas
    # are declared there and Pi sends the generated JSON forms to the model.
    extension_chars = _file_chars(
        project_pi_dir / "extensions" / "recordprep-summary-tools.ts"
    )
    return {
        "system_prompt_chars": system_chars,
        "skill_chars": skill_chars,
        "tool_schema_proxy_chars": extension_chars,
        "envelope_overhead_chars": ENVELOPE_OVERHEAD_CHARS,
        "reasoning_allowance_chars": REASONING_ALLOWANCE_CHARS,
    }


def _file_chars(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8"))
    except OSError:
        return 0


def extraction_request_chars(
    static: dict[str, int],
    *,
    source_payload_chars: int,
    prompt_chars: int,
) -> int:
    """Model-visible chars for one extraction request (single tool result)."""
    return (
        sum(static.values())
        + int(source_payload_chars)
        + int(prompt_chars)
        + EXTRACTION_OUTPUT_ALLOWANCE_CHARS
    )


def synthesis_history_chars(
    static: dict[str, int],
    *,
    overview_chars: int,
    document_block_chars: Sequence[int],
) -> int:
    """Model-visible chars for one long-lived synthesis session.

    Counts the overview and the rendered Markdown blocks the dataset tool
    serves — never the internal canonical JSON rows, which the model does
    not receive — plus allowances for the generated sections and tool
    exchanges that accumulate in history.
    """
    generated = sum(
        SYNTHESIS_SECTION_ALLOWANCE_CHARS + SYNTHESIS_TOOL_EXCHANGE_ALLOWANCE_CHARS
        for _ in document_block_chars
    )
    return (
        sum(static.values())
        + int(overview_chars)
        + sum(int(block) for block in document_block_chars)
        + generated
    )


# --- Read-only diagnostic ---


def _largest_extraction_payload(
    root: Path,
    kind: str,
    config: Any,
    citation_by_page: dict[int, str],
) -> tuple[str | None, int]:
    from recordprep.summary_agents import item_source_payload

    largest_id: str | None = None
    largest_chars = -1
    for item in build_work_items(root, config):
        source = item_source_payload(item, root / "text_pages", citation_by_page)
        if len(source) > largest_chars:
            largest_chars = len(source)
            largest_id = item.item_id
    return largest_id, max(largest_chars, 0)


def collect_kind_report(
    root: Path,
    kind: str,
    project_dir: Path,
    extract_capacity: StageCapacity,
    synthesize_capacity: StageCapacity,
) -> dict[str, Any]:
    """Read-only report for one summary kind. Never publishes or locks."""
    from recordprep import summary_categories
    from recordprep.summary_agents import item_source_payload

    report: dict[str, Any] = {"kind": kind}
    try:
        config = _diagnostic_extraction_config(project_dir, kind)
        items = build_work_items(root, config)
    except (ValueError, summary_categories.SummaryResourceError) as exc:
        report["error"] = str(exc)
        return report

    text_dir = root / "text_pages"
    citation_by_page = _citation_map(root)
    payload_chars: dict[str, int] = {}
    for item in items:
        source = item_source_payload(item, text_dir, citation_by_page)
        payload_chars[item.item_id] = len(source)
    largest_id = max(payload_chars, key=lambda key: payload_chars[key]) if payload_chars else None

    rows = []
    markdown_error = ""
    try:
        rows = load_digest_markdown(root, kind)
    except ValueError as exc:
        markdown_error = str(exc)
    meta = load_digest_meta(root, kind)

    stale = []
    if rows:
        from recordprep.summary_agents import reconcile_digest_rows

        _ordered, stale = reconcile_digest_rows(rows, items)

    report.update(
        {
            "documents": len(items),
            "document_item_ids": [item.item_id for item in items],
            "largest_document_payload_chars": (
                payload_chars[largest_id] if largest_id else 0
            ),
            "largest_document_item_id": largest_id,
            "digest_rows_on_disk": len(rows),
            "digest_stale_item_ids": list(stale),
            "digest_meta_complete": (
                meta.get("complete") if isinstance(meta, dict) else None
            ),
            "digest_markdown_error": markdown_error,
        }
    )

    # Synthesis estimate: measured when the on-disk digest is complete and
    # current; otherwise flagged as extrapolated, never presented as measured.
    from recordprep import summary_agents as sa

    static = stage_static_components(project_dir, _synthesis_skill(kind))
    document_blocks = [
        len(sa.document_markdown_block(row)) for row in rows
    ]
    overview_chars = len(
        json.dumps(sa.build_dataset_overview(rows), ensure_ascii=True)
    )
    history = synthesis_history_chars(
        static, overview_chars=overview_chars, document_block_chars=document_blocks
    )
    decision = check_aggregate_history(
        synthesize_capacity, history, label=f"{kind} synthesis history"
    )
    if not rows:
        estimate_basis = "no digest on disk; estimate covers static components only"
    elif len(rows) < len(items) or bool(stale) or bool(markdown_error):
        estimate_basis = "extrapolated"
    else:
        estimate_basis = "measured on-disk digest blocks"
    report["synthesis"] = {
        **decision.payload(),
        "estimate_based_on": estimate_basis,
        "history_estimate_chars": history,
        "digest_markdown_chars": sum(
            len(sa.document_markdown_block(row)) for row in rows
        ),
    }

    # Individual extraction checks against the largest measured payloads.
    largest_decision = None
    if largest_id is not None:
        prompt_chars = _extraction_prompt_chars(config, kind)
        request = extraction_request_chars(
            stage_static_components(project_dir, _extraction_skill(kind)),
            source_payload_chars=payload_chars[largest_id],
            prompt_chars=prompt_chars,
        )
        try:
            largest_decision = check_individual_request(
                extract_capacity,
                request,
                label=f"{largest_id} extraction",
            ).payload()
        except PreflightError as exc:
            largest_decision = {"level": "fail", "message": str(exc)}
    report["largest_extraction_request"] = largest_decision
    return report


def _citation_map(root: Path) -> dict[int, str]:
    path = root / "artifacts" / "transcript_page_numbers.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    mapping: dict[int, str] = {}
    for item in payload.get("entries", []):
        if not isinstance(item, dict):
            continue
        try:
            page = int(item.get("file_page"))
        except (TypeError, ValueError):
            continue
        mapping[page] = str(item.get("citation_label") or "")
    return mapping


def _diagnostic_extraction_config(project_dir: Path, kind: str) -> Any:
    """Mirror the runner's extraction-config composition without GTK."""
    from recordprep import summary_agents as sa

    settings = _summary_stage_settings(project_dir, kind)
    resolution = sa.resolve_phase_guidance(kind, "extract", settings["extract_prompt"])
    return sa.ExtractionConfig(
        kind=kind,
        guidance=resolution.immutable_guidance,
        additional_guidance=resolution.custom_guidance,
        provider=settings["extract_provider"],
        model=settings["extract_model"],
        thinking=settings["extract_thinking"],
    )


def _summary_stage_settings(project_dir: Path, kind: str) -> dict[str, str]:
    config_path = project_dir.parent / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = {}
    config = config if isinstance(config, dict) else {}

    def value(key: str) -> str:
        return str(config.get(key, "") or "").strip()

    return {
        "extract_provider": value(f"summary_extract_{kind}_pi_provider")
        or value("summary_extract_pi_provider"),
        "extract_model": value(f"summary_extract_{kind}_pi_model")
        or value("summary_extract_pi_model"),
        "extract_thinking": value(f"summary_extract_{kind}_pi_thinking")
        or value("summary_extract_pi_thinking"),
        "synthesize_provider": value(f"summary_synthesize_{kind}_pi_provider")
        or value("summary_synthesize_pi_provider"),
        "synthesize_model": value(f"summary_synthesize_{kind}_pi_model")
        or value("summary_synthesize_pi_model"),
        "synthesize_thinking": value(f"summary_synthesize_{kind}_pi_thinking")
        or value("summary_synthesize_pi_thinking"),
        "extract_prompt": value(f"summarize_{kind}_prompt"),
        "synthesize_prompt": value(f"summarize_{kind}_synthesis_prompt"),
    }


def _extraction_skill(kind: str) -> str:
    from recordprep.summary_agents import SUMMARY_KIND_LABELS

    return f"recordprep-extract-{SUMMARY_KIND_LABELS[kind]}"


def _synthesis_skill(kind: str) -> str:
    from recordprep.summary_agents import SUMMARY_KIND_LABELS

    return f"recordprep-synthesize-{SUMMARY_KIND_LABELS[kind]}"


def _extraction_prompt_chars(config: Any, kind: str) -> int:
    from recordprep import summary_agents as sa

    parts = [
        config.guidance,
        "".join(
            f"- {definition.identifier}: {definition.guidance}\n"
            for definition in sa.summary_category_definitions(kind)
        ),
        config.additional_guidance,
    ]
    return sum(len(part) for part in parts)


def collect_report_pair(
    root: Path,
    kinds: Sequence[str],
    project_dir: Path,
    extract_capacities: dict[str, StageCapacity],
    synthesize_capacities: dict[str, StageCapacity],
) -> dict[str, Any]:
    """Compose the read-only report; one capacity per kind/phase."""
    report = {
        "artifact": ARTIFACT,
        "schema_version": SCHEMA_VERSION,
        "case_bundle": str(root),
        "capacities": {
            kind: {
                "extract": extract_capacities[kind].payload(),
                "synthesize": synthesize_capacities[kind].payload(),
            }
            for kind in kinds
            if kind in extract_capacities and kind in synthesize_capacities
        },
        "estimate_assumptions": {
            "chars_per_token": "UTF-8 bytes divided by 4 (low) to 3 (high)",
            "capacity_fraction": CAPACITY_FRACTION,
            "envelope_overhead_chars": ENVELOPE_OVERHEAD_CHARS,
            "tool_schema_proxy": "staged extension source characters",
            "extraction_output_allowance_chars": EXTRACTION_OUTPUT_ALLOWANCE_CHARS,
            "synthesis_section_allowance_chars": SYNTHESIS_SECTION_ALLOWANCE_CHARS,
            "synthesis_tool_exchange_allowance_chars": (
                SYNTHESIS_TOOL_EXCHANGE_ALLOWANCE_CHARS
            ),
            "reasoning_allowance_chars": REASONING_ALLOWANCE_CHARS,
            "note": (
                "Estimates are not tokenization guarantees; missing or stale "
                "digests make the synthesis estimate extrapolated, not measured."
            ),
        },
        "kinds": {},
    }
    for kind in kinds:
        if kind not in SUMMARY_KINDS:
            raise PreflightError(f"Unknown summary kind: {kind}")
        report["kinds"][kind] = collect_kind_report(
            root,
            kind,
            project_dir,
            extract_capacities[kind],
            synthesize_capacities[kind],
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m recordprep.summary_preflight",
        description=(
            "Read-only RecordPrep summary capacity and freshness diagnostic. "
            "Makes no paid calls, acquires no publishing lock, and writes no "
            "project, bundle, or configuration files."
        ),
    )
    parser.add_argument("--case-bundle", required=True, help="Case bundle root")
    parser.add_argument(
        "--kind",
        default="both",
        choices=("hearings", "reports", "both"),
        help="Which summary kind(s) to report",
    )
    parser.add_argument("--json", action="store_true", help="JSON output (default)")
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip PI model discovery; capacity stays explicitly unknown",
    )
    args = parser.parse_args(argv)

    root = Path(args.case_bundle).expanduser().resolve(strict=False)
    if not (root / "text_pages").is_dir():
        print(f"Case bundle is missing or invalid: {root}", file=sys.stderr)
        return 2
    project_dir = Path(__file__).resolve().parent.parent / ".pi"
    kinds = SUMMARY_KINDS if args.kind == "both" else (args.kind,)
    settings_path = project_dir / "settings.json"

    # One discovery result is reused for every kind/phase identity match.
    discovered: list[pi_runtime.PiModel] | None = None
    discovery_error = ""
    if not args.skip_discovery:
        try:
            pi_command = pi_runtime.resolve_pi_agent_argv(
                pi_runtime.discover_pi_agent_command()
            )
            discovered = pi_runtime.available_pi_models(pi_command)
        except (pi_runtime.PiRuntimeError, OSError, subprocess.SubprocessError) as exc:
            discovery_error = str(exc)

    def _capacity(kind: str, phase: str) -> StageCapacity:
        settings = _summary_stage_settings(project_dir, kind)
        if discovered is not None:
            return resolve_stage_capacity(
                settings, phase, settings_path, models=discovered
            )
        identity = resolve_stage_identity(settings, phase, settings_path)
        return StageCapacity(
            identity=identity,
            discovery_error=discovery_error or "PI model discovery failed.",
        )

    try:
        extract_capacities = {kind: _capacity(kind, "extract") for kind in kinds}
        synthesize_capacities = {kind: _capacity(kind, "synthesize") for kind in kinds}
        report = collect_report_pair(
            root, kinds, project_dir, extract_capacities, synthesize_capacities
        )
    except PreflightError as exc:
        print(f"Preflight failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2))
    failed = any(
        kind_report.get("largest_extraction_request", {}).get("level") == "fail"
        for kind_report in report["kinds"].values()
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
