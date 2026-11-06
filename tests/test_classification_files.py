import tempfile
import unittest
from pathlib import Path
from recordprep import classification_files as files
from recordprep.output_presence import step_outputs_present


class ClassificationFilesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'classification').mkdir()

    def put(self, relative, text='{}\n'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def stage(self, stage, sides=(0, 1), legacy=False):
        return [self.put('classification/' + files.names(stage, legacy=legacy)[i]) for i in sides]

    def test_legacy_resolution_is_readonly_and_needs_no_review_receipt(self):
        expected = self.stage('final', legacy=True)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in expected}
        self.assertEqual(list(files.final_paths(self.root)), expected)
        self.assertEqual(list(files.stage_paths(self.root, 'names')), expected)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in expected})
        self.assertFalse((self.root / files.WORKFLOW).exists())

    def test_failed_new_review_never_falls_back_and_preserves_old_files(self):
        old = self.stage('final', legacy=True)
        self.put(files.RECEIPT)  # Old successful review.
        files.require_review(self.root)
        self.assertFalse(step_outputs_present('correct_classification_agent', self.root))
        for resolve in (files.final_paths, files.navigation_paths):
            with self.assertRaisesRegex(ValueError, 'Correct classification'):
                resolve(self.root)
        self.assertTrue(all(p.read_text() == '{}\n' for p in old))

    def test_new_family_requires_receipt_and_all_sides_without_mixing(self):
        self.stage('names')
        self.stage('final', legacy=True)
        self.stage('final', sides=(0,))
        with self.assertRaises(ValueError): files.final_paths(self.root)
        self.put(files.RECEIPT)
        with self.assertRaisesRegex(ValueError, 'incomplete'): files.final_paths(self.root)
        self.stage('final', sides=(1,))
        self.assertEqual(tuple(p.name for p in files.final_paths(self.root)), files.names('final'))
        self.assertTrue(step_outputs_present('correct_classification_agent', self.root))
        self.put(files.PENDING)
        with self.assertRaisesRegex(ValueError, 'recovery'): files.final_paths(self.root)
        self.assertFalse(step_outputs_present('correct_classification_agent', self.root))

    def test_rt_only_and_ct_only(self):
        for side in (0, 1):
            with self.subTest(side=side):
                for path in (self.root / 'classification').iterdir(): path.unlink()
                self.stage('names', sides=(side,))
                self.stage('final', sides=(side,))
                self.put(files.RECEIPT)
                paths = files.final_paths(self.root)
                self.assertTrue(paths[side].is_file())
                self.assertFalse(paths[1-side].exists())

    def test_intermediates_never_mix_filename_families(self):
        self.stage('names', legacy=True)
        self.stage('names', sides=(0,))
        self.assertEqual(tuple(p.name for p in files.stage_paths(self.root, 'names')), files.names('names'))
        self.assertFalse(files.stage_paths(self.root, 'names')[1].exists())

    def test_generic_navigation_only_for_legacy(self):
        generic = self.put('classification/final.jsonl')
        self.assertIn(generic, files.navigation_paths(self.root))
        self.stage('names', sides=(0,))
        self.stage('final', sides=(0,))
        self.put(files.RECEIPT)
        self.assertNotIn(generic, files.navigation_paths(self.root))
