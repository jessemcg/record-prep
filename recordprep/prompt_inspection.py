"""Offline inspection of RecordPrep-controlled instructions, not a live replay."""
from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from .classifier_prompts import classifier_document
from .document_naming import naming_document
from .profile_contract import CLASSIFICATION_PAGE_TYPES, CLASSIFICATION_FIRST_PAGE_TYPES, ProfileSnapshot
from .structured_guidance import effective_resource

CLASSIFICATION_TASKS = (
    ("rt", "RT page types"), ("ct", "CT page types"),
    ("first_hearing", "Hearing first page"), ("first_minute", "Minute-order first page"),
    ("first_form", "Form first page"), ("first_report", "Report first page"), ("first_motion", "Motion first page"), ("date_hearing", "Hearing dates"),
    ("date_minute", "Minute-order dates"), ("report", "Report Names"), ("form", "Form Names"), ("motion", "Motion Names"),
)
FIXED_TASKS = tuple(item for item in CLASSIFICATION_TASKS if item[0] not in {"report", "form", "motion"})
NAMING_TASKS = tuple(item for item in CLASSIFICATION_TASKS if item[0] in {"report", "form", "motion"})
SUMMARY_TASKS = (("hearings-extract", "Hearing digest"), ("hearings-synthesize", "Hearing narrative"),
                 ("reports-extract", "Report digest"), ("reports-synthesize", "Report narrative"),
                 ("motions-extract", "Motion digest"), ("motions-synthesize", "Motion narrative"), ("minutes", "Minute-order summary"))
TOOLS = {"extract": ("recordprep_get_source", "recordprep_submit_extraction"),
         "synthesize": ("recordprep_get_facts", "recordprep_submit_summary_section", "recordprep_finish_summary", "recordprep_synthesis_scratchpad"),
         "minutes": ("recordprep_get_minute_source", "recordprep_submit_minute_summary")}
PAGE_IMAGE_COMPONENT = ("Page image — attached separately",
                        "⟪The actual page image is attached separately to the request.⟫")


@dataclass(frozen=True)
class Inspection:
    components: tuple[tuple[str, str], ...]
    issues: tuple[str, ...] = ()

    def display_text(self):
        return "\n\n".join("===== " + label + " =====\n" + text for label, text in self.components)


@dataclass(frozen=True)
class DraftInspectionState:
    """A private copy of the complete editor draft, including unparsed buffers."""
    resources: dict
    raw_resources: tuple[tuple[str, str], ...]
    issues: tuple[str, ...]
    snapshot: ProfileSnapshot | None


def freeze_draft(editor, *, raw_resources=None) -> DraftInspectionState:
    from .profile_workflows import ProfileEditor
    from .profile_contract import _json
    draft = ProfileEditor(editor.base)
    draft.manifest = copy.deepcopy(editor.manifest)
    draft.resources = copy.deepcopy(editor.resources)
    raw = tuple((raw_resources or {}).items())
    issues = []
    for name, text in raw:
        try:
            draft.resources[name] = _json(text.encode('utf-8'), name)
        except (ValueError, OSError):
            # Never leave the last successfully parsed object masquerading as
            # this raw draft. Unrelated tasks may still be inspected literally.
            draft.resources.pop(name, None)
            issues.append(f"INCOMPLETE / INVALID DRAFT: Draft validation issue: invalid JSON in {name}. Literal raw text is shown; no executable naming prompt is available.")
    snapshot = None
    if not issues:
        try:
            snapshot = draft.snapshot()
        except (ValueError, OSError) as exc:
            code = exc.issue.code if hasattr(exc, 'issue') else 'invalid settings'
            issues.append("INCOMPLETE / INVALID DRAFT: Draft validation issue: " + code + ". Literal draft values remain inspectable.")
    return DraftInspectionState(copy.deepcopy(draft.resources), raw, tuple(issues), snapshot)


