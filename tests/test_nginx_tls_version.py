import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'src/utils-docker'))
import nginx_tls


class NginxVersionTest(unittest.TestCase):
    def test_supplied_version_does_not_access_docker(self):
        with patch.dict(nginx_tls.os.environ, {'WEBCRATE_NGINX_VERSION': '1.30.6'}), patch.object(nginx_tls.subprocess, 'run') as run:
            self.assertEqual(nginx_tls.nginx_version(), (1, 30, 6))
        run.assert_not_called()

    def test_unknown_supplied_version_does_not_access_docker(self):
        with patch.dict(nginx_tls.os.environ, {'WEBCRATE_NGINX_VERSION': 'unknown'}), patch.object(nginx_tls.subprocess, 'run') as run:
            self.assertIsNone(nginx_tls.nginx_version())
        run.assert_not_called()

    def test_running_container_version_is_read_from_stderr(self):
        result = subprocess.CompletedProcess([], 0, '', 'nginx version: nginx/1.28.0\n')
        with patch.object(nginx_tls.subprocess, 'run', return_value=result) as run:
            self.assertEqual(nginx_tls.nginx_version(), (1, 28, 0))
        self.assertEqual(run.call_args.args[0][-2:], ['nginx', '-v'])

    def test_stopped_container_uses_its_actual_image(self):
        with patch.object(nginx_tls.subprocess, 'run', side_effect=[
            subprocess.CalledProcessError(1, 'docker exec'),
            subprocess.CompletedProcess([], 0, 'sha256:test-image\n', ''),
            subprocess.CompletedProcess([], 0, '', 'nginx version: nginx/1.24.0'),
        ]) as run:
            self.assertEqual(nginx_tls.nginx_version(), (1, 24, 0))
        self.assertIn('sha256:test-image', run.call_args.args[0])

    def test_missing_container_uses_configured_default_image(self):
        with patch.object(nginx_tls.subprocess, 'run', side_effect=[
            subprocess.CalledProcessError(1, 'docker exec'),
            subprocess.CalledProcessError(1, 'docker inspect'),
            subprocess.CompletedProcess([], 0, '', 'nginx version: nginx/1.28.0'),
        ]):
            self.assertEqual(nginx_tls.nginx_version(), (1, 28, 0))

    def test_unavailable_docker_falls_back_to_compatible_syntax(self):
        with patch.object(nginx_tls.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(nginx_tls.tls_listen(), 'listen 1443 ssl http2;')

    def test_render_templates_for_old_and_new_nginx(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            certs = root / 'openssl/demo'
            certs.mkdir(parents=True)
            for filename in ('privkey.pem', 'fullchain.pem'):
                (certs / filename).touch()
            for template in ('ssl.conf', 'redirect-ssl.conf'):
                (root / template).write_text((Path(__file__).parents[1] / 'src/utils-docker' / template).read_text())
                for version in ((1, 24, 0), (1, 25, 0), (1, 25, 1), (1, 28, 0)):
                    with self.subTest(template=template, version=version), patch.object(nginx_tls, 'nginx_version', return_value=version):
                        content = nginx_tls.render('demo', 'openssl', template, root)
                        if version >= (1, 25, 1):
                            self.assertIn('listen 1443 ssl;\nhttp2 on;', content)
                            self.assertNotIn('ssl http2', content)
                        else:
                            self.assertIn('listen 1443 ssl http2;', content)
                            self.assertNotIn('http2 on;', content)
                        self.assertNotIn('%tls_listen%', content)


if __name__ == '__main__':
    unittest.main()
