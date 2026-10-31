"""Retire a public choice without migrating private settings or old snapshots."""
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from recordprep import practice_profiles as api
from recordprep.profile_workflows import ProfileEditor


class ProfileRetirementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = api.ProfileStore('recordprep', config_root=self.root / 'config', data_root=self.root / 'data')
        self.dependency = api.validate_profile_directory(api.bundled_profile_directory('california_dependency')).draft
        self.retired = api.validate_profile_directory(api.bundled_profile_directory('general')).draft

    def tree(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def catalog(self):
        return api.profile_catalog(store=self.store, customization=lambda _: None)

    def save(self, snapshot, **kwargs):
        registry = self.store.read_registry()
        return self.store.managed_save(snapshot, expected_head=registry['heads'].get(snapshot.ref.specialty_id),
                                       expected_default=registry['default'], **kwargs)

    def test_fresh_default_and_new_profile_base_are_dependency_without_writes(self):
        self.assertEqual(api.BUNDLED_PROFILES, ('california_dependency',))
        self.assertEqual([c.snapshot.ref for c in self.catalog()], [self.dependency.ref])
        self.assertEqual(api.default_profile_candidate(store=self.store).ref, self.dependency.ref)
        editor = ProfileEditor.create(self.catalog()[0].snapshot, 'California Criminal Law')
        for name in self.dependency.manifest['resources']:
            self.assertEqual(editor.resources[name], self.dependency.resource(name))
        self.assertEqual(self.tree(), {})

    def test_retired_saved_selection_and_personal_edits_stay_readable_but_hidden(self):
        for personal in (False, True):
            with self.subTest(personal=personal):
                editor = ProfileEditor(self.retired)
                if personal:
                    editor.resources['classification_tasks']['rt'] += '\nSynthetic personal retired instructions.'
                retired = editor.snapshot()
                self.save(retired, personal=personal, use_for_new_cases=True)
                before = self.tree()
                self.assertEqual([c.snapshot.ref for c in self.catalog()], [self.dependency.ref])
                self.assertEqual(api.default_profile_candidate(store=self.store).ref, self.dependency.ref)
                self.assertEqual(self.store.load_profile_snapshot(retired.ref).files, retired.files)
                self.assertEqual(self.store.read_registry()['default'], asdict(retired.ref))
                self.assertEqual(self.tree(), before)

    def test_personal_dependency_and_independent_custom_profiles_are_preserved(self):
        self.save(self.retired, personal=False, use_for_new_cases=True)
        editor = ProfileEditor(self.dependency)
        editor.resources['classification_tasks']['page_types']['rt']['RT_body'] += '\nSynthetic personal dependency instructions.'
        dependency = editor.snapshot()
        self.save(dependency, personal=True)
        custom = ProfileEditor.create(self.retired, 'Existing custom practice').snapshot()
        self.save(custom, personal=True)
        before = self.tree()
        self.assertEqual(api.default_profile_candidate(store=self.store).ref, dependency.ref)
        self.assertEqual({c.snapshot.ref for c in self.catalog()}, {dependency.ref, custom.ref})
        self.assertEqual(self.tree(), before)
        self.store.set_default(custom.ref)
        before = self.tree()
        self.assertEqual(api.default_profile_candidate(store=self.store).ref, custom.ref)
        self.assertEqual(self.tree(), before)

    def test_hidden_general_does_not_require_loading_its_old_snapshot(self):
        self.save(self.retired, personal=False, use_for_new_cases=True)
        before = self.tree()
        with patch.object(self.store, 'load_profile_snapshot', side_effect=AssertionError('Retired snapshot read')):
            self.assertEqual(api.default_profile_candidate(store=self.store).ref, self.dependency.ref)
            self.assertEqual([c.snapshot.ref for c in self.catalog()], [self.dependency.ref])
        self.assertEqual(self.tree(), before)


if __name__ == '__main__':
    unittest.main()
