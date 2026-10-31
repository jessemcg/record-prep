"""Public schema-8 release preserves frozen pre-editorial 1.6.0 fixtures."""
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
        self.assertEqual(b.manifest['version'],'1.8.0')
        for name,path in [('classification_tasks','classification-tasks.json'),('naming','naming.json')]:
            self.assertEqual(effective_resource(json.loads((BASE/path).read_bytes()),name),b.resource(name))

    def test_bundle_already_matches_current_editor_resources(self):
        b=api.bundled_profile_for_identity(api.APPLICATION,api.DEFAULT_PROFILE_ID)
        self.assertEqual(b.manifest['schema_version'],8)
        self.assertEqual(editable_profile(b).snapshot().files,b.files)
        self.assertEqual(set(b.manifest['resources']),{'classification_tasks','case_name','naming','hearings','reports','policies','minutes'})
        self.assertEqual(b.resource('policies'),{})
