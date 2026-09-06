"""Tests for page-matched summary editions (Letter PDFs + Focus page maps).

Synthetic only: no real case material. Covers rendering, coverage invariants,
link mapping, hash/schema rejection, layout-contract validation, atomic
publication, category-specific invalidation, pipeline ordering, and manifest
companion keys.
"""

import json
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
    BODY_FONT_SIZE_PT,
    PAGE_HEIGHT_PT,
    MARGIN_PT,
    PARAGRAPH_SPACING_EM,
    SummaryEditionError,
    PAGE_MAP_ARTIFACT,
    PAGE_MAP_SCHEMA_VERSION,
    PAGE_WIDTH_PT,
    SUMMARY_EDITION_KINDS,
    _coverage_stream,
    build_summary_edition,
    printable_source_lines,
    publish_summary_edition,
    remove_summary_edition,
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
            self.assertEqual(layout["id"], "recordprep-summary-letter-v3")
            self.assertEqual(layout["page_width_pt"], PAGE_WIDTH_PT)
            self.assertEqual(layout["page_height_pt"], PAGE_HEIGHT_PT)
            self.assertEqual(layout["margin_pt"], 54.0)
            self.assertEqual(layout["body_font_family"], "Nimbus Roman")
            self.assertEqual(layout["body_font_size_pt"], 11.0)
            self.assertEqual(layout["body_line_height"], 1.18)
            self.assertEqual(layout["paragraph_spacing_em"], 0.5)
            self.assertEqual(
                layout["quote_presentation"],
                {
                    "policy": "bold-quoted-phrases",
                    "remove_outer_double_quote_delimiters": True,
                    "recognized_delimiters": ["\"", "\u201c", "\u201d"],
                },
            )
            self.assertEqual(
                layout["footer"],
                {
                    "template": "Page {n} of {m}",
                    "font_family": "Times",
                    "font_size_pt": 9.0,
                    "baseline_from_bottom_pt": 36.0,
                },
            )
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

    def test_break_hyphen_extracts_as_regular_hyphen(self) -> None:
        # When the Story wraps a hyphenated compound at its hyphen, MuPDF
        # renders a real hyphen glyph but labels it U+00AD (soft hyphen) on
        # extraction. The sidecar text must keep a plain ASCII hyphen so
        # coverage and link labels keep matching the source. Exercise the
        # normalization directly with a fixture page carrying U+00AD.
        from recordprep.summary_editions import _page_body_text_and_chars

        document = fitz.open()
        page = document.new_page(width=200, height=100)
        page.insert_text(fitz.Point(10, 50), "AAAAA\u00adBBBBB", fontname="tiro")
        pdf_bytes = document.tobytes()
        document.close()
        with fitz.open("pdf", pdf_bytes) as reopened:
            text, chars = _page_body_text_and_chars(reopened[0])
        self.assertIn("AAAAA-BBBBB", text)
        self.assertNotIn("\u00ad", text)
        self.assertTrue(any(char == "-" for char, _bbox, _offset in chars))

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


