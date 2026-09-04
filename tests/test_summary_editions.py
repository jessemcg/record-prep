"""Tests for page-matched summary editions (Letter PDFs + Focus page maps).

Synthetic only: no real case material. Covers rendering, coverage invariants,
link mapping, hash/schema rejection, atomic publication, category-specific
invalidation, pipeline ordering, and manifest companion keys.
"""

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fitz

from recordprep.ui.main_window import (
    CONFIG_KEY_SUMMARIZE_API_KEY,
    CONFIG_KEY_SUMMARIZE_API_URL,
    CONFIG_KEY_SUMMARIZE_MODEL_ID,
    PIPELINE_PHASES,
    PIPELINE_STEP_PHASE,
    RecordPrepWindow,
    _summary_output_paths,
    _minutes_summary_output_path,
    _write_manifest,
)
from recordprep.summary_editions import (
    BODY_FONT_FAMILY,
    CENTURY_SCHOOLBOOK_FAMILY,
    PAGE_HEIGHT_PT,
    SummaryEditionError,
    PAGE_MAP_ARTIFACT,
    PAGE_MAP_SCHEMA_VERSION,
    PAGE_WIDTH_PT,
    SUMMARY_EDITION_KINDS,
    _reset_edition_body_font_cache,
    _resolve_century_schoolbook_font,
    build_summary_edition,
    publish_summary_edition,
    remove_summary_edition,
    resolve_edition_body_font,
    summary_edition_is_complete,
    summary_edition_output_paths,
    validate_edition_payload,
    validate_summary_edition_files,
)

LONG_PARAGRAPH = (
    "The court reviewed the entire record carefully and considered every "
    "argument presented by the parties before reaching its conclusion about "
    "the matters at issue and the submitted evidence. "
)


def _long_source(paragraph_count: int = 30) -> str:
    lines = [f"Paragraph {number}. " + LONG_PARAGRAPH * 2 for number in range(1, paragraph_count + 1)]
    link_line = max(0, min(10, paragraph_count - 1))
    lines[link_line] += "March 3, 2025 [Hearing](page:1234) [Minute Order](page:567) end of line."
    return "\n\n".join(lines) + "\n"


def _write_source(root: Path, kind: str, text: str) -> Path:
    summaries_dir = root / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    names = {
        "hearings": "hearings_sum_IsoCase.txt",
        "reports": "reports_sum_IsoCase.txt",
        "minutes": "minutes_sum_IsoCase.txt",
    }
    path = summaries_dir / names[kind]
    path.write_text(text, encoding="utf-8")
    return path


def _build_bundle(temporary: str) -> Path:
    root = Path(temporary) / "case_bundle"
    root.mkdir(parents=True)
    (root / "case_name.txt").write_text("IsoCase", encoding="utf-8")
    return root


def _publish_all(root: Path, source_text: str | None = None) -> None:
    text = source_text if source_text is not None else _long_source()
    for kind in SUMMARY_EDITION_KINDS:
        source = _write_source(root, kind, text)
        edition = build_summary_edition(kind, source, root)
        publish_summary_edition(edition, source)


def _extract_pdf_page_text(pdf_bytes: bytes) -> list[str]:
    with fitz.open("pdf", pdf_bytes) as document:
        return [page.get_text() for page in document]


def _idle_now(callback, *args):
    callback(*args)
    return 1


def _make_harness(root: Path) -> mock.Mock:
    harness = mock.Mock()
    harness.selected_pdfs = []
    harness._resolve_case_root.return_value = root
    harness._request_plain_text.return_value = "Synthetic summary paragraph."
    harness._prepare_summary_step = RecordPrepWindow._prepare_summary_step.__get__(
        harness, RecordPrepWindow
    )
    return harness


def _run_handler(harness: mock.Mock, handler_name: str) -> bool:
    with tempfile.TemporaryDirectory() as config_temporary:
        config_path = Path(config_temporary) / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    CONFIG_KEY_SUMMARIZE_API_URL: "http://localhost:9999/v1/chat",
                    CONFIG_KEY_SUMMARIZE_MODEL_ID: "synthetic-model",
                    CONFIG_KEY_SUMMARIZE_API_KEY: "synthetic-key",
                }
            ),
            encoding="utf-8",
        )
        with mock.patch(
            "recordprep.ui.main_window.CONFIG_FILE", config_path
        ), mock.patch(
            "recordprep.ui.main_window.GLib.idle_add", side_effect=_idle_now
        ):
            handler = getattr(RecordPrepWindow, handler_name)
            return handler(harness)


