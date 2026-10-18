"""File-presence badges and Resume skipping, independent of historical settings.

Do not read profile revisions, metadata contents, timestamps or hashes here.
Consumers validate their actual inputs; requested generation keeps its own
checkpoint and in-flight publication protection. Resume separately protects
source pages from destructive replacement beneath already-prepared work.
"""
from pathlib import Path


_FILES = {
    "detect_transcript_layout": ("artifacts/transcript_layout.json",),
    "infer_case": ("case_name.txt",),
    "build_toc": ("artifacts/toc.txt",),
    "correct_toc": ("artifacts/toc.txt",),
    "find_boundaries": ("artifacts/hearing_boundaries.json", "artifacts/report_boundaries.json", "artifacts/minutes_boundaries.json"),
    "correct_boundaries": ("artifacts/hearing_boundaries.json", "artifacts/report_boundaries.json"),
    "number_transcript_pages": ("artifacts/transcript_page_numbers.json", "artifacts/transcript_page_number_series.md"),
    "build_participant_index": ("artifacts/participant_index.json",),
    "create_case_overview": ("artifacts/case_overview.md",),
    "build_source_map": ("artifacts/source_map.json",),
}
_CLASSIFICATION = {
    "classify_basic": "basic",
    "classify_advanced": "basic_advanced",
    "correct_classify_advanced": "basic_advanced_corrected",
    "classify_dates": "basic_advanced_corrected_dates",
    "classify_names": "basic_advanced_corrected_dates_names",
}
_SUMMARIES = {
    "create_hearing_summaries": "hearings",
    "create_report_summaries": "reports",
    "create_minute_order_summaries": "minutes",
}


def _has_file(directory: Path, pattern: str) -> bool:
    return any(path.is_file() for path in directory.glob(pattern))


def step_outputs_present(step_id: str, root: Path) -> bool:
    """Whether the step's published output exists, not whether it is current."""
    try:
        if step_id == "create_files":
            return _has_file(root / "text_pages", "*.txt") and _has_file(root / "image_pages", "*.png")
        if step_id == "strip_characters":
            return _has_file(root / "text_pages", "*.txt")
        if step_id in _FILES:
            return all((root / name).is_file() for name in _FILES[step_id])
        if step_id in _CLASSIFICATION:
            directory = root / "classification"
            # RT-only and CT-only bundles have only one side. In a mixed bundle,
            # require the stage output for each side with a basic output file.
            sides = [side for side in ("RT", "CT") if (directory / f"{side}_basic.jsonl").is_file()]
            suffix = _CLASSIFICATION[step_id]
            if sides:
                return all((directory / f"{side}_{suffix}.jsonl").is_file() for side in sides)
            return any((directory / f"{side}_{suffix}.jsonl").is_file() for side in ("RT", "CT"))
        if step_id in _SUMMARIES:
            kind = _SUMMARIES[step_id]
            directory = root / "summaries"
            return ((directory / f"summarized_{kind}.txt").is_file()
                    or _has_file(directory, f"{kind}_sum_*.txt"))
        if step_id == "build_summary_editions":
            directory = root / "summaries/editions"
            return all(any(pdf.with_suffix(".pages.json").is_file()
                           for pattern in (f"{kind}_sum_*.pdf", f"summarized_{kind}.pdf")
                           for pdf in directory.glob(pattern) if pdf.is_file())
                       for kind in ("hearings", "reports", "minutes"))
    except OSError:
        return False
    return False
