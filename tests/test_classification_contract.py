"""Shared structural taxonomy and advisory-only profile lint."""
import importlib
from pathlib import Path
import unittest

PACKAGE = 'focus' if (Path(__file__).resolve().parents[1] / 'focus').is_dir() else 'recordprep'
contract = importlib.import_module(PACKAGE + '.profile_contract')


class ClassificationContractTests(unittest.TestCase):
    def test_supported_labels_and_advanced_markers_are_distinct(self):
        for task, labels in contract.CLASSIFICATION_PAGE_TYPES.items():
            self.assertEqual(contract.classification_guidance_warning(', '.join(labels), task), '')
            self.assertFalse(set(labels) & set(contract.CLASSIFICATION_FIRST_PAGE_TYPES.values()))
        for task, label in contract.CLASSIFICATION_FIRST_PAGE_TYPES.items():
            self.assertEqual(contract.classification_guidance_warning(label, task), '')

    def test_unknown_wrong_side_and_wrong_stage_are_advisory(self):
        for text, task in [('CT_custom_report', 'ct'), ('CR_other', 'ct'), ('CT_report', 'rt'),
                           ('RT_body_first_page', 'rt'), ('CT_made_up', 'classification')]:
            with self.subTest(text=text):
                result = contract.classification_guidance_warning(text, task)
                self.assertIn(text, result)
                self.assertIn('does not block Save', result)
        self.assertEqual(contract.classification_guidance_warning('Use ct_report.', 'ct'), '')
        self.assertEqual(contract.classification_guidance_warning('Recognize expert reports.', 'ct'), '')

    def test_lint_does_not_echo_prose_or_grow_without_bound(self):
        result = contract.classification_guidance_warning('PRIVATE PROSE ' + ' '.join(
            'CT_' + 'x' * 100 + str(i) for i in range(50)), 'ct')
        self.assertNotIn('PRIVATE PROSE', result)
        self.assertLess(len(result), 1400)


if __name__ == '__main__':
    unittest.main()
