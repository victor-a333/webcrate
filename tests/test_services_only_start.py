"""Exercise CLI startup routing and configuration generation without Docker."""
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class ServicesOnlyStartTest(unittest.TestCase):
    def run_start(self, *options, fail=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            includes = root / 'bin/includes'
            includes.mkdir(parents=True)
            (root / 'bin/webcrate').write_text((REPO / 'bin/webcrate').read_text())
            (includes / 'generate-config.inc').write_text((REPO / 'bin/includes/generate-config.inc').read_text())
            (root / '.env').write_text('')
            (includes / 'init.inc').write_text('')
            (includes / 'functions.inc').write_text('''writeLog() { :; }
docker() {
  echo "$*" >> calls
  if [ "$1" = exec ]; then
    echo 'nginx version: nginx/1.30.6' >&2
  fi
}
''')
            for name in ('services', 'projects', 'redirects'):
                (includes / f'{name}.inc').write_text(f'echo {name} >> calls\n' + ('return 1\n' if fail and name == 'services' else ''))
            result = subprocess.run(['bash', str(root / 'bin/webcrate'), 'start', *options], capture_output=True, text=True)
            calls = (root / 'calls').read_text() if (root / 'calls').exists() else ''
            return result, calls

    def test_services_only_skips_project_and_redirect_generation_and_start(self):
        result, calls = self.run_start('--services-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('/parse-services.py', calls)
        self.assertIn('WEBCRATE_NGINX_VERSION=1.30.6', calls)
        self.assertIn('\nservices\n', '\n' + calls)
        for group in ('projects', 'redirects'):
            self.assertNotIn(f'/parse-{group}.py', calls)
            self.assertNotIn(f'\n{group}\n', '\n' + calls)

    def test_default_start_keeps_all_groups(self):
        result, calls = self.run_start()
        self.assertEqual(result.returncode, 0, result.stderr)
        for group in ('services', 'projects', 'redirects'):
            self.assertIn(f'/parse-{group}.py', calls)
            self.assertIn(f'\n{group}\n', '\n' + calls)

    def test_service_failure_returns_nonzero(self):
        result, calls = self.run_start('--services-only', fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('\nprojects\n', '\n' + calls)

    def test_invalid_options_have_no_startup_effect(self):
        for options in (('--unknown',), ('--services-only', '--unknown')):
            with self.subTest(options=options):
                result, calls = self.run_start(*options)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, '')
