from pathlib import Path
import importlib
import json
import os
import sys
import tempfile
import tarfile
import zipfile

package, target, artifacts = sys.argv[1:]
sys.path.insert(0, target)
api = importlib.import_module(package + '.practice_profiles')
assert Path(api.__file__).is_relative_to(Path(target)), api.__file__
store_module = importlib.import_module(package + '.profile_store')
workflow = importlib.import_module(package + '.profile_workflows')
for archive in Path(artifacts).iterdir():
    if not archive.name.endswith(('.whl', '.tar.gz')):
        continue
    if archive.suffix == '.whl':
        with zipfile.ZipFile(archive) as opened:
            names = opened.namelist()
    else:
        with tarfile.open(archive) as opened:
            names = opened.getnames()
    for profile in api.BUNDLED_PROFILES:
        original = api.bundled_profile_directory(profile)
        for resource in original.rglob('*'):
            if resource.is_file():
                relative = resource.relative_to(Path(target)).as_posix()
                assert any(item == relative or item.endswith('/' + relative) for item in names), relative
    assert not any(name.endswith('/config.json') or '/case_bundle/' in name or '/.venv/' in name for name in names)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME'):
        os.environ[key] = str(root / key)
    store = store_module.ProfileStore(package, config_root=root / 'private-config', data_root=root / 'private-data')
    candidates = api.profile_catalog(store=store)
    assert [item.snapshot.manifest['display_name'] for item in candidates] == ['General Court Record', 'California Juvenile Dependency']
    assert all(not item.personal and not item.notice for item in candidates)
    assert not store.registry_path.exists()
    for candidate in candidates:
        snapshot = candidate.snapshot
        if package == 'recordprep':
            # Native Pi compilers use the app's source deployment, not a sibling package.
            from recordprep.case_name_profiles import compile_case_name
            from recordprep.classification_profiles import classifier_prompt
            from recordprep.document_naming import compile_naming_profile
            from recordprep.summary_profiles import compile_summary
            assert compile_case_name(snapshot)
            for task in ('rt', 'ct', 'first_hearing', 'first_minute', 'first_form', 'date_hearing', 'date_minute'):
                assert classifier_prompt(snapshot, task)[0]
            for kind in ('report', 'form'):
                assert compile_naming_profile(snapshot, kind).prompt
            for kind in ('hearings', 'reports'):
                for phase in ('extract', 'synthesize'):
                    assert compile_summary(snapshot, kind, phase).prompt
        else:
            from focus.research_profiles import compile_research
            assert compile_research(snapshot).skill
        editor = workflow.ProfileEditor(snapshot)
        key = 'case_name' if package == 'recordprep' else 'answer_guidance'
        editor.resources[key] += '\nSynthetic installed-wheel customization.\n'
        ref = editor.managed_save(store, expected_head=None, expected_default=None,
                                  can_modify=lambda: True, validate=lambda draft: draft,
                                  use_for_new_cases=False, personal=True)
        assert 'Synthetic installed-wheel customization' in store.load_profile_snapshot(ref).resource(key)
    for loaded in list(sys.modules.values()):
        file = getattr(loaded, '__file__', None)
        if file and ('/RecordPrep/recordprep/' in file or '/Focus/focus/' in file):
            raise AssertionError('Source checkout leaked into installed validation')
print('ISOLATED WHEEL/SDIST PROFILE ACCEPTANCE PASSED', package)
