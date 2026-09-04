# RecordPrep Agent Notes

## Goal

RecordPrep converts OCR-readable legal-record PDFs into direct-source, citation-aware case bundles for Focus Agent search. It may create one concise, versioned, nonauthoritative case-orientation overview, but it must not create retrieval/optimization copies, persistent chunks, speaker-labeled transcript rewrites, embeddings, or vector databases.

## Entry points and modules

- `recordprep/cli.py`: command parser.
- `python -m recordprep app`: GTK application entry.
- `recordprep/ui/main_window.py`: Libadwaita UI, settings, direct-source pipeline, summary windows, and step handlers.
- `recordprep/classification.py`: classification worker pool.
- `recordprep/config.py`: supported settings import surface.
- `recordprep/manifest.py`: manifest import surface.
- `recordprep/summaries.py`: summary path/link import surface.
- `recordprep/summary_editions.py`: page-matched Letter PDF editions and Focus page maps.
- `recordprep/documents.py`: PDF merge, extraction, rendering, and OCR import surface.
- `recordprep/pi_runtime.py`: PI discovery/model settings.
- `recordprep/pi_bundle.py`: PI artifact/schema validation.
- `.pi/`: tracked system prompt, four project-local Agent Skills, sequential runner, and auto-exit extension.

Do not add a root-level `recordprep.py` shim. Use modern Libadwaita widgets and flat buttons.

## Pipeline

1. Create files.
2. Detect transcript layout (PI).
3. Strip characters.
4. Infer case.
5. Basic/advanced/corrected/date/name classification.
6. Build/correct TOC.
7. Find/correct hearing, report, and minute boundaries.
8. Number transcript pages with PI.
9. Build `artifacts/participant_index.json` schema v2 with PI from appearances, express attendance/absence, unsworn colloquy, RT witness indexes, and sworn/examination evidence.
10. Create summaries in three independently runnable stages — hearing, report, and minute-order — each directly from its own boundary-scoped source pages through ephemeral page windows. Each stage writes only its own summary file and completes independently; hearing generation requires the validated participant index, while report and minute-order generation do not.
11. Add summary links (hearing summary only).
12. Build page-matched summary editions deterministically: after Add Links, render each summary into a fixed US-Letter PDF and a schema-v1 page-map sidecar under `summaries/editions/`. The PDF is the immutable pagination authority (Letter portrait, 72-point margins, 12-point serif body, `Page N of M` footer, numbering restarting at 1 per category). The sidecar records per-page selectable body text, trusted record-page link spans and targets, inclusive source-line ranges, and source/PDF hashes; generation verifies normalized page text reproduces the printable source exactly and fails rather than dropping a link. Build and validate all three candidates before replacing any edition, publish PDF then sidecar atomically, and invalidate only the rerun category's edition after a summary or Add Links text change. Editions are never Agent evidence or source-map search paths. RecordPrep/`summary_editions.py` owns this logic, re-exported through `recordprep/summaries.py`.
13. Create the concise nonauthoritative `artifacts/case_overview.md` orientation aid.
14. Build source-map v2 last.

Transcript layout detection runs immediately after Create files, once per new
or changed bundle, and publishes `artifacts/transcript_layout.json` schema v1.
It searches OCR text first and opens only targeted page images (soft budget of
12 PNGs per detection), never a full image sweep. A high-confidence agent
result continues automatically; ambiguity publishes a structurally valid
`needs_review` artifact and pauses before any layout-dependent mutation.
Layouts are case-local, bound to the current page count and input signature;
a value from another case is never used. RecordPrep may atomically rebind an
unchanged, resolved decision after its own guarded text-only normalization.
It must rerun detection when numbered page identity or paired images change,
or when text changes outside that controlled pass. All downstream routing
reads the validated artifact; the manifest `rt_ct_split_mode`/`rt_ct_split_page` fields
are legacy compatibility mirrors only. The retired `rt_ct_split_page` config
key is removed during config migration.

The participant index is hearing-scoped and separates counsel, non-counsel participants, and witnesses. Its helper publishes a temporary, nonauthoritative worklist under `temp/` that scopes first/appearance pages, RT-index pages, and oath/examination/attendance markers without copying source-page text. The agent processes one hearing at a time, reads single source pages, persists completed hearings incrementally, and uses partial validation after batches of at most five hearings. It must never concatenate the complete RT or a multi-hundred-page run. Full validation rejects the unreviewed template placeholder. Law firms/agencies are organizations, not attorney aliases. Q/A alone is not testimony. Unknown/conflicting identity, attendance, witness, or counsel evidence must remain explicit rather than guessed.

