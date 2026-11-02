"""Check host version detection and generation-container arguments without Docker."""
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class GenerateConfigVersionTest(unittest.TestCase):
    def generate(self, scenario):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            includes = root / 'bin/includes'
            includes.mkdir(parents=True)
            (root / '.env').write_text('')
            (includes / 'init.inc').write_text('')
            (includes / 'generate-config.inc').write_text((REPO / 'bin/includes/generate-config.inc').read_text())
            launcher = root / 'bin/webcrate'
            launcher.write_text('''writeLog() { :; }
docker() {
  echo "$*" >> "$TEST_CALLS"
  case "$1" in
    exec)
      [ "$TEST_SCENARIO" = running ] || return 1
      echo 'nginx version: nginx/1.30.6' >&2 ;;
    inspect)
      [ "$TEST_SCENARIO" = missing ] && return 1
      echo 'sha256:actual-image' ;;
    run)
      if [[ " $* " == *" --entrypoint nginx "* ]]; then
        [ "$TEST_SCENARIO" = unavailable ] && return 1
        echo 'nginx version: nginx/1.24.0' >&2
      fi ;;
  esac
  return 0
}
source "$(dirname "$0")/includes/generate-config.inc"
''')
            import os
            env = dict(os.environ, TEST_SCENARIO=scenario, TEST_CALLS=str(root / 'calls'))
            result = subprocess.run(['bash', str(launcher)], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = (root / 'calls').read_text().splitlines()
            generators = [line for line in calls if '--entrypoint /parse-' in line]
            self.assertEqual(len(generators), 3)
            for line in generators:
                self.assertNotIn('/var/run/docker.sock', line)
            return calls, generators

    def test_running_version_detected_once_and_passed_to_all_generators(self):
        calls, generators = self.generate('running')
        self.assertEqual(sum(line.startswith('exec ') for line in calls), 1)
        self.assertEqual(len(calls), 4)
        for line in generators:
            self.assertIn('WEBCRATE_NGINX_VERSION=1.30.6', line)

    def test_stopped_container_uses_its_image(self):
        calls, generators = self.generate('stopped')
        self.assertTrue(any('--entrypoint nginx sha256:actual-image -v' in line for line in calls))
        for line in generators:
            self.assertIn('WEBCRATE_NGINX_VERSION=1.24.0', line)

    def test_missing_container_uses_default_image(self):
        calls, generators = self.generate('missing')
        self.assertTrue(any('--entrypoint nginx ace5040/webcrate-nginx:stable -v' in line for line in calls))

    def test_detection_failure_passes_explicit_unknown(self):
        calls, generators = self.generate('unavailable')
        for line in generators:
            self.assertIn('WEBCRATE_NGINX_VERSION=unknown', line)
