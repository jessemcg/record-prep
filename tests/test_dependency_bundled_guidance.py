"""Current bundle preserves frozen historical naming and unrelated resource bytes."""
import hashlib
import json
from pathlib import Path
import unittest
from recordprep import practice_profiles as api
from recordprep.profile_editor_ui import editable_profile
from recordprep.structured_guidance import effective_resource

BASE = Path(__file__).parent / 'fixtures/dependency-1.6.0'


class DependencyBundledGuidanceTests(unittest.TestCase):
    def test_promoted_guidance_bytes(self):
        b = api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)
        for path,digest in {
            'case-name.md':'ac60cda00e130e635e15cb7be406317b18a24c0416b7abf2a904b8792dfa016a',
            'reports.json':'f0ee91c592bcd555ba3b8e3f36f9835a9664b194a46195bdb8a02615c2d81c37',
        }.items():
            self.assertEqual(hashlib.sha256(dict(b.files)[path]).hexdigest(),digest)

    def test_exact_pre_editorial_fixture_and_allowlisted_conversion(self):
        self.assertEqual(json.loads((BASE/'profile.json').read_bytes())['version'],'1.6.0')
        self.assertEqual(hashlib.sha256((BASE/'classification-tasks.json').read_bytes()).hexdigest(),'ff5f02032aa081923badf4c40c5df19cb137af8be0c8a4512536fe0dbc97c189')
        b=api.bundled_profile_for_identity(api.APPLICATION,api.DEFAULT_PROFILE_ID)
        self.assertEqual(b.manifest['version'],'1.10.0')
        self.assertNotIn('classification_tasks', b.manifest['resources'])
        old = effective_resource(json.loads((BASE/'naming.json').read_bytes()), 'naming')
        frozen = json.loads((api.bundled_profile_directory('california_dependency').parents[1] /
                             'profile_baselines/dependency-1.6.0/naming-v4.json').read_bytes())
        self.assertEqual(old, frozen)
        self.assertEqual(len(old['reports']), 16)
        self.assertTrue(all(not card['guidance'] for card in old['reports']))
        self.assertNotEqual(old, b.resource('naming'))
        self.assertEqual(old['forms'], b.resource('naming')['forms'])

    def test_bundle_already_matches_current_editor_resources(self):
        b=api.bundled_profile_for_identity(api.APPLICATION,api.DEFAULT_PROFILE_ID)
        self.assertEqual(b.manifest['schema_version'],9)
        self.assertEqual(editable_profile(b).snapshot().files,b.files)
        self.assertEqual(set(b.manifest['resources']),{'case_name','naming','hearings','reports','policies','minutes'})
        self.assertEqual(b.resource('policies'),{})
