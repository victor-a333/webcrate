import sys
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'src/utils-docker'))
import certificates as certs
import service_settings
import nginx_tls


class ServiceCertificatesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'ssl.conf').write_text('ssl_certificate /webcrate/%type%/%path%/fullchain.pem;')
        self.service = SimpleNamespace(name='admin', domain='host-site.mediapro.ua', https='letsencrypt')
        self.helpers = Mock()
        self.helpers.load_domains.return_value = ''

    def issue(self, args, **kwargs):
        if args[0] == 'certbot':
            directory = self.root / 'letsencrypt/live' / self.service.name
            directory.mkdir(parents=True)
            for name in ('privkey.pem', 'fullchain.pem'):
                (directory / name).write_text('certificate')
        return SimpleNamespace(returncode=0)

    def test_first_issuance_admin_and_grafana(self):
        for name in ('admin', 'grafana'):
            with self.subTest(service=name):
                self.service.name = name
                with patch.object(certs.subprocess, 'run', side_effect=self.issue) as run:
                    certs.initialize(self.service, self.root)
                self.assertIn(f'letsencrypt/live/{name}/fullchain.pem',
                              (self.root / f'nginx/ssl/{name}.conf').read_text())
                self.assertEqual((self.root / f'letsencrypt-meta/domains-{name}.txt').read_text(), self.service.domain)
                self.assertEqual(run.call_args_list[0].args[0][-1], '-t')

    def test_failure_does_not_install_config_or_record_success(self):
        def fail(args, **kwargs):
            if args[0] == 'certbot':
                raise subprocess.CalledProcessError(1, args)
        with patch.object(certs.subprocess, 'run', side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                certs.initialize(self.service, self.root)
        self.assertFalse((self.root / 'nginx/ssl/admin.conf').exists())
        self.assertFalse((self.root / 'letsencrypt-meta/domains-admin.txt').exists())

    def test_existing_certificate_installs_missing_include_without_issuance(self):
        self.issue(['certbot'])
        (self.root / 'letsencrypt-meta').mkdir(exist_ok=True)
        (self.root / 'letsencrypt-meta/domains-admin.txt').write_text(self.service.domain)
        with patch.object(certs.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            certs.initialize(self.service, self.root)
        self.assertTrue((self.root / 'nginx/ssl/admin.conf').exists())
        self.assertFalse(any(call.args[0][0] == 'certbot' for call in run.call_args_list))

    def test_disabled_removes_include(self):
        target = self.root / 'nginx/ssl/admin.conf'
        target.parent.mkdir(parents=True)
        target.write_text('old')
        self.service.https = 'disabled'
        with patch.object(certs.subprocess, 'run'):
            certs.initialize(self.service, self.root)
        self.assertFalse(target.exists())

    def test_optional_service_flags(self):
        with patch.dict(certs.os.environ, {'WEBCRATE_SERVICE_STATS': 'false'}):
            self.assertFalse(service_settings.enabled('grafana'))
            self.assertTrue(service_settings.enabled('admin'))
        with patch.dict(certs.os.environ, {'WEBCRATE_SERVICE_STATS': 'true'}):
            self.assertTrue(service_settings.enabled('grafana'))


class CertificateLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'letsencrypt-meta').mkdir()

    def test_email_change_preserves_certificates(self):
        (self.root / 'redirects.yml').write_text('demo:\n  active: true\n  https: letsencrypt\n')
        account = self.root / 'letsencrypt/accounts/acme-v02.api.letsencrypt.org/directory/account'
        account.mkdir(parents=True)
        cert = self.root / 'letsencrypt/live/redirect-demo/fullchain.pem'
        cert.parent.mkdir(parents=True)
        cert.write_text('existing certificate')
        (self.root / 'letsencrypt-meta/letsencrypt-email.txt').write_text('old@example.com')
        with patch.dict(certs.os.environ, {'WEBCRATE_ADMIN_EMAIL': 'new@example.com'}), patch.object(certs.subprocess, 'run') as run:
            certs.initialize_account(self.root)
        self.assertEqual(run.call_args.args[0][1], 'update_account')
        self.assertEqual(cert.read_text(), 'existing certificate')

    def test_renew_redirect_only_lineage_without_yaml(self):
        renewal = self.root / 'letsencrypt/renewal'
        renewal.mkdir(parents=True)
        (renewal / 'redirect-demo.conf').write_text('saved lineage')
        with patch.object(certs.subprocess, 'run') as run:
            certs.renew(self.root)
        self.assertEqual(run.call_args.args[0][1], 'renew')
        self.assertTrue((self.root / 'letsencrypt-meta/well-known/redirect-demo').is_dir())

    def test_renew_failure_propagates(self):
        renewal = self.root / 'letsencrypt/renewal'
        renewal.mkdir(parents=True)
        (renewal / 'admin.conf').touch()
        with patch.object(certs.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'certbot')):
            with self.assertRaises(subprocess.CalledProcessError):
                certs.renew(self.root)

    def test_tls_validation_failure_restores_previous_include(self):
        path = self.root / 'nginx/ssl/demo.conf'
        path.parent.mkdir(parents=True)
        path.write_text('old valid configuration')
        with patch.object(nginx_tls, 'render', return_value='new configuration'), patch.object(nginx_tls, 'reload_nginx', side_effect=RuntimeError('invalid nginx config')):
            with self.assertRaises(RuntimeError):
                nginx_tls.configure('demo', 'openssl', root=self.root, reload=True)
        self.assertEqual(path.read_text(), 'old valid configuration')

    def test_redirect_template_and_webroot_persist(self):
        (self.root / 'redirect-ssl.conf').write_text('redirect TLS %type%/%path%')
        target = SimpleNamespace(name='redirect-demo', domains=['b.example.com', 'a.example.com'], https='letsencrypt')
        def issue(args, **kwargs):
            if args[0] == 'certbot':
                directory = self.root / 'letsencrypt/live/redirect-demo'
                directory.mkdir(parents=True)
                for part in ('privkey.pem', 'fullchain.pem'):
                    (directory / part).write_text('cert')
            return SimpleNamespace(returncode=0)
        with patch.object(certs.subprocess, 'run', side_effect=issue):
            certs.initialize(target, self.root, 'redirect-ssl.conf')
        self.assertTrue((self.root / 'letsencrypt-meta/well-known/redirect-demo').is_dir())
        self.assertEqual((self.root / 'letsencrypt-meta/domains-redirect-demo.txt').read_text(), 'a.example.com,b.example.com')
        self.assertEqual((self.root / 'nginx/ssl/redirect-demo.conf').read_text(), 'redirect TLS letsencrypt/live/redirect-demo')


