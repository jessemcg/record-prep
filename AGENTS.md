# Record Prep Agent Notes

Project goal:
- GTK4/Libadwaita Python app named "Record Prep" that processes OCR'd legal transcript PDFs into summaries and helper files.

Entry points:
- `recordprep/cli.py` defines the command parser.
- `python -m recordprep app` launches the GTK app.
- `recordprep/app.py` delegates to the GTK launcher.
- Do not add a root-level `recordprep.py` shim.

Module outline:
- `recordprep/ui/main_window.py`: main GTK UI, pipeline orchestration, settings/test windows, and step handlers.
- `recordprep/classification.py`: reusable classification worker-pool helper.
- `recordprep/config.py`: settings import surface; root-level `config.json` remains the runtime settings file.
- `recordprep/manifest.py`: manifest helper import surface.
- `recordprep/summaries.py`: summary path and page-link helper import surface.
- `recordprep/documents.py`: PDF merge, text extraction, image rendering, and OCR helper import surface.
- `recordprep/optimization.py`: raw/preoptimized/optimized text helper import surface.
- `recordprep/rag.py`: embedding/RAG helper import surface.
- `recordprep/prompts.py`: default prompt import surface.
- `recordprep/pi_runtime.py`: PI executable/model discovery and project model settings.
- `recordprep/pi_bundle.py`: per-skill Agent Refinement artifact validation.
- `.pi/`: tracked PI settings, four project-local skills, and the sequential skill runner.

UI expectations:
- Follow patterns from `example_python_GTK4_app/focus.py` when implementing new UI features.
- Header bar: case bundle picker + PDF picker on the left, status spinner/label in the center, hamburger menu on the right.
- Main view: "Run all", "Stop", "Resume", and "Edit TOC" buttons plus a boxed list of pipeline step rows.
- Settings: custom `SettingsWindow` (Adw.ApplicationWindow) with a navigation list and prompt editor stack; Save Settings triggers `app.save-settings`.

Pipeline steps (current):
- Create files: create `case_bundle/text_pages` and `case_bundle/image_pages` next to the PDFs. If multiple PDFs are chosen, merge them (natural sort order) into `case_bundle/temp/merged.pdf` first.
- Strip characters: remove non-printing characters from extracted text files.
- Infer case: infer the case name from the first pages and write `case_bundle/case_name.txt`.
- Classification basic: create RT/CT basic classification JSONL files for every page.
- Advanced classification: annotate hearing last pages and minute/form first pages.
- Correct advanced classification: fix consecutive first-page markers.
- Classification dates: add dates for hearing and minute order first pages.
- Classification names: add report/form names.
- Build TOC: generate `artifacts/toc.txt`.
- Correct TOC: remove duplicate minute order dates in the TOC.
- Find boundaries: write `artifacts/hearing_boundaries.json`, `artifacts/report_boundaries.json`, and `artifacts/minutes_boundaries.json`.
- Correct boundaries: remove invalid hearing/report boundaries.
- Create raw: write `artifacts/raw_hearings.txt` and `artifacts/raw_reports.txt`.
- Create pre-optimized: write chunk files under `artifacts/preoptimized/`.
- Create optimized: write optimized hearing/report outputs.
- Create summaries: write case-named summary files in `summaries/`.
- Add links to summaries: add hearing/minute links to the hearings summary only.
- Case overview: write `rag/case_overview.txt`.
- Create RAG index: build `rag/vector_database` with VoyageAI or Isaacus + Chroma.
- Agent Refinement: run four separate PI-backed steps in order: transcript page
  numbering, hearing-summary organization, report-summary organization, and
  source-map generation. Source-map generation must remain last.

PI workflow rules:
- Keep every RecordPrep-specific PI resource under tracked `.pi/`.
- Invoke one project-local skill per UI row with `.pi/scripts/run_recordprep_skill.py`.
- Run PI's native interactive terminal UI directly inside VTE, with terminal
  input, its model indicator, ANSI colors, and diff rendering intact.
- After the user exits PI, validate the stage output before advancing.
- The first three skills must not update `manifest.json`; the final source-map
  skill is the single manifest writer.
- All skills inherit the provider/model in `.pi/settings.json`.
- Do not add an agent extension, custom subagent abstraction, or runtime npm install.

Step 1 implementation details:
- Use `pdftotext` with `physical=True` to create per-page text files named `0001.txt`, `0002.txt`, etc.
- Render grayscale PNGs at 300 DPI named `0001.png`, `0002.png`, etc. using PyMuPDF.

Development commands:
- `uv run python -m recordprep app`: launch the app.
- `uv run python -m unittest discover -s tests`: run tests.
- `uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py`: compile check.
- `python3 .pi/scripts/run_recordprep_skill.py --validate-resources`: validate PI resources.

Dependencies:
- Keep `pyproject.toml` current via `uv add` when adding Python dependencies.
- GTK4 VTE, PI 0.80+, and Node 20+ are system/runtime dependencies, not Python packages.