class EditionRenderingTests(unittest.TestCase):
    def test_each_category_restarts_page_numbering_at_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            text = _long_source()
            for kind in SUMMARY_EDITION_KINDS:
                source = _write_source(root, kind, text)
                edition = build_summary_edition(kind, source, root)
                self.assertEqual(edition.page_map["kind"], kind)
                self.assertEqual(edition.page_map["pages"][0]["page"], 1)
                self.assertEqual(
                    [entry["page"] for entry in edition.page_map["pages"]],
                    list(range(1, edition.page_map["pdf"]["page_count"] + 1)),
                )
                self.assertNotEqual(
                    edition.page_map["pdf"]["sha256"],
                    "",
                )

    def test_letter_media_box_and_fixed_layout_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source(5))
            edition = build_summary_edition("hearings", source, root)
            layout = edition.page_map["layout"]
            self.assertEqual(layout["page_width_pt"], PAGE_WIDTH_PT)
            self.assertEqual(layout["page_height_pt"], PAGE_HEIGHT_PT)
            self.assertEqual(layout["margin_pt"], 72.0)
            self.assertEqual(layout["body_font_size_pt"], 12.0)
            with fitz.open("pdf", edition.pdf_bytes) as document:
                for page in document:
                    self.assertEqual(page.rect.width, PAGE_WIDTH_PT)
                    self.assertEqual(page.rect.height, PAGE_HEIGHT_PT)

    def test_multi_page_source_has_monotonic_source_line_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source())
            edition = build_summary_edition("hearings", source, root)
            self.assertGreater(edition.page_map["pdf"]["page_count"], 1)
            previous_last = 0
            for page in edition.pages:
                self.assertGreaterEqual(page.source_first_line, 0)
                self.assertGreaterEqual(page.source_last_line, page.source_first_line)
                self.assertGreaterEqual(page.source_first_line, 0)
                if page.source_last_line:
                    self.assertGreaterEqual(page.source_first_line, previous_last and 1)
                previous_last = page.source_last_line

    def test_page_footer_on_every_pdf_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source())
            edition = build_summary_edition("hearings", source, root)
            total = edition.page_map["pdf"]["page_count"]
            page_texts = _extract_pdf_page_text(edition.pdf_bytes)
            self.assertEqual(len(page_texts), total)
            for number, text in enumerate(page_texts, start=1):
                self.assertIn(f"Page {number} of {total}", text)
            # Footer is excluded from the sidecar page text.
            for page in edition.pages:
                self.assertNotIn(f"Page {page.page} of {total}", page.text)

    def test_full_source_coverage_without_omission_or_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            text = _long_source()
            source = _write_source(root, "hearings", text)
            edition = build_summary_edition("hearings", source, root)
            errors = validate_edition_payload(
                edition.page_map,
                kind="hearings",
                root_dir=root,
                source_text=text,
                pdf_bytes=edition.pdf_bytes,
            )
            self.assertEqual(errors, [])

    def test_curly_quotes_and_ordinary_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            text = (
                "Café naïve — “curly quotes” and ’apostrophes. " + LONG_PARAGRAPH * 4
            )
            source = _write_source(root, "reports", text)
            edition = build_summary_edition("reports", source, root)
            errors = validate_edition_payload(
                edition.page_map,
                kind="reports",
                root_dir=root,
                source_text=text,
                pdf_bytes=edition.pdf_bytes,
            )
            self.assertEqual(errors, [])

    def test_html_like_model_output_is_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            text = (
                "<script>alert('x')</script> & <b>bold</b> \"quoted\" "
                + LONG_PARAGRAPH * 3
            )
            source = _write_source(root, "minutes", text)
            edition = build_summary_edition("minutes", source, root)
            page_texts = _extract_pdf_page_text(edition.pdf_bytes)
            joined = "\n".join(page_texts)
            self.assertIn("<script>alert('x')</script>", joined)
            self.assertNotIn("alert(", joined.replace("<script>alert('x')</script>", ""))
            errors = validate_edition_payload(
                edition.page_map,
                kind="minutes",
                root_dir=root,
                source_text=text,
                pdf_bytes=edition.pdf_bytes,
            )
            self.assertEqual(errors, [])

    def test_pdf_shows_labels_without_raw_markdown_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source())
            edition = build_summary_edition("hearings", source, root)
            joined = "\n".join(_extract_pdf_page_text(edition.pdf_bytes))
            self.assertNotIn("[Hearing](page:", joined)
            self.assertNotIn("[Minute Order](page:", joined)
            self.assertIn("Hearing", joined)
            self.assertIn("Minute Order", joined)

    def test_link_spans_and_targets_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source())
            edition = build_summary_edition("hearings", source, root)
            all_spans = [
                span for page in edition.pages for span in page.links
            ]
            targets = sorted(span.target_page for span in all_spans)
            self.assertEqual(targets, [567, 1234])
            for page in edition.pages:
                for span in page.links:
                    self.assertEqual(page.text[span.start : span.end], span.label)
            ordered = sorted((span.start, span.end) for span in all_spans)
            for (_ps, _pe), (ns, _ne) in zip(ordered, ordered[1:]):
                self.assertGreaterEqual(ns, _pe)

    def test_empty_boundary_category_produces_single_page_edition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "minutes", "   \n\n  ")
            edition = build_summary_edition("minutes", source, root)
            self.assertEqual(edition.page_map["pdf"]["page_count"], 1)
            self.assertEqual(edition.pages[0].text, "")
            self.assertEqual(edition.pages[0].source_first_line, 0)
            self.assertEqual(edition.pages[0].source_last_line, 0)
            errors = validate_edition_payload(
                edition.page_map,
                kind="minutes",
                root_dir=root,
                source_text="   \n\n  ",
                pdf_bytes=edition.pdf_bytes,
            )
            self.assertEqual(errors, [])

    def test_ligature_substitution_keeps_coverage(self) -> None:
        # MuPDF's serif face renders fi/fl/ff as single ligature glyphs, so
        # extraction returns one codepoint where the source has two letters.
        from recordprep.summary_editions import _coverage_stream

        self.assertEqual(_coverage_stream("ﬁne"), _coverage_stream("fine"))
        self.assertEqual(_coverage_stream("ﬂow"), _coverage_stream("flow"))
        self.assertEqual(_coverage_stream("aﬀect"), _coverage_stream("affect"))
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            text = (
                "The official filed a final affidavit before the first "
                "fiscal review. "
                "The flamingo flew over the flat field finally. "
                + LONG_PARAGRAPH * 4
            )
            source = _write_source(root, "hearings", text)
            edition = build_summary_edition("hearings", source, root)
            errors = validate_edition_payload(
                edition.page_map,
                kind="hearings",
                root_dir=root,
                source_text=text,
                pdf_bytes=edition.pdf_bytes,
            )
            self.assertEqual(errors, [])

    def test_alignment_tolerates_wrapped_compounds_and_ligatures(self) -> None:
        # Hyphenated compounds that wrap at the hyphen split into two
        # extracted tokens whose concatenation equals the source word; NFKC
        # folds ligature glyphs. Character-level whitespace-insensitive
        # alignment must accept both.
        from recordprep.summary_editions import _align_source_lines

        printable = [
            (1, "The record-breaking, well-documented \N{LATIN SMALL LIGATURE FI}nal "
                "finding was reviewed."),
            (3, "Second line with more detail here."),
        ]
        # Page 1: the compound "record-breaking" wrapped at the hyphen (space
        # injected by extraction) and the ligature extracted precomposed.
        page_texts = {
            1: "The record- breaking, well- documented ﬁnal finding was",
            2: "reviewed. Second line with more detail here.",
        }
        ranges = _align_source_lines(printable, page_texts)
        self.assertEqual(ranges[1], (1, 1))
        # Page 2 begins mid-paragraph ("reviewed." closes source line 1), so
        # its inclusive source-line range legitimately spans 1..3.
        self.assertEqual(ranges[2], (1, 3))

    def test_overlong_unbreakable_token_fails_loudly(self) -> None:
        # A single word wider than a full line is clipped by the renderer;
        # the coverage check must fail the step instead of losing characters
        # silently. Prior editions are preserved by the caller.
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            text = "Reference marker x" + "y" * 140 + " ends the sentence."
            source = _write_source(root, "reports", text)
            with self.assertRaises(SummaryEditionError):
                build_summary_edition("reports", source, root)


