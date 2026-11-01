"""Isolated Docker TLS smoke test; requires the built utilities and Nginx images.

Run: python3 tests/docker_certificates.py
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

IMAGE = 'webcrate-certificates-check:local'
PREFIX = 'webcrate-certs-' + uuid.uuid4().hex[:8]
UTILITY, NGINX, CRON = PREFIX + '-utils', PREFIX + '-nginx', PREFIX + '-cron'
ROOT = Path(__file__).resolve().parents[1]


def docker(*args, capture=False):
    return subprocess.run(['docker', *args], check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


try:
    docker('network', 'create', PREFIX)
    docker('volume', 'create', PREFIX)
    docker('run', '-d', '--name', UTILITY, '--network', PREFIX,
           '--network-alias', 'webcrate-admin', '--network-alias', 'webcrate-grafana',
           '-v', PREFIX + ':/webcrate', '-v', '/var/run/docker.sock:/var/run/docker.sock',
           '-e', 'WEBCRATE_NGINX_CONTAINER=' + NGINX,
           '-e', 'WEBCRATE_NGINX_CONFIG=/webcrate/nginx-test.conf',
           '-e', 'WEBCRATE_SERVICE_STATS=true', '-e', 'WEBCRATE_countryName=UA',
           '-e', 'WEBCRATE_organizationName=LocalTest', '-e', 'WEBCRATE_ADMIN_EMAIL=test@example.com',
           '--entrypoint', 'python3', IMAGE, '-m', 'http.server', '8000', '--directory', '/webcrate/content')
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        for directory in ('log', 'meta/redirects', 'dnsmasq/hosts', 'nginx/confs', 'content', 'nginx-templates'):
            (fixture / directory).mkdir(parents=True)
        (fixture / 'content/index.html').write_text('certificate smoke test OK')
        (fixture / 'services.yml').write_text('''admin:
  domain: admin.test
  port: 8000
  https: openssl
  mysql_db: false
grafana:
  domain: grafana.test
  port: 8000
  https: openssl
  mysql_db: false
''')
        (fixture / 'projects.yml').write_text('''demo:
  active: true
  domains: [project.test]
  https: openssl
  mysql_db: false
  mysql5_db: false
''')
        (fixture / 'redirects.yml').write_text('''demo:
  active: true
  domains: [redirect.test]
  https: openssl
  url: https://project.test/target
''')
        for name in ('default-service.conf', 'default-redirect.conf'):
            shutil.copyfile(ROOT / 'config/nginx-templates' / name, fixture / 'nginx-templates' / name)
        (fixture / 'nginx/confs/demo.conf').write_text('''server {
listen 1080;
server_name project.test;
include /webcrate/nginx/ssl/demo.conf*;
location /.well-known { root /webcrate/letsencrypt-meta/well-known/demo; }
location / { root /webcrate/content; }
}
''')
        (fixture / 'nginx-test.conf').write_text('''pid /tmp/nginx.pid;
error_log /dev/stderr notice;
events {}
http {
access_log off;
proxy_temp_path /tmp/proxy;
client_body_temp_path /tmp/client;
fastcgi_temp_path /tmp/fastcgi;
uwsgi_temp_path /tmp/uwsgi;
scgi_temp_path /tmp/scgi;
include /webcrate/nginx/confs/*.conf;
}
''')
        docker('cp', str(fixture) + '/.', UTILITY + ':/webcrate')
    docker('exec', UTILITY, 'chmod', '755', '/webcrate')
    docker('exec', UTILITY, 'chown', '-R', '1000:1000', '/webcrate/log')
    docker('exec', UTILITY, 'python3', '-c', 'import certificates; certificates.init_openssl_root_conf()')
    docker('exec', UTILITY, '/parse-services.py')
    docker('exec', UTILITY, '/redirect-config.py', 'demo')
    docker('run', '-d', '--name', NGINX, '--network', PREFIX,
           '--network-alias', 'admin.test', '--network-alias', 'grafana.test',
           '--network-alias', 'project.test', '--network-alias', 'redirect.test',
           '--user', '1000:1000', '-v', PREFIX + ':/webcrate:ro',
           '--tmpfs', '/webcrate/log:uid=1000,gid=1000',
           '--entrypoint', 'nginx', 'ace5040/webcrate-nginx:stable',
           '-c', '/webcrate/nginx-test.conf', '-g', 'daemon off;')
    docker('exec', UTILITY, '/services-init.py')
    docker('exec', UTILITY, '/project-certs.py', 'demo')
    docker('exec', UTILITY, '/redirect-start.py', 'demo')
    # Verify trusted HTTPS, redirects, repeat startup, and scheduled local renewal.
    docker('exec', UTILITY, 'python3', '-c', '''
import ssl, urllib.request, urllib.error
ctx = ssl.create_default_context(cafile='/webcrate/secrets/rootCA.crt')
for host in ('admin.test', 'grafana.test', 'project.test'):
    with urllib.request.urlopen('https://' + host + ':1443/', context=ctx) as response:
        assert response.read().decode().strip() == 'certificate smoke test OK', host
    print(host, 'trusted HTTPS OK')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args): return None
opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ctx))
for scheme, port in [('http', 1080), ('https', 1443)]:
    try:
        opener.open(f'{scheme}://redirect.test:{port}/')
        raise AssertionError('missing redirect')
    except urllib.error.HTTPError as response:
        assert response.code == 301
        assert response.headers['Location'] == 'https://project.test/target'
print('redirect HTTP and HTTPS destinations OK')
''')
    docker('exec', UTILITY, '/services-init.py')
    docker('exec', UTILITY, 'python3', '-c', """
import subprocess
from pathlib import Path
import certificates
cert = Path('/webcrate/openssl/demo/fullchain.pem')
subprocess.run(['openssl', 'x509', '-req', '-extensions', 'SAN',
    '-extfile', '/webcrate/openssl/demo/openssl.cnf',
    '-in', '/webcrate/openssl/demo/fullchain.csr', '-CA', '/webcrate/secrets/rootCA.crt',
    '-CAkey', '/webcrate/secrets/rootCA.key', '-CAcreateserial', '-days', '1', '-out', str(cert)], check=True)
assert not certificates.certificate_current(cert.parent)
Path('/webcrate/short-lived-demo.pem').write_bytes(cert.read_bytes())
""")
    docker('exec', UTILITY, '/certbot-renew.py')
    docker('exec', UTILITY, 'python3', '-c', """
from pathlib import Path
import certificates
cert = Path('/webcrate/openssl/demo/fullchain.pem')
assert certificates.certificate_current(cert.parent)
assert cert.read_bytes() != Path('/webcrate/short-lived-demo.pem').read_bytes()
print('scheduled renewal replaced near-expiry project certificate')
""")
    docker('exec', NGINX, 'nginx', '-t', '-c', '/webcrate/nginx-test.conf')
    docker('run', '-d', '--name', CRON, IMAGE)
    docker('exec', CRON, 'pgrep', 'crond')
    print('Docker certificate integration PASSED')
except Exception:
    subprocess.run(['docker', 'logs', NGINX])
    subprocess.run(['docker', 'logs', CRON])
    raise
finally:
    for name in (CRON, NGINX, UTILITY):
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['docker', 'volume', 'rm', PREFIX], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['docker', 'network', 'rm', PREFIX], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
