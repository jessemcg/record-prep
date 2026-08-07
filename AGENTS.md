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
- `recordprep/documents.py`: PDF merge, extraction, rendering, and OCR import surface.
- `recordprep/pi_runtime.py`: PI discovery/model settings.
- `recordprep/pi_bundle.py`: PI artifact/schema validation.
- `.pi/`: tracked system prompt, four project-local Agent Skills, sequential runner, and auto-exit extension.

Do not add a root-level `recordprep.py` shim. Use modern Libadwaita widgets and flat buttons.

## Pipeline

1. Create files.
2. Strip characters.
3. Infer case.
4. Basic/advanced/corrected/date/name classification.
5. Build/correct TOC.
6. Find/correct hearing, report, and minute boundaries.
7. Number transcript pages with PI.
8. Build `artifacts/participant_index.json` schema v2 with PI from appearances, express attendance/absence, unsworn colloquy, RT witness indexes, and sworn/examination evidence.
9. Create summaries directly from boundary-scoped source pages through ephemeral page windows.
10. Add summary links.
11. Create the concise nonauthoritative `artifacts/case_overview.md` orientation aid.
12. Build source-map v2 last.

The participant index is hearing-scoped and separates counsel, non-counsel participants, and witnesses. Law firms/agencies are organizations, not attorney aliases. Q/A alone is not testimony. Unknown/conflicting identity, attendance, witness, or counsel evidence must remain explicit rather than guessed.

Summary windows keep pages intact and adapt toward a 6,000-character target, with defaults of six primary pages maximum and a 12,000-character safety limit; one oversized page remains intact. They include a preceding context-only page where useful, prefer examination boundaries, and are never persisted. Do not reinterpret the retired paragraph-count setting as a page count. The complete hearing and report prompts shown in Settings must explain their labeled input sections; do not append a hidden attribution contract. Normalize each page-window response to one prose paragraph and insert one blank line between adjacent hearing or report paragraphs deterministically rather than depending on model-supplied trailing whitespace. Each hearing request receives validated participant-index context privately under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY`. Treat source pages as factual authority, do not publish counsel/participant rosters or standalone testimony-status lines, reject/retry known-bad attribution, and fail rather than save a known false testimony claim.

The case overview is a schema-versioned orientation aid derived from source summaries and participant metadata. It is never authoritative evidence and must be regenerated when those inputs change.

Source-map v2 uses original `text_pages`, boundaries, transcript citation metadata, participants, examinations, warnings, the case-overview path, and summary paths. Only source pages are authoritative evidence.

## PI rules

- Keep every RecordPrep PI resource under tracked `.pi/`.
- Invoke one explicit skill per UI row with `.pi/scripts/run_recordprep_skill.py`.
- Stage `.pi/SYSTEM.md` and only `extensions/recordprep-auto-exit.ts` into a private workspace.
- Preserve PI's native interactive VTE UI.
- Validate each stage after PI exits.
- Transcript numbering and participant/summary stages must not update `manifest.json`.
- The case-overview skill writes only `artifacts/case_overview.md`.
- The final source-map skill is the single manifest publisher.
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
