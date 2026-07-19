# Record Prep

<img src="recordprep_icon.png" alt="Record Prep icon" width="128" align="left">

Record Prep is a GTK4/Libadwaita desktop app that turns OCR'd legal transcript PDFs into a structured
case bundle with classifications, summaries, and retrieval-ready artifacts for appellate workflows.

- Functional GTK4/Libadwaita desktop UI with the full pipeline exposed as step-by-step actions.
- Modular Python package under `recordprep/`, with the GTK orchestration in `recordprep/ui/main_window.py`.
- Settings are stored in the ignored root-level `config.json` and cover API URLs, model IDs, keys, and prompts.
- Local OCR defaults to a llama.cpp server, while remote steps use configurable API providers.
- RAG output targets VoyageAI or Isaacus embeddings with a Chroma vector store.
- Activity is always visible in a fixed-height, embedded GTK4 VTE terminal.
- RT + CT pipelines require the last RT page before any pipeline action can start.
- The final Agent Refinement phase runs four project-local PI skills in order
  and streams their live output in the embedded terminal.

## What it does
- Imports one or more PDFs, merged in natural sort order when needed.
- Extracts per-page text and grayscale page images.
- Classifies pages, adds dates/names, and builds a table of contents.
- Finds hearing/report/minute order boundaries.
- Generates raw and optimized text, summaries, and a case overview.
- Stores chunk metadata separately from optimized chunk text and writes per-chunk JSONL artifacts.
- Optionally builds a VoyageAI/Chroma or Isaacus/Chroma RAG index from optimized hearing/report content, with similarity search filters driven by chunk metadata such as hearing date and report name.

## Requirements
- Python 3.13+
- GTK4/Libadwaita via `pygobject`
- GTK4 VTE 3.91 (`gir1.2-vte-3.91` and `libvte-2.91-gtk4-0` on Debian/Ubuntu)
- [PI](https://pi.dev/docs/latest) 0.80+ with Node.js 20+ and an authenticated model
- `pdftotext` Python bindings, PyMuPDF, PyPDF, LangChain + Chroma + VoyageAI/Isaacus for RAG

## Quick start
```bash
uv run python -m recordprep app
```

The package parser can also be inspected directly:

```bash
python -m recordprep app
```

## Package layout
```text
recordprep/
  cli.py                  # recordprep command
  __main__.py             # python -m recordprep entry
  app.py                  # GTK app launcher
  classification.py       # reusable classifier worker helper
  config.py               # settings import surface
  documents.py            # PDF/text/image helper import surface
  manifest.py             # manifest helper import surface
  optimization.py         # optimization helper import surface
  prompts.py              # default prompt import surface
  rag.py                  # RAG helper import surface
  summaries.py            # summary path/link helper import surface
  pi_runtime.py           # PI discovery, model RPC, and project settings
  pi_bundle.py            # per-skill Agent Refinement artifact validation
  ui/main_window.py       # main GTK UI and pipeline orchestration
.pi/
  settings.json           # tracked project-wide PI model selection
  skills/                 # four project-local RecordPrep skills and helpers
  scripts/                # sequential skill runner and resource validator
```

## Using the app
1. Click the folder button to choose an existing `case_bundle` folder or its parent directory.
2. Click the list-add button to select one or more PDFs from the same folder.
3. Run individual steps or click "Run all steps".
4. Use Settings to configure API endpoints and prompts, plus the PI executable
   and project-wide PI model under Agent → PI.
5. Use the menu button to open "Test Classification" for a single-image prompt run with a live preview.

Choosing a different PDF set in the same folder makes the next Create files run
clear the previous generated bundle before rebuilding it. If parallel local OCR
drops its connection, RecordPrep restarts the server and retries unfinished pages
one at a time.

PI provider credentials remain in PI's global configuration. RecordPrep stores
only the executable command in ignored `config.json` and the selected
provider/model in tracked `.pi/settings.json`.

## Output layout
A `case_bundle/` folder is created next to the selected PDFs or reused if already present:
```text
case_bundle/
  case_name.txt
  manifest.json
  text_pages/           # 0001.txt, 0002.txt, ...
  image_pages/          # 0001.png, 0002.png, ... (300 DPI grayscale)
  classification/       # RT/CT classification JSONL files
  artifacts/            # toc.txt, boundary JSON, raw/optimized text, optimized chunk data
  summaries/            # source summaries plus derived _organized summaries
  rag/                  # case_overview.txt, vector_database/
  temp/                 # merged.pdf when multiple PDFs are selected
```

## Pipeline steps
- Create files: generate `text_pages/` and `image_pages/` and merge PDFs when needed.
- Strip characters: remove non-printing characters, normalize tables, and convert LaTeX.
- Infer case: derive the case name from the first pages and save `case_name.txt`.
- Classification basic: classify every page into major page types.
- Advanced classification: mark hearing, minute, and form first pages.
- Correct advanced classification: convert consecutive RT first-page markers to RT body pages.
- Classification dates: add hearing and minute order dates.
- Classification names: add report and form names.
- Build TOC and Correct TOC.
- Find and correct boundaries for hearings, reports, and minute orders.
- Create raw, pre-optimized, and optimized text artifacts.
- Create summaries and add hearing/minute page links to the hearings summary.
- Case overview: create parties plus factual/procedural dated histories for RAG context.
- Create RAG index: build a VoyageAI or Isaacus Chroma vector store.
- Agent Refinement:
  - Number transcript pages.
  - Organize hearing summary.
  - Organize report summary.
  - Build source map, only after the preceding three outputs validate.

Each row launches one project-local skill with PI in JSON event mode. RecordPrep
renders assistant text, tool activity, retries, and errors as they arrive in the
embedded terminal. The four rows run sequentially and retain one continuous
terminal transcript. They overwrite only derived transcript-numbering,
organized-summary, and source-map outputs; original summaries and record pages
remain unchanged. Stop terminates the active PI process tree. Resume skips each
fresh, valid Agent Refinement output and always keeps source-map generation last.

## Development
```bash
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
python3 .pi/scripts/run_recordprep_skill.py --validate-resources
```

Keep `pyproject.toml` and `uv.lock` synchronized when adding dependencies.

## License
GPL-3.0-or-later. See `LICENSE`.