def tool_audit(project_dir: Path, phase: str):
    path = Path(__file__).parent / "resources/prompt-tools.json"
    try:
        manifest = json.loads(path.read_bytes())
        stale = [name for name, digest in manifest["sources"].items()
                 if hashlib.sha256((project_dir.parent / name).read_bytes()).hexdigest() != digest]
        extension = {"extract": "recordprep-summary-tools.ts", "synthesize": "recordprep-summary-synthesis-tools.ts",
                     "minutes": "recordprep-profile-minute-tools.ts"}[phase]
        registered = {t["name"]: t for t in manifest["definitions"][extension]}
        tools = [registered[name] for name in TOOLS[phase]]
        issues = []
        if stale:
            issues.append("INCOMPLETE / OUTDATED INSPECTION: source hashes differ: " + ", ".join(stale))
        audit = manifest.get('skill_command_audit', {})
        if not isinstance(audit, dict):
            audit = {}
        expected_skills = {'recordprep-extract-hearing', 'recordprep-extract-report',
                           'recordprep-synthesize-hearings', 'recordprep-synthesize-reports',
                           'recordprep-summarize-minutes', 'recordprep-extract-motion', 'recordprep-synthesize-motions'}
        if (audit.get('expands') is not True or audit.get('launch_prefix') != 'slash-skill followed by space'
                or not expected_skills.issubset(audit.get('skills', []))):
            issues.append("INSPECTION LIMITATION — the packaged audit does not verify Pi skill expansion. "
                          "The staged skill below is not verified model-visible; regenerate and validate the offline delivery audit.")
        return json.dumps(tools, ensure_ascii=False, indent=2), tuple(issues)
    except (OSError, ValueError, KeyError, TypeError):
        return "Tool audit unavailable.", ("INCOMPLETE INSPECTION: packaged tool schemas or tracked extension sources are unavailable.",)


def inspect_prompt(resources: dict, task: str, project_dir: Path, *, template=True, snapshot=None,
                   draft: DraftInspectionState | None = None, contract=None) -> Inspection:
    if task in dict(FIXED_TASKS):
        # Application rules remain inspectable even when a draft/store is invalid.
        return Inspection((("System message", classifier_document(task, contract).render()), PAGE_IMAGE_COMPONENT))
    if task == "minutes":
        # Fixed inspection never depends on unrelated draft validity or resources.
        return _inspect_prompt({}, task, project_dir)
    if draft is not None:
        resources, snapshot = draft.resources, draft.snapshot
        raw = dict(draft.raw_resources)
        if not template and task in ('report', 'form') and 'naming' in raw and snapshot is None:
            return Inspection((("Current draft — literal naming JSON (not compiled)", raw['naming']),),
                              draft.issues or ("INCOMPLETE / INVALID DRAFT: naming has not validated.",))
    result = _inspect_prompt(resources, task, project_dir, template=template, snapshot=snapshot)
    issues = (*draft.issues, *result.issues) if draft else result.issues
    return Inspection(result.components, tuple(dict.fromkeys(issues)))


