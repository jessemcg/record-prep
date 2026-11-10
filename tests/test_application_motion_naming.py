"""Motion naming is universal; report/form catalogs remain personal. Offline only."""
import copy
from pathlib import Path
import unittest

from recordprep.classification_profiles import classifier_prompt, component
from recordprep.document_naming import compile_motion_naming, compile_naming_profile
from recordprep.motion_guidance import NEUTRAL_MOTION_NAMING
from recordprep.profile_contract import compile_stage_profile, json_bytes, validate_contents, ProfileError
from recordprep.profile_workflows import ProfileEditor
from recordprep.prompt_inspection import DraftInspectionState, inspect_prompt
from test_structured_classification import bundle


def historical(catalog, version=12):
    from test_practice_profiles import historical_snapshot
    base = historical_snapshot(bundle(), version=13)
    files, manifest = dict(base.files), base.manifest
    manifest['schema_version'] = version
    manifest['resources']['motion_naming'] = 'motion-naming.json'
    files['motion-naming.json'] = json_bytes(catalog)
    if version == 11:
        manifest['resources']['motions'] = 'motions.json'
        files['motions.json'] = json_bytes([{'id': 'legacy', 'title': 'Legacy', 'guidance': 'Historical only'}])
    files['profile.json'] = json_bytes(manifest)
    return validate_contents(tuple(files.items()), 'recordprep')


class ApplicationMotionNamingTests(unittest.TestCase):
    def test_all_profiles_ignore_historical_catalog_and_identity(self):
        expected = compile_motion_naming(None)
        custom = copy.deepcopy(NEUTRAL_MOTION_NAMING)
        custom['motions'][0].update(name='CANARY NAME', guidance='CANARY Include forms and exclude replies')
        profiles = [bundle(), historical(custom), historical(custom, 11),
                    historical({'schema_version': 1, 'motions': []})]
        for profile in profiles:
            before = profile.files
            self.assertEqual(compile_motion_naming(profile), expected)
            self.assertEqual(classifier_prompt(profile, 'motion')[0], expected.prompt)
            self.assertNotIn('CANARY', expected.prompt)
            self.assertEqual(profile.files, before)
            compiled = compile_stage_profile(profile, 'motion_naming', core_contract=expected.prompt.encode())
            self.assertNotIn('CANARY', str(compiled))
        self.assertIn('Standardized forms, custom-written and handwritten requests are equally eligible', expected.prompt)
        self.assertNotIn('court request forms remain Forms', expected.prompt)
        self.assertIn('neutral agency reports remain Reports', expected.prompt)
        self.assertIn('source title', expected.prompt)
        self.assertEqual(component(profiles[1], 'names'), component(profiles[-1], 'names'))

    def test_report_and_form_edits_still_control_their_own_prompts(self):
        base = bundle()
        for kind in ('report', 'form'):
            editor = ProfileEditor(base)
            editor.resources['naming'][kind + 's'][0]['guidance'] += ' CANARY specialty eligibility.'
            changed = editor.snapshot()
            self.assertNotEqual(compile_naming_profile(base, kind).prompt,
                                compile_naming_profile(changed, kind).prompt)
            self.assertNotEqual(component(base, 'names'), component(changed, 'names'))
            self.assertEqual(compile_motion_naming(base), compile_motion_naming(changed))
            other = 'form' if kind == 'report' else 'report'
            self.assertEqual(compile_naming_profile(base, other).prompt,
                             compile_naming_profile(changed, other).prompt)

    def test_projection_drops_only_retired_motion_resource_without_mutating_original(self):
        old = historical(NEUTRAL_MOTION_NAMING)
        before = old.files
        editor = ProfileEditor(old)
        self.assertEqual(editor.snapshot().files, before)
        editor.use_current_schema()
        current = editor.snapshot()
        self.assertEqual(current.manifest['schema_version'], 14)
        self.assertNotIn('motion_naming', current.manifest['resources'])
        self.assertNotIn('motion-naming.json', dict(current.files))
        for name in ('naming', 'reports'):
            path = old.manifest['resources'][name]
            self.assertEqual(dict(current.files)[path], dict(old.files)[path])
        self.assertEqual(old.files, before)
        files, manifest = dict(current.files), current.manifest
        manifest['resources']['motion_naming'] = 'motion-naming.json'
        files['profile.json'] = json_bytes(manifest)
        files['motion-naming.json'] = json_bytes(NEUTRAL_MOTION_NAMING)
        with self.assertRaises(ProfileError):
            validate_contents(tuple(files.items()), 'recordprep')

    def test_preview_ignores_even_invalid_unsaved_drafts(self):
        project = Path(__file__).resolve().parents[1] / '.pi'
        draft = DraftInspectionState({'motion_naming': {'CANARY': True}}, (), ('INVALID CANARY',), None)
        for template in (True, False):
            result = inspect_prompt({}, 'motion', project, template=template, draft=draft)
            self.assertEqual(result.components[0][1], compile_motion_naming(None).prompt)
            self.assertFalse(result.issues)
            self.assertNotIn('CANARY', result.display_text())


if __name__ == '__main__':
    unittest.main()
