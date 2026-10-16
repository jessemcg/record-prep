"""Private controlling-PTY acceptance; no network, native transactions or AI calls."""
import io
import json
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_public_install import ROOT, m


def terminal_run(command, env, responses=(), timeout=12):
    pid, master = pty.fork()
    if pid == 0:
        os.execve(command[0], command, env)
    data = b''; pending = list(responses); deadline = time.monotonic() + timeout; status = None
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], .05)[0]:
                try: block = os.read(master, 65536)
                except OSError: block = b''
                data += block
            if pending and pending[0][0].encode() in data:
                _, response = pending.pop(0); os.write(master, response)
            child, status_value = os.waitpid(pid, os.WNOHANG)
            if child:
                status = os.waitstatus_to_exitcode(status_value)
                while select.select([master], [], [], .05)[0]:
                    try: block = os.read(master, 65536)
                    except OSError: break
                    if not block: break
                    data += block
                return status, data.decode(errors='replace')
        raise AssertionError('PTY child timed out: ' + data.decode(errors='replace'))
    finally:
        if status is None:
            try: os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError: pass
            os.waitpid(pid, 0)
        os.close(master)


class TerminalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='recordprep-pty-'); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.home = self.root / "home '$space"; self.home.mkdir()
        self.bin = self.root / 'bin'; self.bin.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('PI_', 'RECORDPREP_', 'XDG_', 'UV_'))}
        self.env.update(HOME=str(self.home), TERM='xterm-256color', PYTHONIOENCODING='utf-8',
                        PATH=str(self.bin) + ':/usr/bin:/bin', PI_RUN_METRICS_ENABLED='0')
        self.env.pop('NO_COLOR', None)
        self.load = f"import runpy; m=runpy.run_path({str(ROOT / 'scripts/recordprep_maintenance.py')!r}); "

    def test_real_normal_enter_and_ctrl_c(self):
        code = self.load + "\ntry:\n m['approve']('Synthetic path approval', ''); print('CONTINUED')\nexcept KeyboardInterrupt:\n raise SystemExit(130)\n"
        for response, expected in ((b'\n', 0), (b'\x03', 130)):
            with self.subTest(response=response):
                status, output = terminal_run([sys.executable, '-c', code], self.env, [('Press Enter to continue', response)])
                self.assertEqual(status, expected); self.assertIn('Ctrl+C to cancel', output)
                self.assertEqual('CONTINUED' in output, expected == 0)

    def test_optional_pi_enter_skip_eof_cancel_in_controlling_terminal(self):
        code = self.load + "print('RESULT', m['continue_pi_install']())"
        for response, expected in ((b'\n', True), (b'skip\n', False), (b'\x04', False), (b'\x03', False)):
            with self.subTest(response=response):
                status, output = terminal_run([sys.executable, '-c', code], self.env, [('type skip to finish:', response)])
                self.assertEqual(status, 0); self.assertIn(f'RESULT {expected}', output)

    def test_completed_receipt_and_success_precede_real_pi_offer(self):
        code = f'''import sys
sys.path.insert(0, {str(ROOT / 'tests')!r})
from test_public_install import InstallTests, m
real_prompt = m.continue_pi_install
case = InstallTests(); case.setUp()
try:
 args = case.lifecycle()
 m.continue_pi_install = real_prompt
 def optional(env):
  assert case.receipt()['phase'] == 'complete'
  print('OPTIONAL_CHILD_FAILURE', flush=True)
  raise RuntimeError('synthetic Pi failure')
 m.install_optional_pi = optional
 sys.stdout = sys.__stdout__
 result = m.install(args)
 assert case.receipt()['phase'] == 'complete'
 assert result == 0
 print('RECORDPREP_STILL_COMPLETE', flush=True)
finally:
 case.doCleanups()
'''
        for response in (b'\n', b'skip\n', b'\x04', b'\x03'):
            with self.subTest(response=response):
                status, output = terminal_run([sys.executable, '-c', code], self.env,
                                             [('type skip to finish:', response)], timeout=20)
                self.assertEqual(status, 0, output)
                self.assertLess(output.index(m.INSTALL_SUCCESS), output.index('Press Enter to install Pi'))
                self.assertIn('RECORDPREP_STILL_COMPLETE', output)
                self.assertEqual('OPTIONAL_CHILD_FAILURE' in output, response == b'\n')

    def test_actual_presentation_and_plain_fallbacks(self):
        code = self.load + "m['welcome'](); m['say']('CHECK','1/8 Platform'); m['say']('OK',m['INSTALL_SUCCESS'])"
        status, output = terminal_run([sys.executable, '-c', code], self.env)
        self.assertEqual(status, 0); self.assertIn("Let's get you set up.", output)
        self.assertIn('8/8 stages passed', output); self.assertIn('\033[1;32m✓ OK', output); self.assertNotIn('\033[2J', output)
        for mode in ('NO_COLOR', 'TERM'):
            env = self.env | ({'NO_COLOR': ''} if mode == 'NO_COLOR' else {'TERM': 'dumb'})
            status, output = terminal_run([sys.executable, '-c', code], env)
            self.assertNotIn('\033[', output); self.assertIn('[OK] ' + m.INSTALL_SUCCESS, output)
        redirected = subprocess.run([sys.executable, '-c', code], env=self.env, capture_output=True, text=True, check=True)
        self.assertNotIn('\033[', redirected.stdout)
        class ASCII(io.StringIO):
            encoding = 'ascii'
            def isatty(self): return True
        with patch.dict(os.environ, self.env, clear=True):
            self.assertIn('[##------]', m.status_text('CHECK', '3/8 Native', ASCII()))

    def fake_downloader(self, body, status=0):
        downloader = self.bin / 'curl'
        downloader.write_text(f'''#!{sys.executable}
import os,sys
from pathlib import Path
args=sys.argv[1:]
flag='--output' if '--output' in args else '-o' if '-o' in args else None
content={body!r}
if flag:
 p=Path(args[args.index(flag)+1]); p.write_text(content)
 Path(os.environ['DOWNLOAD_RECORD']).write_text(str(p))
else: print(content,end='')
sys.exit({status})
''')
        downloader.chmod(0o700); self.env['DOWNLOAD_RECORD'] = str(self.root / 'download-path')

    def test_official_pi_download_executes_in_same_terminal_and_propagates_failure(self):
        for status in (0, 19):
            with self.subTest(child_status=status):
                self.fake_downloader(f'#!/bin/sh\ntest -t 0 && test -t 1 && test -t 2 || exit 99\nprintf "PI_CHILD\\n"\nexit {status}\n')
                code = self.load + "m['install_optional_pi'](dict(__import__('os').environ))"
                result, output = terminal_run([sys.executable, '-c', code], self.env)
                self.assertEqual(result == 0, status == 0); self.assertIn('PI_CHILD', output)
                self.assertFalse(Path((self.root / 'download-path').read_text()).exists())

    def test_failed_partial_pi_download_is_never_executed(self):
        marker = self.root / 'executed'
        self.fake_downloader(f'#!/bin/sh\ntouch {shlex.quote(str(marker))}\n', status=7)
        code = self.load + "m['install_optional_pi'](dict(__import__('os').environ))"
        result, _ = terminal_run([sys.executable, '-c', code], self.env)
        self.assertNotEqual(result, 0); self.assertFalse(marker.exists())
        self.assertFalse(Path((self.root / 'download-path').read_text()).exists())

    def test_piped_bootstrap_reads_tty_forwards_args_and_preserves_child_status(self):
        # This executes the actual platform checks on the current supported host.
        try: m.detect_platform()
        except m.MaintenanceError: self.skipTest('Local platform outside public policy')
        body = '#!/bin/sh\nprintf "CHILD_APPROVAL\\n"\nIFS= read -r line </dev/tty\nprintf "ANSWER=%s ARGS=%s,%s\\n" "$line" "$1" "$2"\nexit 17\n'
        self.fake_downloader(body)
        command = ['/bin/bash', '-c', 'printf %s ' + shlex.quote((ROOT / 'scripts/install-bootstrap.sh').read_text())
                   + ' | /bin/bash -s -- --source-dir "literal $HOME"']
        status, output = terminal_run(command, self.env, [('CHILD_APPROVAL', b'\n')])
        self.assertEqual(status, 17); self.assertIn('ANSWER= ARGS=--source-dir,literal /', output)
        self.assertFalse(Path((self.root / 'download-path').read_text()).exists())

    def test_partial_public_installer_and_engine_downloads_are_not_executed(self):
        try: m.detect_platform()
        except m.MaintenanceError: self.skipTest('Local platform outside public policy')
        marker = self.root / 'executed'
        for target in ('installer', 'engine'):
            with self.subTest(target=target):
                body = ('#!/bin/sh\ntouch ' + shlex.quote(str(marker)) + '\n' if target == 'installer'
                        else 'from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
                self.fake_downloader(body, status=7)
                script = (ROOT / 'scripts/install-bootstrap.sh' if target == 'installer' else self.root / 'install.sh')
                if target == 'engine': script.write_bytes((ROOT / 'install.sh').read_bytes())
                result = subprocess.run(['/bin/bash', str(script)], env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
                self.assertFalse(marker.exists())
                self.assertFalse(Path((self.root / 'download-path').read_text()).exists())

    def test_bootstrap_native_preview_refuses_removal_before_consent_or_sudo(self):
        try: family = m.detect_platform()
        except m.MaintenanceError: self.skipTest('Local platform outside public policy')
        if family != 'apt': self.skipTest('Local apt bootstrap acceptance')
        for name, body in (('dpkg-query', 'printf "git\\tinstalled\\n"'),
                           ('apt-get', 'printf "Remv unrelated [1]\\n"'),
                           ('sudo', 'touch ' + shlex.quote(str(self.root / 'sudo-called')))):
            executable = self.bin / name; executable.write_text('#!/bin/sh\n' + body + '\n'); executable.chmod(0o700)
        for target in ('installer', 'engine'):
            with self.subTest(target=target):
                script = ROOT / ('scripts/install-bootstrap.sh' if target == 'installer' else 'install.sh')
                missing = 'curl|wget' if target == 'installer' else 'python3'
                code = ('command() { if [[ "$1" == -v ]]; then case "$2" in ' + missing
                        + ') return 1;; esac; fi; builtin command "$@"; }; source ' + shlex.quote(str(script)))
                result = subprocess.run(['/bin/bash', '-c', code], env=self.env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('would remove packages', result.stdout + result.stderr)
                self.assertNotIn('Authorize', result.stdout)
                self.assertFalse((self.root / 'sudo-called').exists())

    def test_complete_download_command_refuses_partial_and_cleans_metacharacter_paths(self):
        command = subprocess.check_output([sys.executable, str(ROOT / 'scripts/print-install-command.py'), '--download-first'], text=True).strip()
        temp = self.root / "temporary space '$literal\""; temp.mkdir(); self.env['TMPDIR'] = str(temp)
        for download_status, child_status in ((7, 0), (0, 0), (0, 17)):
            with self.subTest(download=download_status, child=child_status):
                marker = self.root / 'child'; marker.unlink(missing_ok=True)
                self.fake_downloader('printf "%s" "$@" > ' + shlex.quote(str(marker)) + f'\nexit {child_status}\n', download_status)
                result = subprocess.run(['/bin/bash', '-c', command + ' --source-dir "path $literal"'], env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, download_status or child_status)
                self.assertEqual(marker.exists(), not download_status); self.assertFalse(list(temp.iterdir()))


if __name__ == '__main__': unittest.main()