def _inspect_prompt(resources: dict, task: str, project_dir: Path, *, template=True, snapshot=None) -> Inspection:
    resources = copy.deepcopy(resources)
    if task == "motion":
        from .document_naming import source_title_document
        naming = resources.get("motion_naming", {"schema_version": 1, "motions": []})
        if template:
            naming = {"schema_version": 1, "motions": [{"id": "⟪stable internal ID⟫", "name": "⟪fallback name⟫", "guidance": "⟪eligibility description⟫", "naming_mode": "source_title"}]}
        return Inspection((("System message", source_title_document(naming, "motion").render()), PAGE_IMAGE_COMPONENT))
    if task in dict(CLASSIFICATION_TASKS):
        if task in ("report", "form"):
            naming = effective_resource(resources["naming"], "naming")
            if naming.get("schema_version") in (4, 5):
                if template:
                    modes = list(dict.fromkeys(e.get("naming_mode", "fixed") for e in naming[task + "s"])) or ["fixed"]
                    naming[task + "s"] = [{"id": "⟪stable internal ID⟫", "name": "⟪approved name or fallback⟫",
                                           "guidance": "⟪eligibility description⟫",
                                           **({"naming_mode": mode} if mode == "source_title" else {})}
                                          for mode in modes]
                prompt = naming_document(naming, task).render()
            elif snapshot is not None and not template:
                from .document_naming import compile_naming_profile
                prompt = compile_naming_profile(snapshot, task).prompt
            else:
                # No guessed splitting or bundled substitution for legacy drafts.
                from .document_naming import _CORE, _REPORT, _FORM
                prompt = _CORE + (_REPORT if task == "report" else _FORM) + "\nSaved naming guidance:\n" + ("⟪legacy naming resource⟫" if template else json.dumps(naming, ensure_ascii=False, indent=2))
                return Inspection((("System message", prompt), PAGE_IMAGE_COMPONENT),
                                  ("Compatibility naming inspection is incomplete until this draft validates; literal resource shown without substitution.",))
        return Inspection((("System message", prompt), PAGE_IMAGE_COMPONENT))

    from .summary_profiles import profile_skill_text, draft_summary_guidance
    from .summary_prompts import extraction_document, synthesis_document, minute_document
    if task == "minutes":
        from .minute_summaries import application_guidance
        skill = "recordprep-summarize-minutes"
        skill_text = (project_dir / "skills" / skill / "SKILL.md").read_text()
        launch = minute_document({"guidance": application_guidance()}).render()
        phase = "minutes"
        runtime = "⟪complete boundary-scoped minute order source pages, source labels and document metadata⟫\n⟪private candidate path⟫"
    else:
        kind, phase = task.split("-", 1)
        skill = {("hearings", "extract"): "recordprep-extract-hearing", ("reports", "extract"): "recordprep-extract-report",
                 ("hearings", "synthesize"): "recordprep-synthesize-hearings", ("reports", "synthesize"): "recordprep-synthesize-reports",
                 ("motions", "extract"): "recordprep-extract-motion", ("motions", "synthesize"): "recordprep-synthesize-motions"}[(kind, phase)]
        skill_text = profile_skill_text(project_dir, skill, phase)
        from .motion_guidance import MOTION_TOPICS
        catalog = resources.get(kind, MOTION_TOPICS if kind == "motions" else []) if not template else [{"id": "⟪topic-id⟫", "title": "⟪topic name⟫", "guidance": "⟪topic instructions⟫"}]
        guidance = draft_summary_guidance(catalog, kind, phase)
        if phase == "extract":
            config = SimpleNamespace(guidance=guidance, additional_guidance="", definitions=[SimpleNamespace(identifier=c.get("id", ""), guidance=c.get("guidance", "")) for c in catalog])
            item = SimpleNamespace(item_id="⟪document ID⟫", ordinal="⟪ordinal⟫", label="⟪document label⟫", start_page="⟪first page⟫", end_page="⟪last page⟫")
            launch = extraction_document(skill, item, config, "⟪private candidate path⟫").render()
            runtime = "⟪complete document source pages and citation labels⟫\n" + ("⟪hearing participant context — for attribution only⟫" if kind == "hearings" else "")
        else:
            launch = synthesis_document(skill, "⟪digest row count⟫", {"guidance": guidance}, "⟪private candidate path⟫").render()
            runtime = "⟪digest dataset overview, document metadata, Markdown digest blocks and exact quote IDs⟫\nSubsequent tool results, scratchpad contents and model-generated exchanges are dynamic, not omitted fixed instructions."
    tools, issues = tool_audit(project_dir, phase)
    return Inspection((("Application system instructions", (project_dir / "SYSTEM.md").read_text()),
                       ("Staged skill: " + skill, skill_text), ("Launch message (before Pi skill expansion)", launch),
                       ("Active tools — names, descriptions and JSON schemas", tools), ("Runtime data placeholders", runtime)), issues)
