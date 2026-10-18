"""Standalone maintenance contracts. All state/source/packages/providers are synthetic."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recordprep_maintenance', ROOT / 'scripts/recordprep_maintenance.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='recordprep-install-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home space '$literal"; self.home.mkdir(mode=0o700)
        env = {k: v for k, v in os.environ.items() if not k.startswith(('XDG_', 'RECORDPREP_', 'PI_', 'UV_'))}
        env.update(HOME=str(self.home), PI_RUN_METRICS_ENABLED='0', PATH='/usr/bin:/bin')
        self.enter(patch.dict(os.environ, env, clear=True))
        old = os.umask(0o077); self.addCleanup(os.umask, old)
        self.paths = m.layout(self.home / 'RecordPrep source')
        self.data = {'schema': 1, 'installation_id': 'a' * 32, 'phase': 'preflight',
                     'paths': {k: str(p) for k, p in self.paths.items()}, 'created': [], 'files': {},
                     'tool_versions': {}, 'introduced_packages': [], 'package_family': 'apt', 'config_created': False}
        self.output = io.StringIO(); self.enter(contextlib.redirect_stdout(self.output))

    def enter(self, manager):
        value = manager.__enter__(); self.addCleanup(manager.__exit__, None, None, None); return value

    def receipt(self):
        return m.private_json(self.paths['state'] / 'receipt.json')

    def record(self):
        m.atomic_json(self.paths['state'] / 'receipt.json', self.data)

    def test_platform_policy(self):
        for ident, version, family in [('ubuntu', '24.04', 'apt'), ('ubuntu', '26.04', 'apt'),
                                       ('fedora', '43', 'dnf'), ('fedora', '44', 'dnf')]:
            for arch in ('x86_64', 'aarch64'):
                with self.subTest(ident=ident, version=version, arch=arch):
                    self.assertEqual(m.detect_platform({'ID': ident, 'VERSION_ID': version}, arch, False), family)
        self.assertEqual(m.detect_platform({'ID': 'mint', 'ID_LIKE': 'ubuntu debian', 'UBUNTU_CODENAME': 'noble'}, 'x86_64', False), 'apt')
        for release, arch, immutable in [({'ID': 'ubuntu', 'VERSION_ID': '22.04'}, 'x86_64', False),
                ({'ID': 'debian', 'VERSION_ID': '13'}, 'x86_64', False),
                ({'ID': 'fedora', 'VERSION_ID': '44'}, 'armv7l', False),
                ({'ID': 'fedora', 'VERSION_ID': '44'}, 'x86_64', True),
                ({'ID': 'fedora', 'VERSION_ID': '44', 'VARIANT_ID': 'silverblue'}, 'x86_64', False)]:
            with self.subTest(release=release), self.assertRaises(m.MaintenanceError):
                m.detect_platform(release, arch, immutable)
        self.assertIn('libpoppler-cpp-dev', m.PACKAGES['apt'])
        self.assertTrue({'poppler-cpp-devel', 'gcc-c++', 'cairo-gobject-devel'} <= set(m.PACKAGES['dnf']))

    def test_paths_receipt_permissions_and_lock(self):
        self.record(); self.assertEqual(self.receipt(), self.data)
        self.assertEqual((self.paths['state'] / 'receipt.json').stat().st_mode & 0o777, 0o600)
        with m.lock(self.paths['state']):
            with self.assertRaises(m.MaintenanceError):
                with m.lock(self.paths['state']): pass
        for key, value in [('schema', 2), ('installation_id', '../foreign'), ('created', ['foreign']), ('files', {'command': 'bad'})]:
            with self.subTest(key=key), self.assertRaises(m.MaintenanceError):
                m.validate_receipt(self.data | {key: value}, self.paths)
        link = self.home / 'linked'; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(m.MaintenanceError): m.layout(link / 'source')
        with self.assertRaises(m.MaintenanceError): m.layout(self.home / '.local')
        with patch.dict(os.environ, XDG_DATA_HOME='/tmp'):
            with self.assertRaises(m.MaintenanceError): m.layout(self.paths['source'])

    def test_file_collisions_and_environment_contract(self):
        for key in ('command', 'uninstall_command', 'desktop', 'svg', 'symbolic', 'png'):
            with self.subTest(key=key):
                target = self.paths[key]; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('foreign')
                with self.assertRaises(m.MaintenanceError): m.owned_file(key, target, b'new', self.data, lambda: None)
                target.unlink(); m.owned_file(key, target, b'owned', self.data, lambda: None)
                m.owned_file(key, target, b'updated', self.data, lambda: None)
                target.write_text('modified')
                with self.assertRaises(m.MaintenanceError): m.owned_file(key, target, b'new', self.data, lambda: None)
        self.paths['source'].mkdir(); (self.paths['source'] / 'pyproject.toml').write_text('synthetic'); (self.paths['source'] / 'uv.lock').write_text('locked')
        self.paths['environment'].mkdir(parents=True)
        m.marker(self.paths['environment'], self.data['installation_id'], self.paths['source'])
        m.atomic_json(self.paths['environment'] / 'recordprep-env.json', {'fingerprint': 'old'})
        with self.assertRaisesRegex(m.MaintenanceError, 'Dependencies changed'): m.verify_environment(self.paths)
        m.marker(self.paths['environment'], self.data['installation_id'], self.home / 'foreign')
        with self.assertRaisesRegex(m.MaintenanceError, 'another checkout'): m.verify_environment(self.paths)

    def test_native_transaction_bounds_and_enter(self):
        packages = m.Packages('apt')
        def execute(argv, **kw):
            return subprocess.CompletedProcess(argv, 0, 'Candidate: 1\n' if argv[0] == 'apt-cache' else 'Remv unrelated [1]\n', '')
        with patch.object(m, 'execute', execute):
            with self.assertRaises(m.MaintenanceError): packages.preview(['git'])
            with self.assertRaises(m.MaintenanceError): packages.preview(['git'], remove=True)
        with patch.object(packages, 'preview'), patch.object(m, 'approve') as consent, patch.object(m, 'execute') as run:
            packages.install(['git']); self.assertEqual(consent.call_args.args[1], '')
            self.assertEqual(run.call_args.args[0], ['sudo', 'apt-get', 'install', 'git'])
        with patch.object(packages, 'preview'), patch.object(m, 'approve', side_effect=m.MaintenanceError('cancel')), patch.object(m, 'execute') as run:
            with self.assertRaises(m.MaintenanceError): packages.install(['git'])
            run.assert_not_called()

    def test_sync_is_locked_and_run_never_provisions(self):
        source = self.paths['source']; source.mkdir(); (source / 'pyproject.toml').write_text('synthetic'); (source / 'uv.lock').write_text('locked')
        with patch.object(m, 'locate_uv', return_value='/synthetic/uv'), patch.object(m, 'execute') as run, patch.object(m, 'verify_environment'):
            m.synchronize(self.paths, self.data, lambda: None)
        sync = next(c.args[0] for c in run.call_args_list if 'sync' in c.args[0])
        self.assertIn('--locked', sync); self.assertIn('--no-default-groups', sync); self.assertNotIn('--group', sync)
        self.assertFalse((source / '.venv').exists())
        with patch.dict(os.environ, UV_PROJECT_ENVIRONMENT='/foreign', VIRTUAL_ENV='/foreign', PYTHONPATH='/foreign'):
            env = m.python_environment(self.paths)
            self.assertEqual(env['UV_PROJECT_ENVIRONMENT'], str(self.paths['environment']))
            self.assertNotIn('VIRTUAL_ENV', env); self.assertNotIn('PYTHONPATH', env)
        binary = self.paths['environment'] / 'bin/recordprep'; binary.parent.mkdir(); binary.write_text('synthetic')
        self.record()
        def execve(executable, argv, env):
            self.assertEqual(executable, binary); self.assertEqual(argv[-1], 'literal $path')
            self.assertEqual(env['UV_OFFLINE'], '1'); self.assertEqual(env['PI_RUN_METRICS_ENABLED'], '0')
            self.assertEqual(env['RECORDPREP_CONFIG_DIR'], str(self.paths['config']))
            raise SystemExit(0)
        cwd = Path.cwd()
        try:
            with patch.object(m, 'verify_environment'), patch.object(m, 'synchronize', side_effect=AssertionError('provisioned')), patch.object(m.os, 'execve', execve):
                with self.assertRaises(SystemExit):
                    m.run_environment(argparse.Namespace(operation='run', project=str(source), arguments=['recordprep', 'literal $path']))
        finally: os.chdir(cwd)

    def lifecycle(self):
        repo = self.root / 'published'; repo.mkdir()
        for name in ('pyproject.toml', 'uv.lock', 'recordprep_icon.svg', 'recordprep_icon-symbolic.svg', 'recordprep_icon.png', 'install.sh'):
            shutil.copyfile(ROOT / name, repo / name)
        for name in ('scripts', '.pi'):
            shutil.copytree(ROOT / name, repo / name, ignore=shutil.ignore_patterns('__pycache__'))
        # No personal source settings enter the fabricated published repository.
        (repo / '.pi/settings.json').write_text('{}')
        subprocess.run(['git', 'init', '-q', '--initial-branch=main', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        self.enter(patch.object(m, 'REPOSITORY', str(repo)))
        for name, value in [('detect_platform', lambda: 'apt'), ('approve', lambda *a: None), ('continue_pi_install', lambda: False),
                            ('native_meets', lambda *a: True), ('active_processes', lambda *a: []),
                            ('refresh_caches', lambda *a: None), ('verify_environment', lambda *a: {})]:
            self.enter(patch.object(m, name, value))
        for name, value in [('snapshot', lambda *a: {'git', 'curl'}), ('missing', lambda *a: []), ('install', lambda *a: None)]:
            self.enter(patch.object(m.Packages, name, value))
        self.calls = []; original = m.execute
        def execute(command, **kw):
            self.calls.append(command)
            if command[0] in ('git', 'desktop-file-validate'): return original(command, **kw)
            return subprocess.CompletedProcess(command, 0, '', '')
        self.enter(patch.object(m, 'execute', execute))
        def sync(paths, data, save, **kw):
            for name in ('environment', 'python', 'tools', 'cache'):
                if not paths[name].exists():
                    paths[name].mkdir(parents=True); m.marker(paths[name], data['installation_id'], paths['source']); data['created'].append(name)
            save()
        self.enter(patch.object(m, 'synchronize', sync))
        return m.parser().parse_args(['install', '--source-dir', str(self.paths['source'])])

    def test_complete_repair_resume_and_optional_pi_failures(self):
        args = self.lifecycle()
        self.assertEqual(m.install(args), 0); self.assertEqual(self.receipt()['phase'], 'complete')
        self.assertEqual(self.receipt()['source_ref'], 'main')
        branch = subprocess.check_output(['git', '-C', str(self.paths['source']), 'branch', '--show-current'], text=True).strip()
        self.assertEqual(branch, 'recordprep-install')
        edit = self.paths['source'] / 'local-edit.txt'; edit.write_text('retain')
        args.repair = True
        for failure in (None, RuntimeError('Pi failure'), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                self.output.seek(0); self.output.truncate(); self.calls.clear()
                def optional(env):
                    self.assertEqual(self.receipt()['phase'], 'complete')
                    self.assertIn(m.INSTALL_SUCCESS, self.output.getvalue())
                    if failure is not None: raise failure
                with patch.object(m, 'continue_pi_install', return_value=True), patch.object(m, 'install_optional_pi', optional):
                    self.assertEqual(m.install(args), 0)
                self.assertEqual(self.receipt()['phase'], 'complete'); self.assertEqual(edit.read_text(), 'retain')
                self.assertFalse(any('fetch' in c or 'reset' in c or 'stash' in c or 'switch' in c or 'clone' in c for c in self.calls))
                self.assertNotIn('Incomplete at', self.output.getvalue())
        # Discovery errors are also outside the application success boundary.
        with patch.object(m, 'offer_pi_install', side_effect=RuntimeError('discovery failed')):
            self.assertEqual(m.install(args), 0)
        args.resume = True; args.repair = False
        self.assertEqual(m.install(args), 0)
        remove = m.parser().parse_args(['uninstall'])
        self.assertEqual(m.uninstall(remove), 0)
        self.assertTrue(edit.exists()); self.assertTrue(self.paths['config'].exists()); self.assertFalse(self.paths['environment'].exists())

    def test_interrupted_source_can_resume_or_uninstall(self):
        args = self.lifecycle(); original = m.execute
        def interrupted(command, **kw):
            if command[:2] == ['git', 'clone']: raise m.MaintenanceError('interrupted download')
            return original(command, **kw)
        with patch.object(m, 'execute', interrupted):
            with self.assertRaises(m.MaintenanceError): m.install(args)
        self.assertTrue(self.paths['uninstall_command'].exists()); self.assertEqual(self.receipt()['phase'], 'source')
        args.resume = True; self.assertEqual(m.install(args), 0)

    def test_foreign_environment_and_first_cancel_are_preserved(self):
        self.enter(patch.object(m, 'detect_platform', return_value='apt'))
        args = m.parser().parse_args(['install', '--source-dir', str(self.paths['source'])])
        self.paths['environment'].mkdir(parents=True)
        with self.assertRaises(m.MaintenanceError): m.install(args)
        self.paths['environment'].rmdir()
        with patch.object(m, 'approve', side_effect=m.MaintenanceError('cancel')):
            with self.assertRaises(m.MaintenanceError): m.install(args)
        target = self.paths['state'] / 'maintenance.lock'; inode = target.stat().st_ino
        with patch.object(m, 'approve'), patch.object(m, 'owned_file', side_effect=RuntimeError('stop')):
            with self.assertRaises(RuntimeError): m.install(args)
        self.assertEqual(target.stat().st_ino, inode)

    def test_purge_never_removes_documents_or_profile_stores(self):
        for name in ('text_pages/0001.txt', 'image_pages/0001.png', 'nested/input.PDF',
                     'nested/registry.json', 'nested/snapshots/hash/data.json'):
            with self.subTest(name=name):
                root = self.root / 'protected'; target = root / name; target.parent.mkdir(parents=True); target.write_text('synthetic')
                with self.assertRaises(m.MaintenanceError): m.remove_tree(root)
                self.assertEqual(target.read_text(), 'synthetic'); shutil.rmtree(root)
        root = self.paths['config']; root.mkdir(parents=True)
        self.data['config_created'] = True; m.marker(root, self.data['installation_id'], self.paths['source'])
        for name in ('config.json', 'pi/settings.json', 'practice-profiles/registry.json', 'practice-profiles/snapshots/accepted/data.json'):
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('{}')
        with patch.object(m, 'approve') as consent: m.purge_settings(self.paths, self.data)
        self.assertEqual(consent.call_count, 2); self.assertFalse((root / 'config.json').exists())
        self.assertTrue((root / 'practice-profiles/registry.json').exists())
        self.assertTrue((root / 'practice-profiles/snapshots/accepted/data.json').exists())
        self.assertTrue(root.exists())

    def test_active_process_modified_file_and_dry_run_removal(self):
        args = self.lifecycle(); m.install(args)
        with patch.object(m, 'active_processes', return_value=[123]):
            with self.assertRaises(m.MaintenanceError): m.uninstall(m.parser().parse_args(['uninstall']))
        self.assertEqual(m.uninstall(m.parser().parse_args(['uninstall', '--dry-run'])), 0)
        self.assertTrue(self.paths['command'].exists())
        self.paths['command'].write_text('modified')
        with self.assertRaises(m.MaintenanceError): m.uninstall(m.parser().parse_args(['uninstall']))
        self.assertTrue(self.paths['environment'].exists())

    def test_readme_public_surface(self):
        text = (ROOT / 'README.md').read_text()
        self.assertTrue(text.startswith('# RecordPrep\n\n<img src="recordprep_icon.svg" alt="RecordPrep icon" width="96" align="right">'))
        section = text.split('### Uninstall RecordPrep', 1)[1].split('### Uninstall Pi', 1)[0]
        self.assertEqual(section.count('"$HOME/.local/bin/recordprep-uninstall"'), 1)
        self.assertNotIn('--dry-run', section)
        self.assertEqual((ROOT / 'scripts/install-bootstrap.sh').read_bytes(), (ROOT / 'scripts/download-bootstrap.sh.in').read_bytes())
        self.assertIn('The install has been tested with Ubuntu and Fedora.', text)


if __name__ == '__main__': unittest.main()