class StartupCertificateFailureTest(unittest.TestCase):
    def test_account_registration_failure_is_logged_and_nonfatal(self):
        logger = Mock()
        error = subprocess.CalledProcessError(1, ['certbot', 'register'])
        with patch.object(certs, 'init_openssl_root_conf'), patch.object(certs, 'initialize_account', side_effect=error), patch('sys.stderr'):
            certs.prepare_startup(logger)
        self.assertIn('ACME account', logger.write.call_args.args[0])
        self.assertIn('continuing startup', logger.write.call_args.args[0])

    def test_leaf_failure_is_logged_and_nonfatal(self):
        logger = Mock()
        target = SimpleNamespace(name='admin')
        with patch.object(certs, 'initialize', side_effect=RuntimeError('issuance failed')), patch('sys.stderr'):
            self.assertFalse(certs.initialize_for_startup(target, logger))
        self.assertIn('admin', logger.write.call_args.args[0])

    def test_services_initialization_continues_after_certificate_failures(self):
        import builtins
        import runpy
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'services.yml').write_text('admin:\n  mysql_db: false\n')
            (root / 'projects.yml').write_text('{}')
            logger = Mock()
            real_open = builtins.open
            def fixture_open(path, *args, **kwargs):
                if str(path).startswith('/webcrate/'):
                    path = root / Path(path).name
                return real_open(path, *args, **kwargs)
            with patch.dict(sys.modules, {'helpers': Mock(), 'log': SimpleNamespace(log=Mock(return_value=logger)), 'munch': SimpleNamespace(munchify=lambda mapping: {name: SimpleNamespace(**target) for name, target in mapping.items()})}), patch('builtins.open', side_effect=fixture_open), patch.object(certs, 'init_openssl_root_conf'), patch.object(certs, 'initialize_account', side_effect=RuntimeError('invalid email')), patch.object(certs, 'initialize', side_effect=RuntimeError('issuance failed')), patch('os.system', return_value=0), patch('sys.stderr'):
                runpy.run_path(str(Path(__file__).parents[1] / 'src/utils-docker/services-init.py'), run_name='__main__')
            self.assertEqual((root / 'dbhosts.txt').read_text(), 'webcrate-mysql')
            self.assertEqual(logger.write.call_count, 2)


if __name__ == '__main__':
    unittest.main()
