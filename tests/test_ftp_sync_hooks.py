"""Verify startup batches sync once and only explicit Apply reloads sync per project."""
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import mock_open, patch

ROOT = Path(__file__).resolve().parents[1] / 'src/utils-docker'


class Project(dict):
    def __getattr__(self, name):
        return self[name]


class FtpSyncHooksTest(unittest.TestCase):
    def execute(self, script, args, batch=False, fail=False):
        projects = {name: Project(active=False) for name in ('first', 'second', 'third')}
        modules = {
            'yaml': SimpleNamespace(safe_load=lambda source: projects),
            'munch': SimpleNamespace(munchify=lambda value: value),
            'nginx_tls': SimpleNamespace(),
        }
        calls = []

        def sync(command, **kwargs):
            calls.append(command)
            self.assertTrue(kwargs.get('check'))
            if fail:
                raise subprocess.CalledProcessError(1, command)

        def system(command):
            if batch and command.startswith('/project-config.py '):
                with patch.object(sys, 'argv', command.split()):
                    try:
                        runpy.run_path(str(ROOT / 'project-config.py'), run_name='__main__')
                    except SystemExit as result:
                        self.assertEqual(result.code, 0)
            return 0

        with patch.dict(sys.modules, modules), patch('builtins.open', mock_open()), \
             patch('os.system', side_effect=system), patch('subprocess.run', side_effect=sync), \
             patch.object(sys, 'argv', [script, *args]):
            try:
                runpy.run_path(str(ROOT / script), run_name='__main__')
            except SystemExit as result:
                self.assertEqual(result.code, 0)
        return calls

    def test_startup_syncs_once_for_multiple_projects(self):
        self.assertEqual(self.execute('parse-projects.py', [], batch=True), [['/ftp-sync.py']])

    def test_normal_project_configuration_does_not_sync(self):
        self.assertEqual(self.execute('project-config.py', ['first']), [])

    def test_admin_apply_syncs_once(self):
        self.assertEqual(self.execute('project-config.py', ['first', 'reload']), [['/ftp-sync.py']])

    def test_apply_sync_failure_propagates(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute('project-config.py', ['first', 'reload'], fail=True)

    def test_ftp_has_no_cron_job(self):
        self.assertNotIn('/etc/cron.d/ftp-sync', (ROOT / 'Dockerfile').read_text())