def _system_font_file() -> Path | None:
    """Any usable system font file for mocked-resolution rendering tests."""
    fc_match = shutil.which("fc-match")
    if not fc_match:
        return None
    try:
        result = subprocess.run(
            [fc_match, "-f", "file=%{file}\n", "serif"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    _key, separator, value = result.stdout.strip().partition("=")
    if not separator:
        return None
    path = Path(value.strip())
    if not path.is_file() or path.suffix.casefold() not in {
        ".ttf",
        ".otf",
        ".ttc",
        ".otc",
    }:
        return None
    return path


class EditionFontResolutionTests(unittest.TestCase):
    """Fontconfig resolution and graceful fallback (no real fc-match calls
    with synthetic payloads; the exact-family test uses a temporary file)."""

    def setUp(self) -> None:
        _reset_edition_body_font_cache()

    def tearDown(self) -> None:
        _reset_edition_body_font_cache()

    def _run_fc_match(self, stdout: str, returncode: int = 0, file_exists: bool = True):
        """Patch fc-match discovery and return the resolver result plus mock."""
        font_file = None
        for line in stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "file":
                font_file = Path(value.strip())
        def fake_run(argv, **_kwargs):
            self.assertIsInstance(argv, list)
            if file_exists and font_file is not None:
                font_file.parent.mkdir(parents=True, exist_ok=True)
                font_file.write_bytes(b"synthetic")
            return mock.Mock(returncode=returncode, stdout=stdout)

        with mock.patch(
            "recordprep.summary_editions.shutil.which", return_value="/usr/bin/fc-match"
        ) as which_mock, mock.patch(
            "recordprep.summary_editions.subprocess.run", side_effect=fake_run
        ) as run_patch:
            resolved = _resolve_century_schoolbook_font()
        which_mock.assert_called_once_with("fc-match")
        return resolved, run_patch

    def test_exact_family_regular_style_resolves_to_file(self) -> None:
        resolved, _run_patch = self._run_fc_match(
            "family=Century Schoolbook\n"
            "style=Regular,normal,Standard\n"
            "file=/tmp/fonttest/Century Schoolbook.ttf\n"
        )
        self.assertEqual(resolved, Path("/tmp/fonttest/Century Schoolbook.ttf"))

    def test_directly_named_variant_family_resolves(self) -> None:
        resolved, _run_patch = self._run_fc_match(
            "family=Century Schoolbook L\n"
            "style=Regular\n"
            "file=/tmp/fonttest/Century Schoolbook L.ttf\n"
        )
        self.assertEqual(resolved, Path("/tmp/fonttest/Century Schoolbook L.ttf"))

    def test_unrelated_fallback_family_is_rejected(self) -> None:
        resolved, _run_patch = self._run_fc_match(
            "family=DejaVu Serif\n"
            "style=Regular,normal\n"
            "file=/tmp/fonttest/DejaVuSerif.ttf\n"
        )
        self.assertIsNone(resolved)

    def test_non_regular_style_is_rejected(self) -> None:
        resolved, _run_patch = self._run_fc_match(
            "family=Century Schoolbook\n"
            "style=Bold\n"
            "file=/tmp/fonttest/Century Schoolbook Bold.ttf\n"
        )
        self.assertIsNone(resolved)

    def test_missing_command_falls_back(self) -> None:
        with mock.patch("recordprep.summary_editions.shutil.which", return_value=None):
            self.assertIsNone(_resolve_century_schoolbook_font())

    def test_failed_command_falls_back(self) -> None:
        resolved, _run_patch = self._run_fc_match("", returncode=1, file_exists=False)
        self.assertIsNone(resolved)

    def test_timeout_falls_back(self) -> None:
        with mock.patch(
            "recordprep.summary_editions.shutil.which", return_value="/usr/bin/fc-match"
        ), mock.patch(
            "recordprep.summary_editions.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="fc-match", timeout=5),
        ):
            self.assertIsNone(_resolve_century_schoolbook_font())

    def test_subprocess_error_falls_back(self) -> None:
        with mock.patch(
            "recordprep.summary_editions.shutil.which", return_value="/usr/bin/fc-match"
        ), mock.patch(
            "recordprep.summary_editions.subprocess.run",
            side_effect=OSError("fc-match vanished"),
        ):
            self.assertIsNone(_resolve_century_schoolbook_font())

    def test_malformed_output_falls_back(self) -> None:
        resolved, _run_patch = self._run_fc_match(
            "garbage without separators\n", file_exists=False
        )
        self.assertIsNone(resolved)

    def test_missing_font_file_falls_back(self) -> None:
        resolved, _run_patch = self._run_fc_match(
            "family=Century Schoolbook\n"
            "style=Regular\n"
            "file=/tmp/fonttest/absent.ttf\n",
            file_exists=False,
        )
        self.assertIsNone(resolved)

    def test_unsupported_suffix_falls_back(self) -> None:
        resolved, _run_patch = self._run_fc_match(
            "family=Century Schoolbook\n"
            "style=Regular\n"
            "file=/tmp/fonttest/Century Schoolbook.txt\n"
        )
        self.assertIsNone(resolved)

    def test_resolution_is_cached_per_process(self) -> None:
        with mock.patch(
            "recordprep.summary_editions._resolve_century_schoolbook_font",
            return_value=None,
        ) as resolver:
            self.assertIsNone(resolve_edition_body_font())
            self.assertIsNone(resolve_edition_body_font())
            self.assertEqual(resolver.call_count, 1)
            _reset_edition_body_font_cache()
            self.assertIsNone(resolve_edition_body_font())
            self.assertEqual(resolver.call_count, 2)


class EditionFontRenderingTests(unittest.TestCase):
    """Rendering invariants with the Century preference enabled and disabled.

    Rendering tests use any real system font file behind a mocked resolver,
    never a bundled Century font.
    """

    def setUp(self) -> None:
        _reset_edition_body_font_cache()

    def tearDown(self) -> None:
        _reset_edition_body_font_cache()

    def _edition_with_mocked_font(self, root: Path, font_path: Path | None):
        source = _write_source(root, "hearings", _long_source(5))
        with mock.patch(
            "recordprep.summary_editions.resolve_edition_body_font",
            return_value=font_path,
        ):
            edition = build_summary_edition("hearings", source, root)
        return edition

    def test_century_enabled_rendering_passes_all_invariants(self) -> None:
        system_font = _system_font_file()
        if system_font is None:
            self.skipTest("no usable system font file for mocked resolver")
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            font_path = root / "Test Body Font.ttf"
            shutil.copyfile(system_font, font_path)
            edition = self._edition_with_mocked_font(root, font_path)

            self.assertEqual(
                edition.page_map["layout"]["body_font_family"],
                CENTURY_SCHOOLBOOK_FAMILY,
            )
            self.assertEqual(edition.page_map["layout"]["id"], "recordprep-summary-letter-v1")
            errors = validate_edition_payload(
                edition.page_map,
                kind="hearings",
                root_dir=root,
                source_text=_long_source(5),
                pdf_bytes=edition.pdf_bytes,
            )
            self.assertEqual(errors, [])

            expected_name = fitz.Font(fontfile=str(font_path)).name
            total = edition.page_map["pdf"]["page_count"]
            page_texts = _extract_pdf_page_text(edition.pdf_bytes)
            with fitz.open("pdf", edition.pdf_bytes) as document:
                for number, page in enumerate(document):
                    self.assertEqual(page.rect.width, PAGE_WIDTH_PT)
                    self.assertEqual(page.rect.height, PAGE_HEIGHT_PT)
                    fonts = document.get_page_fonts(number)
                    basefonts = [entry[3] for entry in fonts]
                    self.assertIn(expected_name, basefonts)
                    refnames = [entry[4] for entry in fonts]
                    self.assertIn("CSBRegular", refnames)
            for number, text in enumerate(page_texts, start=1):
                self.assertIn(f"Page {number} of {total}", text)
            for page in edition.pages:
                self.assertNotIn(f"Page {page.page} of {total}", page.text)

    def test_fallback_rendering_reports_generic_serif(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            edition = self._edition_with_mocked_font(root, None)
            self.assertEqual(
                edition.page_map["layout"]["body_font_family"], BODY_FONT_FAMILY
            )
            errors = validate_edition_payload(
                edition.page_map,
                kind="hearings",
                root_dir=root,
                source_text=_long_source(5),
                pdf_bytes=edition.pdf_bytes,
            )
            self.assertEqual(errors, [])
            total = edition.page_map["pdf"]["page_count"]
            for number, text in enumerate(_extract_pdf_page_text(edition.pdf_bytes), start=1):
                self.assertIn(f"Page {number} of {total}", text)


class EditionRejectionTests(unittest.TestCase):
    def _published(self, temporary: str) -> tuple[Path, Path, Path]:
        root = _build_bundle(temporary)
        source = _write_source(root, "hearings", _long_source())
        edition = build_summary_edition("hearings", source, root)
        publish_summary_edition(edition, source)
        pdf_path, pages_path = summary_edition_output_paths(source)
        return root, source, pages_path

    def test_tampered_pdf_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            page_map["pdf"]["sha256"] = "0" * 64
            errors = validate_edition_payload(
                page_map, kind="hearings", root_dir=root
            )
            self.assertIn("Page map PDF hash mismatch.", errors)

    def test_changed_source_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, _pages_path = self._published(temporary)
            source.write_text(source.read_text(encoding="utf-8") + "extra\n", encoding="utf-8")
            errors = validate_summary_edition_files("hearings", source, root)
            self.assertIn("Page map source hash mismatch.", errors)
            self.assertFalse(summary_edition_is_complete("hearings", source, root))

    def test_unsupported_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            page_map["schema_version"] = PAGE_MAP_SCHEMA_VERSION + 1
            errors = validate_edition_payload(
                page_map, kind="hearings", root_dir=root
            )
            self.assertIn("Page map schema version is unsupported.", errors)

    def test_wrong_category_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            errors = validate_edition_payload(
                page_map, kind="reports", root_dir=root
            )
            self.assertIn(
                "Page map category does not match the requested summary.", errors
            )

    def test_page_gap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            if len(page_map["pages"]) > 1:
                page_map["pages"][1]["page"] = 3
            else:
                page_map["pages"][0]["page"] = 2
            errors = validate_edition_payload(
                page_map, kind="hearings", root_dir=root
            )
            self.assertIn(
                "Page map page numbers are not consecutive starting at 1.", errors
            )

    def test_path_escaping_sidecar_is_rejected_without_opening_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            page_map["pdf"]["path"] = "../../outside.pdf"
            errors = validate_edition_payload(
                page_map, kind="hearings", root_dir=root
            )
            self.assertIn(
                "Edition path must be relative and stay inside the bundle.", errors
            )

    def test_dropped_link_span_label_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            for entry in page_map["pages"]:
                for link in entry["links"]:
                    link["label"] = "Wrong Label"
            errors = validate_edition_payload(
                page_map, kind="hearings", root_dir=root
            )
            self.assertIn(
                "Page map link span does not match its label.", errors
            )


class PublicationTests(unittest.TestCase):
    def test_publish_creates_pdf_then_sidecar_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source())
            edition = build_summary_edition("hearings", source, root)
            publish_summary_edition(edition, source)
            pdf_path, pages_path = summary_edition_output_paths(source)
            self.assertTrue(pdf_path.exists())
            self.assertTrue(pages_path.exists())
            self.assertEqual(
                pdf_path.parent.name, "editions"
            )
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            self.assertEqual(page_map["artifact"], PAGE_MAP_ARTIFACT)
            self.assertEqual(page_map["pdf"]["sha256"], edition.page_map["pdf"]["sha256"])

    def test_failed_build_preserves_existing_editions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source())
            edition = build_summary_edition("hearings", source, root)
            publish_summary_edition(edition, source)
            pdf_path, pages_path = summary_edition_output_paths(source)
            original_pdf = pdf_path.read_bytes()
            original_map = pages_path.read_bytes()

            with mock.patch(
                "recordprep.summary_editions._render_story_html",
                side_effect=RuntimeError("synthetic rendering failure"),
            ):
                with self.assertRaises(RuntimeError):
                    build_summary_edition("hearings", source, root)

            self.assertEqual(pdf_path.read_bytes(), original_pdf)
            self.assertEqual(pages_path.read_bytes(), original_map)
            self.assertTrue(summary_edition_is_complete("hearings", source, root))

    def test_partial_publication_is_detectable_through_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source())
            edition = build_summary_edition("hearings", source, root)
            publish_summary_edition(edition, source)
            _pdf_path, pages_path = summary_edition_output_paths(source)
            # Simulate a crash between the PDF and sidecar replacements.
            stale = json.loads(pages_path.read_text(encoding="utf-8"))
            stale["pdf"]["sha256"] = "0" * 64
            pages_path.write_text(json.dumps(stale), encoding="utf-8")
            errors = validate_summary_edition_files("hearings", source, root)
            self.assertIn("Page map PDF hash mismatch.", errors)
            self.assertFalse(summary_edition_is_complete("hearings", source, root))

    def test_remove_summary_edition_deletes_only_that_category(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            sources = {
                kind: _write_source(root, kind, _long_source(5))
                for kind in SUMMARY_EDITION_KINDS
            }
            for kind, source in sources.items():
                publish_summary_edition(
                    build_summary_edition(kind, source, root), source
                )
            remove_summary_edition(sources["hearings"])
            for kind, source in sources.items():
                pdf_path, pages_path = summary_edition_output_paths(source)
                if kind == "hearings":
                    self.assertFalse(pdf_path.exists())
                    self.assertFalse(pages_path.exists())
                else:
                    self.assertTrue(pdf_path.exists())
                    self.assertTrue(pages_path.exists())
                    self.assertTrue(summary_edition_is_complete(kind, source, root))


def _seed_boundaries(root: Path) -> None:
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    text_pages = root / "text_pages"
    text_pages.mkdir(exist_ok=True)
    (text_pages / "0001.txt").write_text("Hearing page one.\n", encoding="utf-8")
    (text_pages / "0002.txt").write_text("Report and minute page two.\n", encoding="utf-8")
    transcript = {
        "schema_version": 2,
        "entries": [
            {"file_page": 1, "citation_label": "RT 1"},
            {"file_page": 2, "citation_label": "RT 2"},
        ],
    }
    (artifacts / "transcript_page_numbers.json").write_text(
        json.dumps(transcript), encoding="utf-8"
    )
    (artifacts / "hearing_boundaries.json").write_text(
        json.dumps([{"date": "March 3, 2025", "start_page": "0001", "end_page": "0001"}]),
        encoding="utf-8",
    )
    (artifacts / "report_boundaries.json").write_text(
        json.dumps(
            [
                {
                    "report_name": "Detention Report",
                    "report_date": "March 3, 2025",
                    "report_label": "Detention Report March 3, 2025",
                    "start_page": "0002",
                    "end_page": "0002",
                }
            ]
        ),
        encoding="utf-8",
    )
    (artifacts / "minutes_boundaries.json").write_text(
        json.dumps([{"date": "March 3, 2025", "start_page": "0002", "end_page": "0002"}]),
        encoding="utf-8",
    )
    hearing = {
        "id": "hearing:0001",
        "start_page": 1,
        "end_page": 1,
        "warnings": ["Hearing reviewed synthetically."],
        "witness_status": "none",
        "witness_evidence": [
            {
                "text_path": "text_pages/0001.txt",
                "file_page": 1,
                "citation_label": "RT 1",
                "citation_key": "RT:1",
                "note": "Explicit no-witness index.",
            }
        ],
        "witnesses": [],
        "counsel": [],
        "participants": [],
    }
    (artifacts / "participant_index.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source": "record-participant-index",
                "warnings": [],
                "hearings": [hearing],
            }
        ),
        encoding="utf-8",
    )