Summary windows keep pages intact and adapt toward a 6,000-character target, with defaults of six primary pages maximum and a 12,000-character safety limit; one oversized page remains intact. They include a preceding context-only page where useful, prefer examination boundaries, and are never persisted. Report windows remain page-intact: a formal package of proposed/recommended advisements, findings, orders, and associated boilerplate offered for court adoption is out of summary scope. A conservative, ephemeral detector recognizes only bounded structural signatures (a `PROPOSED`/`RECOMMENDED FINDINGS AND ORDERS` title, a formal lead-in asking the court to make the following findings and orders, a split proposed-findings-then-proposed-orders template, or a proposal expressly asking the court to `find`/`order`); it never fires on a generic recommendation heading, a change-in-recommendation note, a substantive treatment/assessment recommendation, a singular assessment-order request, or narrative references to orders the court already made. Actual historical orders and a high-level agency recommendation stated apart from the formal template remain distinguishable and in scope. Detection is carried only as a non-sensitive page/offset/line/kind marker; matched text is never logged or persisted. A proposal-only window returns the exact `NO_SUMMARIZABLE_REPORT_CONTENT` sentinel, which RecordPrep skips, and natural-language output is never regex-filtered, validated, or repaired after generation. The built-in report prompt requires at least six legally significant verbatim quotes per window whenever the eligible primary material contains six suitable quotations, each an uninterrupted two-to-five-word sequence drawn only from eligible material; when fewer exist it requires every suitable quotation instead of invented, altered, insignificant, or out-of-scope language, and asks for the quotations to be distributed across material facts, observations, interviews, and assessments without sacrificing factual coverage. Prompt instructions remain nonbinding guidance: no quote counting, rejection, retry, or repair is applied to model output. Do not reinterpret the retired paragraph-count setting as a page count. The complete hearing and report prompts shown in Settings must explain their labeled input sections; do not append a hidden attribution contract. Normalize each page-window response to one prose paragraph and insert one blank line between adjacent hearing or report paragraphs deterministically rather than depending on model-supplied trailing whitespace. Each hearing request receives validated participant-index context privately under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY`. The prompt should discourage counsel/participant rosters, standalone testimony-status lines, and unsupported testimony attribution, but RecordPrep must not apply deterministic model-output attribution validation, rejection, or repair requests. Summaries are nonauthoritative; source pages remain the factual authority.

The case overview is a schema-versioned orientation aid derived from source summaries and participant metadata. It is never authoritative evidence and must be regenerated when those inputs change.

Source-map v2 uses original `text_pages`, boundaries, transcript citation metadata, participants, examinations, warnings, the case-overview path, and summary paths. Only source pages are authoritative evidence.

## PI rules

- Keep every RecordPrep PI resource under tracked `.pi/`.
- Invoke one explicit skill per UI row with `.pi/scripts/run_recordprep_skill.py`.
- Stage `.pi/SYSTEM.md` and only `extensions/recordprep-auto-exit.ts` into a private workspace.
- Preserve PI's native interactive VTE UI.
- Validate each stage after PI exits.
- The runner monitors session-file growth and child CPU state. Sustained high CPU with no session progress produces a visible stalled-stage warning but never kills PI automatically; the user must press Stop.
- Stop signals the runner, terminates PI's complete process group, escalates to SIGKILL only when SIGTERM fails, restores the row to Pending, and prevents downstream stages from starting.
- PI launch logs the immutable bundle root. RecordPrep warns when a parent folder's apparent appellate case number conflicts with manifest/PDF identity, but never moves or renames private case data.
- The transcript-layout skill writes only `artifacts/transcript_layout.json`; the runner accepts a structurally valid `needs_review` artifact, while RecordPrep treats only a resolved, fresh artifact as step completion.
- Transcript numbering and participant/summary stages must not update `manifest.json`.
- The case-overview skill writes only `artifacts/case_overview.md`.
- The final source-map skill is the single manifest publisher and also publishes the `transcript_layout` path.
- Do not add an agent framework, subagent abstraction, or runtime npm install.

## Source extraction

- Use `pdftotext` with `physical=True` for `text_pages/0001.txt`, etc.
- Render grayscale 300-DPI `image_pages/0001.png`, etc., with PyMuPDF.
- Preserve source page identity and never place private case content in tests or commits.

## Development commands

```bash
uv run python -m recordprep app
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
python3 .pi/scripts/run_recordprep_skill.py --validate-resources
```

Use the Agent Skill validator for every changed skill. Keep `pyproject.toml` and tracked `uv.lock` synchronized. GTK4 VTE, PI 0.80+, and Node 20+ are system/runtime dependencies.
