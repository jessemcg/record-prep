"""Classification has one editable prompt per task, with no shared guidance."""
import tempfile
import unittest
from pathlib import Path

from recordprep import practice_profiles as api
from recordprep.classification_profiles import KINDS, classifier_prompt, component
from recordprep.profile_contract import compile_stage_profile, json_bytes, validate_contents
from recordprep.profile_editor_ui import editable_profile
from recordprep.profile_workflows import ProfileEditor
from test_practice_profiles import historical_snapshot


class TaskOnlyClassificationTests(unittest.TestCase):
    def setUp(self):
        self.base = api.validate_profile_directory(api.bundled_profile_directory('california_dependency')).draft

    def test_public_resources_and_new_copies_omit_common_guidance(self):
        for name in (*api.BUNDLED_PROFILES, 'general'):
            directory = api.bundled_profile_directory(name)
            base = api.validate_profile_directory(directory).draft
            self.assertEqual(base.manifest['schema_version'], 6)
            self.assertNotIn('classification', base.manifest['resources'])
            self.assertFalse((directory / 'classification.md').exists())
            self.assertNotIn('classification', ProfileEditor.create(base, 'Synthetic copy').resources)
            manifest = base.manifest
            manifest['resources']['classification'] = 'classification.md'
            files = dict(base.files) | {'profile.json': json_bytes(manifest), 'classification.md': b'Rejected field'}
            with self.assertRaises(ValueError):
                validate_contents(tuple(files.items()), 'recordprep')

    def test_old_common_text_never_enters_prompts_or_component_hashes(self):
        for version in range(1, 6):
            old = historical_snapshot(self.base, version)
            editor = ProfileEditor(old)
            editor.resources['classification'] = 'RETIRED_COMMON_CANARY'
            revised = editor.snapshot()
            for task in KINDS:
                self.assertEqual(classifier_prompt(old, task), classifier_prompt(revised, task))
                self.assertNotIn('RETIRED_COMMON_CANARY', classifier_prompt(revised, task)[0])
            for stage in ('basic', 'advanced', 'corrected', 'dates', 'names'):
                self.assertEqual(component(old, stage), component(revised, stage))
            self.assertNotIn('classification', dict(compile_stage_profile(revised, 'classification', core_contract=b'core').resources))

    def test_schema_cleanup_preserves_unrelated_stage_components(self):
        old = historical_snapshot(self.base, 5)
        current = self.base
        for stage in ('participants', 'overview', 'hearing_extraction', 'report_extraction',
                      'hearing_synthesis', 'report_synthesis', 'minutes', 'naming'):
            self.assertEqual(
                compile_stage_profile(old, stage, core_contract=b'core').component_sha256,
                compile_stage_profile(current, stage, core_contract=b'core').component_sha256)

    def test_explicit_edit_and_save_remove_field_and_text_not_just_the_widget(self):
        for version in range(1, 6):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = api.ProfileStore('recordprep', config_root=root/'config', data_root=root/'data')
                old_editor = ProfileEditor(historical_snapshot(self.base, version))
                old_editor.resources['classification'] = 'RETIRED_COMMON_CANARY'
                old = old_editor.snapshot()
                editor = editable_profile(old)
                self.assertEqual(editor.manifest['schema_version'], 6)
                self.assertNotIn('classification', editor.resources)
                ref = editor.managed_save(store, expected_head=None, expected_default=None,
                                          validate=lambda draft: classifier_prompt(draft, 'rt'), can_modify=lambda: True)
                saved = store.load_profile_snapshot(ref)
                self.assertNotIn('classification', saved.manifest['resources'])
                self.assertFalse(any(b'RETIRED_COMMON_CANARY' in data for _, data in saved.files))
                self.assertFalse((store.data_root/'snapshots'/ref.content_sha256/'classification.md').exists())
                self.assertEqual(old.resource('classification'), 'RETIRED_COMMON_CANARY')


if __name__ == '__main__':
    unittest.main()