class InvalidationTests(unittest.TestCase):
    def test_hearing_summary_rerun_invalidates_only_hearing_edition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _seed_boundaries(root)
            _publish_all(root, source_text=_long_source(5))
            hearings, reports = _summary_output_paths(root)
            minutes = _minutes_summary_output_path(root)
            sources = {"hearings": hearings, "reports": reports, "minutes": minutes}
            for kind, source in sources.items():
                self.assertTrue(
                    summary_edition_is_complete(kind, source, root),
                    f"{kind} edition should start valid",
                )

            harness = _make_harness(root)
            self.assertTrue(_run_handler(harness, "_run_step_create_hearing_summaries"))

            self.assertFalse(summary_edition_is_complete("hearings", hearings, root))
            self.assertFalse((root / "summaries/editions" / f"{hearings.stem}.pdf").exists())
            self.assertTrue(summary_edition_is_complete("reports", reports, root))
            self.assertTrue(summary_edition_is_complete("minutes", minutes, root))

    def test_report_summary_rerun_invalidates_only_report_edition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _seed_boundaries(root)
            _publish_all(root, source_text=_long_source(5))
            hearings, reports = _summary_output_paths(root)
            minutes = _minutes_summary_output_path(root)

            harness = _make_harness(root)
            self.assertTrue(_run_handler(harness, "_run_step_create_report_summaries"))

            self.assertTrue(summary_edition_is_complete("hearings", hearings, root))
            self.assertFalse(summary_edition_is_complete("reports", reports, root))
            self.assertTrue(summary_edition_is_complete("minutes", minutes, root))

    def test_minute_summary_rerun_invalidates_only_minute_edition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _seed_boundaries(root)
            _publish_all(root, source_text=_long_source(5))
            hearings, reports = _summary_output_paths(root)
            minutes = _minutes_summary_output_path(root)

            harness = _make_harness(root)
            self.assertTrue(
                _run_handler(harness, "_run_step_create_minute_order_summaries")
            )

            self.assertTrue(summary_edition_is_complete("hearings", hearings, root))
            self.assertTrue(summary_edition_is_complete("reports", reports, root))
            self.assertFalse(summary_edition_is_complete("minutes", minutes, root))

    def test_add_links_invalidates_hearing_edition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _seed_boundaries(root)
            _publish_all(root, source_text=_long_source(5))
            hearings, _reports = _summary_output_paths(root)
            self.assertTrue(summary_edition_is_complete("hearings", hearings, root))

            harness = _make_harness(root)
            self.assertTrue(_run_handler(harness, "_run_step_add_hearing_date_links"))

            self.assertFalse(summary_edition_is_complete("hearings", hearings, root))


