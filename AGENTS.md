# RecordPrep Agent Notes

## Goal

RecordPrep converts OCR-readable legal-record PDFs into direct-source, citation-aware case bundles for Focus Agent search. It may create one concise, versioned, nonauthoritative case-orientation overview, but it must not create retrieval/optimization copies, persistent chunks, speaker-labeled transcript rewrites, embeddings, or vector databases.

## Entry points and modules

- `recordprep/cli.py`: command parser.
- `python -m recordprep app`: GTK application entry.
- `recordprep/ui/main_window.py`: Libadwaita UI, settings, direct-source pipeline (minute orders), summary stage settings, and step handlers (hearing/report summary handlers are thin wrappers around `_run_pi_skill_step`).
- `recordprep/classification.py`: classification worker pool.
- `recordprep/config.py`: supported settings import surface.
- `recordprep/manifest.py`: manifest import surface.
- `recordprep/summaries.py`: summary path/link import surface.
- `recordprep/summary_editions.py`: page-matched Letter PDF editions and Focus page maps.
- `recordprep/summary_agents.py`: two-stage PI summary pipeline — category schemas, work items, fingerprints, canonical JSONL/meta publication with per-kind locks, quote span resolution, recurrence analysis, synthesis validation, and deterministic rendering.
- `recordprep/documents.py`: PDF merge, extraction, rendering, and OCR import surface.
- `recordprep/pi_runtime.py`: PI discovery/model settings, model context metadata, and summary context preflight.
- `recordprep/pi_bundle.py`: PI artifact/schema validation (including both summary PI stages).
- `.pi/`: tracked system prompt, project-local Agent Skills, sequential runner, auto-exit extension, and summary-tools extension.

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
10. Create summaries in three independently runnable stages. Hearing and report stages run the resumable two-stage PI pipeline (`recordprep/summary_agents.py` + `.pi/extensions/recordprep-summary-tools.ts`): stage one launches one fresh `--mode json --no-session` PI process per document whose only tools are `recordprep_get_source` (the document's complete source pages in one payload) and `recordprep_submit_extraction`; Python independently validates the structured candidate (exact category ids/order, `facts: null` semantics, page scope, two-to-twelve-word contiguous verbatim quotes matched to the declared page, report proposal cutoff) and is the sole canonical JSONL/metadata publisher under an exclusive per-kind lock with atomic replace and a final newline. Stage two launches one fresh PI process per completed JSONL with dataset-only tools, validates exact section order, category coverage/duplicate-suppression accounting, `{{quote:<id>}}`-only placeholders, evidence reuse, and long repeated shingles, then a deterministic renderer publishes the final text plus final metadata atomically. Item IDs are stable by kind and start page; changed end pages, labels, source text, prompts, models, or reasoning change generation fingerprints only. Each stage writes only its own final summary file (`hearings_sum_<case>.txt` / `reports_sum_<case>.txt`) and completes independently; hearing extraction requires the validated participant index, while report extraction does not. A zero-item boundary set publishes an empty JSONL/meta and a title-only summary without a paid call. The minute-order stage keeps the direct API path and writes only `minutes_sum_<case>.txt`.
11. Add summary links (hearing summary only).
12. Build page-matched summary editions deterministically: after Add Links, render each summary into a fixed US-Letter PDF and a schema-v1 page-map sidecar under `summaries/editions/`. The PDF is the immutable pagination authority under the fixed `recordprep-summary-letter-v2` layout (Letter portrait, 54-point margins, 11-point body, 1.18 line height, 0.5em paragraph spacing, `Page N of M` 9-point Times footer, numbering restarting at 1 per category). The body renders with PyMuPDF's built-in Times-compatible Nimbus Roman face, requested through the CSS `Times` family, so pagination is deterministic and never depends on locally installed fonts, Fontconfig, or any external font file. The sidecar layout metadata records the complete typography contract and validation rejects any sidecar whose layout ID or fixed metrics differ, so pre-v2 editions show the build step as pending until rebuilt (old editions remain untouched until a successful rebuild). The sidecar records per-page selectable body text, trusted record-page link spans and targets, inclusive source-line ranges, and source/PDF hashes; generation verifies normalized page text reproduces the printable source exactly and fails rather than dropping a link. Build and validate all three candidates before replacing any edition, publish PDF then sidecar atomically, and invalidate only the rerun category's edition after a summary or Add Links text change. Editions are never Agent evidence or source-map search paths. RecordPrep/`summary_editions.py` owns this logic, re-exported through `recordprep/summaries.py`.
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

Summary extraction serves each document's complete source pages in one payload — PI extraction is not windowed, and there are no PI extraction window settings. Page-intact adaptive windows remain only where each window is a separate direct-API request: minute orders (6,000 characters/six primary pages by default, under the 12,000-character primary-source safety limit; a target above the limit is normalized to it, one oversized page remains intact, examination breaks are preferred, and a preceding context-only page may be included) and the prompt-testing sandbox, which uses built-in defaults for hearings and reports. Window size is a batching control only and never a direct output-length rule. Narrative density in synthesis is guided by a soft words-per-report target (`summarize_reports_window_target_words`, default 250, `0` disables it), attached as an ephemeral `REPORT SUMMARY LENGTH GUIDANCE — FOR OUTPUT SHAPE ONLY` section to the report synthesis prompt: prompt guidance about output shape only — never an API token cap, truncation rule, validator, retry, or repair pass.

A formal package of proposed/recommended advisements, findings, orders, and associated boilerplate offered for court adoption is out of summary scope. A conservative, ephemeral detector recognizes only bounded structural signatures (a `PROPOSED`/`RECOMMENDED FINDINGS AND ORDERS` title, a formal lead-in asking the court to make the following findings and orders, a split proposed-findings-then-proposed-orders template, or a proposal expressly asking the court to `find`/`order`); it never fires on a generic recommendation heading, a change-in-recommendation note, a substantive treatment/assessment recommendation, a singular assessment-order request, or narrative references to orders the court already made. Actual historical orders and a high-level agency recommendation stated apart from the formal template remain distinguishable and in scope. Detection is carried only as a non-sensitive page/offset/line/kind marker; matched text is never logged or persisted. Report extraction inserts the scope delimiter at the marker in the source payload and Python rejects evidence quotes from pages past the cutoff.

Canonical facts rows carry trusted Python-injected metadata (schema version 1, kind, stable item id by kind and start page, ordinal, label, page range, source and generation fingerprints) and categories in exact configured order: hearings use `parent_appearances`, `evidence_considered`, `testimony`, `disputed_legal_issues`, `party_positions_and_reasons`, `court_orders_and_reasons`; reports use the expanded twelve-category schema ending in `placement_and_caregiver_adoption_approval`. `facts` is exactly `null` when the source has no responsive information; empty arrays and absence explanations are rejected. Every fact needs at least one verified evidence quote: a short contiguous verbatim span (two to twelve words, no ellipsis or line break) matched against the declared page after Unicode/whitespace normalization, with Python recording the original offsets, canonical quote id, and page hash. Ambiguous matches are rejected so the agent can choose a more distinctive phrase. Stage one records developments described as current/recent by a report; stage two determines what is genuinely new. Synthesis validation additionally enforces exact section order, category coverage or duplicate-suppression accounting (suppression only when facts are demonstrably carried forward), `{{quote:<id>}}`-only quotation placeholders, no reuse of an earlier report's evidence quote, and rejection of long repeated narrative shingles across report sections; all-null report rows render the deterministic `NO_SUMMARIZABLE_REPORT_CONTENT` sentinel under their required document heading.

Each summary category has its own built-in prompt migration chain, so previously shipped built-ins advance to the new guidance while custom prompts remain byte-for-byte unchanged and are wrapped as lower-priority additional guidance that cannot override the immutable schema, scope, quote, and safety contracts. Do not reinterpret the retired paragraph-count setting as a page count. The complete hearing and report guidance shown in Settings must explain their labeled input sections; do not append a hidden attribution contract. The hearing source payload includes validated participant-index context privately under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY` as attribution context only; every submitted fact still requires evidence from original hearing pages. Summaries are nonauthoritative; source pages remain the factual authority.

The case overview is a schema-versioned orientation aid derived from source summaries and participant metadata. It is never authoritative evidence and must be regenerated when those inputs change.

Source-map v2 uses original `text_pages`, boundaries, transcript citation metadata, participants, examinations, warnings, the case-overview path, and summary paths. Only source pages are authoritative evidence.

## PI rules

- Keep every RecordPrep PI resource under tracked `.pi/`.
- Invoke one explicit skill per UI row with `.pi/scripts/run_recordprep_skill.py`.
- Native VTE stages stage `.pi/SYSTEM.md`, one skill, and only `extensions/recordprep-auto-exit.ts` into a private workspace. Summary stages stage `.pi/SYSTEM.md`, the phase skill, and only `extensions/recordprep-summary-tools.ts`, with `--mode json --no-session --approve`, an exact custom-tool allowlist, optional runner-owned `--provider`/`--model`/`--thinking` overrides, and a unique private cache workspace and candidate path removed in `finally`.
- Preserve PI's native interactive VTE UI for the native stages.
- Validate each stage after PI exits; summary children publish only after Python-side validation of the candidate.
- The runner monitors session-file growth and child CPU state for native stages and JSON-event activity for summary children. Sustained activity without progress produces a visible stalled-stage warning but never kills PI automatically; the user must press Stop.
- Stop signals the runner, terminates the active child's complete process group, escalates to SIGKILL only when SIGTERM fails, releases locks, restores the row to Pending, and prevents the next child or downstream stages from starting.
- PI launch logs the immutable bundle root. RecordPrep warns when a parent folder's apparent appellate case number conflicts with manifest/PDF identity, but never moves or renames private case data. Summary child output never contains prompts, source text, tool arguments/results, model prose, or JSONL facts — only phase, ordinal/count, event class, PID, elapsed/stall information, and sanitized error codes.
- Harden executable resolution before any `--version` or agent spawn: never attempt a nonexistent configured path; rediscover only for `pi` or a known legacy default location and fail early with the discovered alternative for an arbitrary missing custom command. The summary-resource minimum is PI 0.85 while Node 20+ stays a documentation-level dependency; never hard-code an absolute installer path.
- The transcript-layout skill writes only `artifacts/transcript_layout.json`; the runner accepts a structurally valid `needs_review` artifact, while RecordPrep treats only a resolved, fresh artifact as step completion.
- Transcript numbering, participant, and summary stages must not update `manifest.json`.
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

Use the Agent Skill validator for every changed skill. Keep `pyproject.toml` and tracked `uv.lock` synchronized. GTK4 VTE, PI 0.85+ (0.80+ for the native stages), and Node 20+ are system/runtime dependencies.