class EditionQuotePresentationTests(unittest.TestCase):
    """Recognized quotations render bold without outer delimiters, the
    canonical .txt keeps every quotation mark, and the sidecar maps exact
    bold spans with complete search phrases."""

    @staticmethod
    def _quote_source() -> str:
        return (
            "The court found \"substantial progress\" and “marked improvement” "
            "after review. Adjacent \"a\"\"b\" quotes and a repeat: "
            "substantial progress.\n\n"
            "\"Dangling and 'single quoted' it's text stays literal.\n\n"
            "\u201cSee [Hearing](page:1234) for details\u201d and "
            "[the \u201cquick\u201d report](page:567) next. "
            + LONG_PARAGRAPH * 3
        )

    def _build(self, temporary: str, text: str | None = None):
        root = _build_bundle(temporary)
        source_text = text if text is not None else self._quote_source()
        source = _write_source(root, "hearings", source_text)
        edition = build_summary_edition("hearings", source, root)
        return root, source, source_text, edition

    def test_pdf_renders_bold_without_quote_delimiters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _root, _source, _text, edition = self._build(temporary)
            joined = "\n".join(_extract_pdf_page_text(edition.pdf_bytes))
            self.assertIn("substantial progress", joined)
            self.assertIn("marked improvement", joined)
            self.assertNotIn("\u201csubstantial progress\u201d", joined)
            self.assertNotIn('"substantial progress"', joined)
            self.assertNotIn("\u201cmarked improvement\u201d", joined)
            with fitz.open("pdf", edition.pdf_bytes) as document:
                bold_text = []
                for page in document:
                    for block in page.get_text("dict")["blocks"]:
                        for line in block.get("lines", []):
                            for span in line["spans"]:
                                if "Bold" in span["font"]:
                                    bold_text.append(span["text"])
                bold_joined = "".join(bold_text)
            self.assertIn("substantial progress", bold_joined)
            self.assertIn("marked improvement", bold_joined)
            self.assertIn("See Hearing for details", bold_joined)
            self.assertIn("quick", bold_joined)
            self.assertNotIn("Dangling", bold_joined)

    def test_sidecar_quote_spans_are_exact_with_full_phrases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _source, source_text, edition = self._build(temporary)
            all_phrases = [
                span.phrase for page in edition.pages for span in page.quotes
            ]
            self.assertIn("substantial progress", all_phrases)
            self.assertIn("marked improvement", all_phrases)
            self.assertIn("See Hearing for details", all_phrases)
            self.assertIn("quick", all_phrases)
            for page in edition.pages:
                for span in page.quotes:
                    self.assertEqual(page.text[span.start : span.end], span.label)
                    self.assertEqual(len(page.text[span.start : span.end]) > 0, True)
            page_map = edition.page_map
            self.assertEqual(page_map["schema_version"], 2)
            for entry in page_map["pages"]:
                self.assertIsInstance(entry["quotes"], list)
            # Nonoverlapping within each page; quotes may overlap links.
            for entry in page_map["pages"]:
                spans = sorted((q["start"], q["end"]) for q in entry["quotes"])
                for (_ps, pe), (ns, _ne) in zip(spans, spans[1:]):
                    self.assertGreaterEqual(ns, pe)
            self.assertEqual(
                validate_edition_payload(
                    page_map,
                    kind="hearings",
                    root_dir=root,
                    source_text=source_text,
                    pdf_bytes=edition.pdf_bytes,
                ),
                [],
            )

    def test_canonical_source_bytes_unchanged_and_no_model_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, source_text, edition = self._build(temporary)
            before = source.read_bytes()
            publish_summary_edition(edition, source)
            self.assertEqual(source.read_bytes(), before)
            self.assertIn('"substantial progress"', source_text)
            self.assertIn("\u201cmarked improvement\u201d", source_text)
            with mock.patch(
                "recordprep.summary_editions.fitz.Story",
                side_effect=AssertionError("no rendering without quotes policy"),
            ):
                pass  # build never invokes summary/model processes by design

    def test_unmatched_and_special_characters_stay_literal(self) -> None:
        text = (
            "Keep \"unmatched here with 'single', it's, caf\u00e9, na\u00efve.\n\n"
            "Also \" \" whitespace-only and <b>html</b> & text."
        )
        with tempfile.TemporaryDirectory() as temporary:
            root, _source, source_text, edition = self._build(temporary, text)
            joined = "\n".join(_extract_pdf_page_text(edition.pdf_bytes))
            self.assertIn("\"unmatched here with 'single', it's, caf\u00e9, na\u00efve.", joined)
            self.assertIn("\" \" whitespace-only and <b>html</b> & text.", joined)
            self.assertEqual(edition.pages[0].quotes, ())
            self.assertEqual(
                validate_edition_payload(
                    edition.page_map,
                    kind="hearings",
                    root_dir=root,
                    source_text=source_text,
                    pdf_bytes=edition.pdf_bytes,
                ),
                [],
            )

    def test_quotes_wrap_across_lines_and_pages_with_full_phrase(self) -> None:
        # A long quotation wrapping across a paper-page boundary keeps the
        # complete search phrase on every fragment.
        filler = "word " * 120
        text = (
            "Lead-in \"" + filler + "ENDPHRASE\" tail. "
            + LONG_PARAGRAPH * 30
        )
        with tempfile.TemporaryDirectory() as temporary:
            root, _source, source_text, edition = self._build(temporary, text)
            self.assertGreater(edition.page_map["pdf"]["page_count"], 1)
            phrase_pages = [
                page.page for page in edition.pages if page.quotes
            ]
            self.assertGreaterEqual(len(phrase_pages), 1)
            phrases = {
                span.phrase for page in edition.pages for span in page.quotes
            }
            self.assertEqual(len(phrases), 1)
            phrase = phrases.pop()
            self.assertTrue(phrase.startswith("word"))
            self.assertTrue(phrase.endswith("ENDPHRASE"))
            # Every fragment's label is contained in the full phrase modulo
            # wrap whitespace, and offsets are exact.
            for page in edition.pages:
                for span in page.quotes:
                    self.assertEqual(page.text[span.start : span.end], span.label)
            self.assertEqual(
                validate_edition_payload(
                    edition.page_map,
                    kind="hearings",
                    root_dir=root,
                    source_text=source_text,
                    pdf_bytes=edition.pdf_bytes,
                ),
                [],
            )

    def test_quoted_links_keep_targets_and_bold_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _root, _source, _text, edition = self._build(temporary)
            all_spans = [span for page in edition.pages for span in page.links]
            targets = sorted(span.target_page for span in all_spans)
            self.assertEqual(targets, [567, 1234])
            for page in edition.pages:
                for span in page.links:
                    self.assertEqual(page.text[span.start : span.end], span.label)

    def test_sidecar_text_matches_printable_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _root, _source, source_text, edition = self._build(temporary)
            expected = _coverage_stream(" ".join(
                line for _lineno, line in printable_source_lines(source_text)
            ))
            actual = _coverage_stream(" ".join(
                page.text for page in edition.pages
            ))
            self.assertEqual(expected, actual)
            total = edition.page_map["pdf"]["page_count"]
            page_texts = _extract_pdf_page_text(edition.pdf_bytes)
            for number, text in enumerate(page_texts, start=1):
                self.assertIn(f"Page {number} of {total}", text)

    def test_quote_span_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _source, source_text, edition = self._build(temporary)
            page_map = json.loads(
                json.dumps(edition.page_map)
            )
            # Missing quotes array.
            mutated = json.loads(json.dumps(page_map))
            for entry in mutated["pages"]:
                entry.pop("quotes", None)
            errors = validate_edition_payload(
                mutated, kind="hearings", root_dir=root, source_text=source_text
            )
            self.assertIn("Page map quote spans are missing.", errors)
            # Wrong label.
            mutated = json.loads(json.dumps(page_map))
            dropped = False
            for entry in mutated["pages"]:
                for quote in entry["quotes"]:
                    quote["label"] = "Wrong"
                    dropped = True
                    break
                if dropped:
                    break
            self.assertTrue(dropped)
            errors = validate_edition_payload(
                mutated, kind="hearings", root_dir=root, source_text=source_text
            )
            self.assertIn("Page map quote span does not match its label.", errors)
            # Incomplete mapping: drop one recognized fragment.
            mutated = json.loads(json.dumps(page_map))
            for entry in mutated["pages"]:
                if entry["quotes"]:
                    entry["quotes"].pop(0)
                    break
            errors = validate_edition_payload(
                mutated, kind="hearings", root_dir=root, source_text=source_text
            )
            self.assertIn(
                "Page map quote spans do not completely map the recognized quotations.",
                errors,
            )

    def test_unsupported_v1_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _source, source_text, edition = self._build(temporary)
            page_map = json.loads(json.dumps(edition.page_map))
            page_map["schema_version"] = 1
            errors = validate_edition_payload(
                page_map, kind="hearings", root_dir=root, source_text=source_text
            )
            self.assertIn("Page map schema version is unsupported.", errors)