class StepHandlerTests(unittest.TestCase):
    def test_build_step_publishes_all_three_and_reports_page_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _write_source(root, "hearings", _long_source(5))
            _write_source(root, "reports", _long_source(5))
            _write_source(root, "minutes", _long_source(5))
            harness = _make_harness(root)

            self.assertTrue(
                _run_handler(harness, "_run_step_build_summary_editions")
            )
            self.assertEqual(
                harness._safe_update_manifest.call_args.args[1][
                    "last_completed_step"
                ],
                "build_summary_editions",
            )
            toast = harness.show_toast.call_args.args[0]
            self.assertIn("Build paginated summary editions complete", toast)
            self.assertIn("hearings", toast)
            self.assertIn("pages", toast)
            for kind in SUMMARY_EDITION_KINDS:
                source = {
                    "hearings": root / "summaries/hearings_sum_IsoCase.txt",
                    "reports": root / "summaries/reports_sum_IsoCase.txt",
                    "minutes": root / "summaries/minutes_sum_IsoCase.txt",
                }[kind]
                self.assertTrue(summary_edition_is_complete(kind, source, root))

    def test_build_step_fails_without_summary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _write_source(root, "hearings", _long_source(5))
            harness = _make_harness(root)

            self.assertFalse(
                _run_handler(harness, "_run_step_build_summary_editions")
            )
            harness._safe_update_manifest.assert_not_called()
            self.assertIn(
                "Build paginated summary editions failed",
                harness.show_toast.call_args.args[0],
            )


