import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pylatexenc.latex2text import LatexNodes2Text

from recordprep.ui.main_window import (
    _convert_html_tables,
    _ocr_image,
    _strip_markdown,
    _strip_nonstandard_characters,
)


class LocalOcrGroundingTests(unittest.TestCase):
    def test_request_uses_grounding_and_larger_budget(self):
        raw = '![text](10,10,900,800)\nSynthetic text\n![page_number](800,900,950,980)\n-18-'
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / 'page.png'
            image.write_bytes(b'synthetic image')
            with patch('recordprep.ui.main_window.requests.post') as post:
                post.return_value.json.return_value = {
                    'choices': [{'message': {'content': raw}, 'finish_reason': 'stop'}]
                }
                self.assertEqual(_ocr_image(image, 'http://127.0.0.1:8000/v1/chat/completions', 'test-model'), raw)
                payload = post.call_args.kwargs['json']
                self.assertEqual(payload['max_tokens'], 4096)
                self.assertEqual(payload['model'], 'test-model')
                content = payload['messages'][0]['content']
                self.assertEqual(content[0]['type'], 'image_url')
                self.assertEqual(content[1], {'type': 'text', 'text': 'grounding'})
                post.return_value.raise_for_status.assert_called_once()

    def test_cleanup_removes_region_markers_not_footer_text(self):
        raw = ('![header](10,10,900,80)\nSYNTHETIC HEADER\n\n'
               '![text](10,100,900,800)\nBody text\n\n'
               '![footer](10,900,400,980)\nReport 7\n\n'
               '![page_number](800,900,950,980)\n-18-\n')
        cleaned = _strip_markdown(_convert_html_tables(raw))
        for expected in ('SYNTHETIC HEADER', 'Body text', 'Report 7', '-18-'):
            self.assertIn(expected, cleaned)
        self.assertNotIn('![', cleaned)

    def test_inline_grounding_markers_preserve_both_page_numbers(self):
        raw = ('![text](10,100,900,800) Synthetic body\n\n'
               '![page_number](880,850,900,880) 7\n\n'
               '![page_number](910,960,970,990) --18--\n')
        cleaned = _strip_nonstandard_characters(raw)
        cleaned = _convert_html_tables(cleaned)
        cleaned = LatexNodes2Text().latex_to_text(cleaned)
        cleaned = _strip_markdown(cleaned)
        self.assertIn('Synthetic body', cleaned)
        self.assertIn('7', cleaned.splitlines())
        self.assertRegex(cleaned, r'(?m)^[-–—]+18[-–—]+$')
        self.assertNotIn('![', cleaned)


if __name__ == '__main__':
    unittest.main()