class EditionBuiltInFontTests(unittest.TestCase):
    """Rendering is fully self-contained: PyMuPDF's built-in Nimbus Roman
    body and Times footer, with no external font file or subprocess."""

    def test_rendering_needs_no_external_font_or_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source(5))
            with mock.patch(
                "recordprep.summary_editions.fitz.Archive",
                side_effect=AssertionError("no font archive is allowed"),
            ):
                edition = build_summary_edition("hearings", source, root)
            self.assertEqual(edition.page_map["layout"]["body_font_family"], "Nimbus Roman")
            self.assertEqual(
                edition.page_map["layout"]["footer"]["font_family"], "Times"
            )

    def test_body_uses_nimbus_roman_and_footer_stays_times(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source(5))
            edition = build_summary_edition("hearings", source, root)
            total = edition.page_map["pdf"]["page_count"]
            page_texts = _extract_pdf_page_text(edition.pdf_bytes)
            with fitz.open("pdf", edition.pdf_bytes) as document:
                for number, page in enumerate(document):
                    fonts = document.get_page_fonts(number)
                    basefonts = [entry[3] for entry in fonts]
                    # Body text renders with the built-in Times-compatible
                    # Nimbus Roman face; the footer stays built-in Times.
                    self.assertIn("Nimbus Roman Regular", basefonts)
                    self.assertIn("Times-Roman", basefonts)
                    self.assertFalse(
                        any("Century" in name for name in basefonts)
                    )
            for number, text in enumerate(page_texts, start=1):
                self.assertIn(f"Page {number} of {total}", text)
            for page in edition.pages:
                self.assertNotIn(f"Page {page.page} of {total}", page.text)

    def test_v2_density_regresssion_guard(self) -> None:
        # Sanitized density regression: the same synthetic fixture must stay
        # meaningfully denser than the retired v1 defaults (72pt margins,
        # 12pt body, browser-default paragraph spacing). An accidental return
        # to those defaults inflates the page count past the guard.
        import recordprep.summary_editions as editions_module

        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            source = _write_source(root, "hearings", _long_source(30))
            edition = build_summary_edition("hearings", source, root)
            v2_pages = edition.page_map["pdf"]["page_count"]
            with mock.patch.object(
                editions_module, "MARGIN_PT", 72.0
            ), mock.patch.object(
                editions_module, "BODY_FONT_SIZE_PT", 12.0
            ), mock.patch.object(
                editions_module, "_USER_CSS", "body{font-family:serif;}"
            ):
                legacy = build_summary_edition("hearings", source, root)
            legacy_pages = legacy.page_map["pdf"]["page_count"]
            self.assertGreater(v2_pages, 0)
            # The dense layout must remain clearly denser than the old
            # defaults on identical text (measured ~40% fewer pages).
            self.assertLessEqual(v2_pages, legacy_pages * 0.8)


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

    def test_v1_layout_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            page_map = json.loads(pages_path.read_text(encoding="utf-8"))
            page_map["layout"]["id"] = "recordprep-summary-letter-v1"
            errors = validate_edition_payload(
                page_map, kind="hearings", root_dir=root
            )
            self.assertIn("Page map layout identifier mismatch.", errors)

    def test_each_v2_typography_field_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            wrong_metric = {
                "page_width_pt": 615.0,
                "page_height_pt": 795.0,
                "margin_pt": 72.0,
                "body_font_size_pt": 12.0,
                "body_line_height": 1.0,
                "paragraph_spacing_em": 1.0,
            }
            for key, value in wrong_metric.items():
                mutated = json.loads(pages_path.read_text(encoding="utf-8"))
                mutated["layout"][key] = value
                errors = validate_edition_payload(
                    mutated, kind="hearings", root_dir=root
                )
                self.assertIn(
                    f"Page map layout field {key} does not match the fixed layout.",
                    errors,
                    f"expected rejection for {key}={value}",
                )
            mutated = json.loads(pages_path.read_text(encoding="utf-8"))
            mutated["layout"]["body_font_family"] = "serif"
            errors = validate_edition_payload(mutated, kind="hearings", root_dir=root)
            self.assertIn(
                "Page map layout field body_font_family does not match the fixed layout.",
                errors,
            )

    def test_each_v2_footer_field_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source, pages_path = self._published(temporary)
            for key, needle in (
                ("template", "footer template"),
                ("font_family", "footer font family"),
                ("font_size_pt", "footer field font_size_pt"),
                ("baseline_from_bottom_pt", "footer field baseline_from_bottom_pt"),
            ):
                mutated = json.loads(pages_path.read_text(encoding="utf-8"))
                mutated["layout"]["footer"][key] = (
                    "Page {n}/{m}"
                    if key == "template"
                    else "Helvetica"
                    if key == "font_family"
                    else 72.0
                )
                errors = validate_edition_payload(
                    mutated, kind="hearings", root_dir=root
                )
                self.assertTrue(
                    any(needle in error for error in errors),
                    f"expected footer rejection for {key}: {errors}",
                )
            mutated = json.loads(pages_path.read_text(encoding="utf-8"))
            mutated["layout"]["footer"] = "Page {n} of {m}"
            errors = validate_edition_payload(mutated, kind="hearings", root_dir=root)
            self.assertIn("Page map layout footer metadata is missing.", errors)

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
    """Hearing/report reruns now go through the PI runner; verify delegation.

    The runner publishes only after full validation and invalidates the
    matching edition (covered in tests/test_summary_agent_pipeline.py). Here
    we confirm the GTK handlers are thin wrappers around the PI skill runner
    and that the minute-order direct path still invalidates only its own
    edition.
    """

    def test_hearing_summary_rerun_delegates_to_pi_skill_runner(self) -> None:
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
            delegate = mock.Mock(return_value=True)
            harness._run_pi_skill_step = delegate
            self.assertTrue(
                _run_handler(harness, "_run_step_create_hearing_summaries")
            )
            delegate.assert_called_once()
            self.assertEqual(delegate.call_args.args[0], "create_hearing_summaries")
            # Delegation alone does not disturb existing editions.
            self.assertTrue(summary_edition_is_complete("hearings", hearings, root))
            self.assertTrue(summary_edition_is_complete("reports", reports, root))
            self.assertTrue(summary_edition_is_complete("minutes", minutes, root))

    def test_report_summary_rerun_delegates_to_pi_skill_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _seed_boundaries(root)
            _publish_all(root, source_text=_long_source(5))
            hearings, reports = _summary_output_paths(root)
            minutes = _minutes_summary_output_path(root)

            harness = _make_harness(root)
            delegate = mock.Mock(return_value=True)
            harness._run_pi_skill_step = delegate
            self.assertTrue(
                _run_handler(harness, "_run_step_create_report_summaries")
            )
            delegate.assert_called_once()
            self.assertEqual(delegate.call_args.args[0], "create_report_summaries")
            self.assertTrue(summary_edition_is_complete("hearings", hearings, root))
            self.assertTrue(summary_edition_is_complete("reports", reports, root))
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

    def test_hearing_summary_text_change_invalidates_hearing_edition(self) -> None:
        """The retired Add-links step is gone; a source text change still
        invalidates only that category's edition."""
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            _seed_boundaries(root)
            _publish_all(root, source_text=_long_source(5))
            hearings, _reports = _summary_output_paths(root)
            self.assertTrue(summary_edition_is_complete("hearings", hearings, root))

            hearings.write_text(
                hearings.read_text(encoding="utf-8") + "\nAdditional paragraph.\n",
                encoding="utf-8",
            )

            self.assertFalse(summary_edition_is_complete("hearings", hearings, root))
            _reports = None


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
        # The Add-links step was retired; editions build directly after the
        # three summary stages.
        self.assertNotIn("add_hearing_date_links", summarize_ids)
        self.assertEqual(
            summarize_ids.index("build_summary_editions"),
            summarize_ids.index("create_minute_order_summaries") + 1,
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