class PipelineAndManifestTests(unittest.TestCase):
    def test_build_summary_editions_follows_add_links_in_summarize_phase(self) -> None:
        summarize_ids = [
            step_ids
            for phase_id, _title, step_ids in [(phase[0], phase[1], phase[2]) for phase in PIPELINE_PHASES]
            if phase_id == "summarize"
        ][0]
        self.assertIn("build_summary_editions", summarize_ids)
        self.assertEqual(
            summarize_ids.index("build_summary_editions"),
            summarize_ids.index("add_hearing_date_links") + 1,
        )
        self.assertEqual(
            PIPELINE_STEP_PHASE["build_summary_editions"], "summarize"
        )

    def test_completion_requires_all_three_validated_editions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)

            def complete() -> bool:
                return RecordPrepWindow._step_artifact_complete(
                    mock.Mock(), "build_summary_editions", root, []
                )

            self.assertFalse(complete())
            _publish_all(root, source_text=_long_source(5))
            self.assertTrue(complete())
            hearing_source, _reports = _summary_output_paths(root)
            remove_summary_edition(hearing_source)
            self.assertFalse(complete())

    def test_manifest_publishes_and_preserves_companion_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _publish_all(root, source_text=_long_source(5))

            _write_manifest(root, [])
            manifest = json.loads(
                (root / "manifest.json").read_text(encoding="utf-8")
            )
            files = manifest["files"]
            for kind in SUMMARY_EDITION_KINDS:
                self.assertIn(f"summarized_{kind}_pdf", files)
                self.assertIn(f"summarized_{kind}_pages", files)
                self.assertTrue(
                    files[f"summarized_{kind}_pdf"].startswith("summaries/editions/")
                )
            self.assertEqual(files["summarized_hearings_pdf"], "summaries/editions/hearings_sum_IsoCase.pdf")
            self.assertEqual(
                files["summarized_hearings_pages"],
                "summaries/editions/hearings_sum_IsoCase.pages.json",
            )

            # Simulate the source-map publisher rewriting the manifest: the
            # companion keys must survive a second publication.
            _write_manifest(root, [])
            manifest = json.loads(
                (root / "manifest.json").read_text(encoding="utf-8")
            )
            for kind in SUMMARY_EDITION_KINDS:
                self.assertIn(f"summarized_{kind}_pdf", manifest["files"])
                self.assertIn(f"summarized_{kind}_pages", manifest["files"])

            # Invalidation drops the keys on the next manifest publication.
            hearings, _reports = _summary_output_paths(root)
            remove_summary_edition(hearings)
            _write_manifest(root, [])
            manifest = json.loads(
                (root / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("summarized_hearings_pdf", manifest["files"])
            self.assertNotIn("summarized_hearings_pages", manifest["files"])
            self.assertIn("summarized_reports_pdf", manifest["files"])

    def test_manifest_without_editions_has_no_companion_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _write_manifest(root, [])
            manifest = json.loads(
                (root / "manifest.json").read_text(encoding="utf-8")
            )
            for kind in SUMMARY_EDITION_KINDS:
                self.assertNotIn(f"summarized_{kind}_pdf", manifest["files"])
                self.assertNotIn(f"summarized_{kind}_pages", manifest["files"])


if __name__ == "__main__":
    unittest.main()
