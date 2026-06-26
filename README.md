# Record Prep

<img src="recordprep_icon.png" alt="Record Prep icon" width="128" align="left">

Record Prep is a GTK4/Libadwaita desktop app that turns OCR'd legal transcript PDFs into a structured
case bundle with classifications, summaries, and retrieval-ready artifacts for appellate workflows.

- Functional GTK4/Libadwaita desktop UI with the full pipeline exposed as step-by-step actions.
- Modular Python package under `recordprep/`, with the GTK orchestration in `recordprep/ui/main_window.py`.
- Settings are stored in the ignored root-level `config.json` and cover API URLs, model IDs, keys, and prompts.
- Local OCR defaults to a llama.cpp server, while remote steps use configurable API providers.
- RAG output targets VoyageAI or Isaacus embeddings with a Chroma vector store.

## What it does
- Imports one or more PDFs, merged in natural sort order when needed.
- Extracts per-page text and grayscale page images.
- Classifies pages, adds dates/names, and builds a table of contents.
- Finds hearing/report/minute order boundaries.
- Generates raw and optimized text, summaries, and a case overview.
- Stores chunk metadata separately from optimized chunk text and writes per-chunk JSONL artifacts.
- Optionally builds a VoyageAI/Chroma or Isaacus/Chroma RAG index from optimized hearing/report content, with similarity search filters driven by chunk metadata such as hearing date and report name.

Transcript page numbering is handled outside this app by the CodexMenu `transcript-page-numbering` skill.

## Requirements
- Python 3.13+
- GTK4/Libadwaita via `pygobject`
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
  ui/main_window.py       # main GTK UI and pipeline orchestration
```

## Using the app
1. Click the folder button to choose an existing `case_bundle` folder or its parent directory.
2. Click the list-add button to select one or more PDFs from the same folder.
3. Run individual steps or click "Run all steps".
4. Use the menu button to open Settings and configure API endpoints, models, keys, and prompts.
5. Use the menu button to open "Test Classification" for a single-image prompt run with a live preview.

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
  summaries/            # hearings_sum_<case>.txt, reports_sum_<case>.txt, minutes_sum_<case>.txt
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

## Development
```bash
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
```

Keep `pyproject.toml` and `uv.lock` synchronized when adding dependencies.

## License
GPL-3.0-or-later. See `LICENSE`.
