"""Minute PDF spacing follows source entry boundaries, not every line."""
import copy
from pathlib import Path
import tempfile
import unittest

import fitz

from recordprep.summary_editions import (
    BODY_FONT_SIZE_PT, BODY_LINE_HEIGHT, build_summary_edition,
    validate_edition_payload,
)


ENTRY = (
    "January 8, 2026 — Review hearing\n"
    "Appearances: Alex Example appeared with counsel.\n"
    'Orders: The court ordered “continued services” [CT 1](page:1).\n'
    "Next: Review hearing on April 8, 2026."
)


class MinuteEditionSpacingTests(unittest.TestCase):
    def build(self, root, text, kind="minutes"):
        path = root / f"{kind}.txt"
        path.write_text(text, encoding="utf-8")
        return build_summary_edition(kind, path, root)

    def test_pdf_geometry_and_sidecar_preserve_entry_boundaries(self):
        text = ENTRY + "\n\n" + ENTRY
        with tempfile.TemporaryDirectory() as tmp:
            edition = self.build(Path(tmp), text)
            with fitz.open(stream=edition.pdf_bytes, filetype="pdf") as doc:
                lines = [line for block in doc[0].get_text("dict")["blocks"]
                         for line in block.get("lines", [])][:-1]
                ys = [line["bbox"][1] for line in lines]
                self.assertEqual(len(ys), 8)
                leading = BODY_FONT_SIZE_PT * BODY_LINE_HEIGHT
                for index in range(1, 8):
                    self.assertAlmostEqual(ys[index] - ys[index - 1],
                                           leading * (2 if index == 4 else 1), places=3)
            printable = ENTRY.replace('“', '').replace('”', '').replace('[CT 1](page:1)', 'CT 1')
            self.assertEqual(edition.pages[0].text, printable + "\n\n" + printable)
            self.assertEqual(len(edition.pages[0].links), 2)
            self.assertEqual(len(edition.pages[0].quotes), 2)
            self.assertEqual((Path(tmp) / 'minutes.txt').read_text(), text)

    def test_only_minute_field_prefixes_are_bold_without_quote_links(self):
        text = ("January 8, 2026 — Review hearing\n"
                "Appearances: Alex Example appeared.\n"
                "Orders: Services continued.\n"
                "Next: Review hearing in April.\n\n"
                "The Orders: word in prose stays plain.\n"
                "Next:door is not a field prefix.")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for kind in ('minutes', 'hearings', 'reports'):
                edition = self.build(root, text, kind)
                with fitz.open(stream=edition.pdf_bytes, filetype='pdf') as doc:
                    bold = [span['text'] for page in doc
                            for block in page.get_text('dict')['blocks']
                            for line in block.get('lines', [])
                            for span in line['spans'] if span['flags'] & 16]
                self.assertEqual(bold, ['Appearances:', 'Orders:', 'Next:']
                                 if kind == 'minutes' else [])
                self.assertFalse(any(page.quotes or page.links for page in edition.pages))
                if kind == 'minutes':
                    payload = copy.deepcopy(edition.page_map)
                    payload['layout'].pop('minute_label_emphasis')
                    errors = validate_edition_payload(
                        payload, kind=kind, root_dir=root, source_text=text,
                        pdf_bytes=edition.pdf_bytes)
                    self.assertEqual(len(errors), 1)
                    self.assertIn('label emphasis', errors[0])

    def test_wrapping_page_breaks_and_multiple_blank_lines(self):
        entry = ENTRY.replace('continued services', 'continued services ' * 100)
        text = (entry + '\n\n\n') * 15
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edition = self.build(root, text)
            self.assertGreater(len(edition.pages), 2)
            self.assertEqual(validate_edition_payload(
                edition.page_map, kind='minutes', root_dir=root,
                source_text=text, pdf_bytes=edition.pdf_bytes), [])
            for page in edition.pages:
                self.assertNotIn('\n\n\n', page.text)
                for span in (*page.links, *page.quotes):
                    self.assertEqual(page.text[span.start:span.end], span.label)

    def test_old_minute_spacing_stales_only_minutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for kind in ('minutes', 'hearings', 'reports'):
                edition = self.build(root, ENTRY, kind)
                payload = copy.deepcopy(edition.page_map)
                payload['layout'].pop('minute_spacing', None)
                errors = validate_edition_payload(payload, kind=kind, root_dir=root,
                                                  source_text=ENTRY, pdf_bytes=edition.pdf_bytes)
                self.assertEqual(bool(errors), kind == 'minutes')
                if errors:
                    self.assertIn('spacing', errors[0])


if __name__ == '__main__':
    unittest.main()
