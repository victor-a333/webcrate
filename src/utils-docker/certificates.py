"""Shared certificate lifecycle for services, projects, and redirects."""

import os
from pathlib import Path
import subprocess
import fcntl
from contextlib import contextmanager
import nginx_tls


@contextmanager
def locked(root=Path('/webcrate')):
    (root / 'letsencrypt-meta').mkdir(parents=True, exist_ok=True)
    with (root / 'letsencrypt-meta/certificates.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def certificate_current(directory, days=30):
    if not all((directory / part).is_file() for part in ('privkey.pem', 'fullchain.pem')):
        return False
    return subprocess.run(['openssl', 'x509', '-checkend', str(days * 86400),
                           '-noout', '-in', str(directory / 'fullchain.pem')],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def initialize(target, root=Path('/webcrate'), template='ssl.conf'):
    with locked(root):
        return _initialize(target, root, template)


def _initialize(service, root, template):
    name = service.name
    if service.https == 'disabled':
        return nginx_tls.configure(name, 'disabled', template, root, reload=True)
    if service.https not in ('letsencrypt', 'openssl'):
        raise ValueError(f'Unsupported HTTPS mode: {service.https}')

    cert_path = ('letsencrypt/live/' if service.https == 'letsencrypt' else 'openssl/') + name
    cert_dir = root / cert_path
    has_certificate = certificate_current(cert_dir)
    renewed = False
    if service.https == 'letsencrypt':
        domains = sorted(set(getattr(service, 'domains', [getattr(service, 'domain', '')])))
        domains = [domain for domain in domains if domain and domain.split('.')[-1].lower() != 'test']
        domain = ','.join(domains)
        if not domains:
            print(f'{name} - skipping Let\'s Encrypt for .test domain')
            return
        metadata = root / 'letsencrypt-meta' / f'domains-{name}.txt'
        previous_domains = metadata.read_text() if metadata.exists() else ''
        if not has_certificate or previous_domains != domain:
            challenge = root / 'letsencrypt-meta' / 'well-known' / name
            challenge.mkdir(parents=True, exist_ok=True)
            # Load the generated HTTP virtual host before the ACME challenge.
            nginx_tls.reload_nginx()
            subprocess.run([
                'certbot', 'certonly', '--non-interactive', '--key-type', 'ecdsa',
                '--keep-until-expiring', '--renew-with-new-domains',
                '--config-dir', str(root / 'letsencrypt'), '--cert-name', name,
                '--webroot', '--webroot-path', str(challenge), '-d', domain,
            ], check=True)
            if not all((cert_dir / part).is_file() for part in ('privkey.pem', 'fullchain.pem')):
                raise RuntimeError(f'{name} - certificate files missing after issuance')
            metadata.write_text(domain)
            renewed = True
    else:
        renewed = _issue_local(service, root)

    if not all((cert_dir / filename).is_file() for filename in ('privkey.pem', 'fullchain.pem')):
        raise RuntimeError(f'{name} - certificate files missing after issuance')
    # Nginx runs as WEBCRATE_UID and must be able to read private keys.
    owner = f"{os.environ.get('WEBCRATE_UID', '1000')}:{os.environ.get('WEBCRATE_GID', '1000')}"
    subprocess.run(['chown', '-R', owner, str(root / service.https)], check=True)
    changed = nginx_tls.configure(name, service.https, template, root, reload=True)
    if renewed and not changed:
        nginx_tls.reload_nginx()
    print(f'{name} - SSL configuration installed')
    return changed


def initialize_account(root=Path('/webcrate')):
    """Register/update the ACME account without deleting certificate lineages."""
    import yaml
    import service_settings
    wanted = False
    for filename in ('projects.yml', 'services.yml', 'redirects.yml'):
        path = root / filename
        if not path.exists():
            continue
        for name, target in (yaml.safe_load(path.read_text()) or {}).items():
            if target.get('https') == 'letsencrypt' and target.get('active', True):
                if filename != 'services.yml' or service_settings.enabled(name):
                    wanted = True
    if not wanted:
        return False
    with locked(root):
        email = os.environ.get('WEBCRATE_ADMIN_EMAIL', '')
        metadata = root / 'letsencrypt-meta/letsencrypt-email.txt'
        accounts = root / 'letsencrypt/accounts/acme-v02.api.letsencrypt.org/directory'
        registered = accounts.is_dir() and any(accounts.iterdir())
        if registered and metadata.exists() and metadata.read_text() == email:
            return False
        command = 'update_account' if registered else 'register'
        subprocess.run(['certbot', command, '--non-interactive', '--config-dir',
                        str(root / 'letsencrypt'), '--agree-tos', '--email', email], check=True)
        metadata.write_text(email)
    return True


def renew(root=Path('/webcrate')):
    """Renew saved ACME lineages and local certificates nearing expiry."""
    import yaml
    import service_settings
    from types import SimpleNamespace
    with locked(root):
        renewal = root / 'letsencrypt/renewal'
        lineages = list(renewal.glob('*.conf')) if renewal.exists() else []
        for lineage in lineages:
            # Repair webroots removed by older project/redirect startup scripts.
            (root / 'letsencrypt-meta/well-known' / lineage.stem).mkdir(parents=True, exist_ok=True)
        if lineages:
            subprocess.run(['certbot', 'renew', '--non-interactive', '--config-dir',
                            str(root / 'letsencrypt'), '--deploy-hook', '/certbot-renew-deploy.py'], check=True)
    targets = []
    for filename in ('projects.yml', 'services.yml', 'redirects.yml'):
        path = root / filename
        if not path.exists():
            continue
        for name, config in (yaml.safe_load(path.read_text()) or {}).items():
            if config.get('https') != 'openssl' or not config.get('active', True):
                continue
            if filename == 'services.yml' and not service_settings.enabled(name):
                continue
            config['name'] = f'redirect-{name}' if filename == 'redirects.yml' else name
            template = 'redirect-ssl.conf' if filename == 'redirects.yml' else 'ssl.conf'
            targets.append((SimpleNamespace(**config), template))
    if targets or (root / 'secrets/rootCA.key').exists():
        if init_openssl_root_conf(root):
            nginx_tls.reload_nginx()
    for target, template in targets:
        initialize(target, root, template)


def load_openssl_conf(name):
  conf_old = ''
  if os.path.isfile(f'/webcrate/openssl/{name}/openssl.cnf'):
    with open(f'/webcrate/openssl/{name}/openssl.cnf', 'r') as f:
      conf_old = f.read()
      f.close()
  return conf_old


def load_domains(name):
  domains = ''
  if os.path.isfile(f'/webcrate/letsencrypt-meta/domains-{name}.txt'):
    with open(f'/webcrate/letsencrypt-meta/domains-{name}.txt', 'r') as f:
      domains = f.read()
      f.close()
  return domains


def genereate_openssl_conf(name, domains):
  countryName = os.environ.get('WEBCRATE_countryName', '')
  organizationName = os.environ.get('WEBCRATE_organizationName', '')
  OPENSSL_EMAIL = os.environ.get('WEBCRATE_ADMIN_EMAIL', '')
  return (f'[req]\n'
    f'distinguished_name = dn\n'
    f'prompt = no\n'
    f'req_extensions = SAN\n'
    f'[dn]\n'
    f'C={countryName}\n'
    f'O={organizationName}\n'
    f'emailAddress={OPENSSL_EMAIL}\n'
    f'CN = {name}\n'
    f'[SAN]\n'
    f'subjectAltName = DNS:{",DNS:".join(domains)}\n')


def genereate_openssl_root_conf():
  countryName = os.environ.get('WEBCRATE_countryName', '')
  OPENSSL_EMAIL = os.environ.get('WEBCRATE_ADMIN_EMAIL', '')
  return (f'[req]\n'
    f'distinguished_name = dn\n'
    f'prompt = no\n'
    f'x509_extensions = x509_ext\n'
    f'[dn]\n'
    f'C={countryName}\n'
    f'O=Webcrate\n'
    f'emailAddress={OPENSSL_EMAIL}\n'
    f'CN = Webcrate\n'
    f'[ x509_ext ]\n'
    f'subjectKeyIdentifier = hash\n'
    f'authorityKeyIdentifier = keyid:always,issuer\n'
    f'basicConstraints = critical, CA:TRUE\n'
    f'keyUsage = critical, digitalSignature, keyEncipherment, cRLSign, keyCertSign\n'
    f'extendedKeyUsage = serverAuth\n')



def init_openssl_root_conf(root=Path('/webcrate')):
    """Maintain the local CA without deleting issued certificates."""
    with locked(root):
        secrets = root / 'secrets'
        secrets.mkdir(parents=True, exist_ok=True)
        config = secrets / 'openssl-root.cnf'
        key = secrets / 'rootCA.key'
        cert = secrets / 'rootCA.crt'
        content = genereate_openssl_root_conf()
        changed = not config.exists() or config.read_text() != content
        config.write_text(content)
        if not key.exists():
            subprocess.run(['openssl', 'genrsa', '-out', str(key), '4096'], check=True)
        valid = cert.exists() and subprocess.run(
            ['openssl', 'x509', '-checkend', str(30 * 86400), '-noout', '-in', str(cert)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if changed or not valid:
            temporary = secrets / 'rootCA.next.crt'
            subprocess.run(['openssl', 'req', '-x509', '-new', '-key', str(key), '-sha256',
                            '-days', '825', '-out', str(temporary), '-config', str(config)], check=True)
            temporary.replace(cert)
    target = type('Target', (), {'name': 'default', 'domains': ['default'], 'https': 'openssl'})()
    # The default certificate must exist before Nginx can start; do not reload here.
    with locked(root):
        default_changed = _issue_local(target, root)
    return changed or not valid or default_changed


def _issue_local(target, root):
    import tempfile
    directory = root / 'openssl' / target.name
    config = genereate_openssl_conf(target.name, getattr(target, 'domains', [getattr(target, 'domain', '')]))
    config_path = directory / 'openssl.cnf'
    valid = certificate_current(directory)
    if valid:
        valid = subprocess.run(['openssl', 'verify', '-CAfile', str(root / 'secrets/rootCA.crt'),
                                str(directory / 'fullchain.pem')], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL).returncode == 0
    if valid and config_path.exists() and config_path.read_text() == config:
        return False
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory.parent) as temporary:
        stage = Path(temporary)
        (stage / 'openssl.cnf').write_text(config)
        subprocess.run(['openssl', 'genrsa', '-out', str(stage / 'privkey.pem'), '2048'], check=True)
        subprocess.run(['openssl', 'req', '-new', '-sha256', '-key', str(stage / 'privkey.pem'),
                        '-out', str(stage / 'fullchain.csr'), '-config', str(stage / 'openssl.cnf')], check=True)
        subprocess.run(['openssl', 'x509', '-req', '-extensions', 'SAN', '-extfile', str(stage / 'openssl.cnf'),
                        '-in', str(stage / 'fullchain.csr'), '-CA', str(root / 'secrets/rootCA.crt'),
                        '-CAkey', str(root / 'secrets/rootCA.key'), '-CAcreateserial',
                        '-out', str(stage / 'fullchain.pem'), '-days', '365', '-sha256'], check=True)
        owner = f"{os.environ.get('WEBCRATE_UID', '1000')}:{os.environ.get('WEBCRATE_GID', '1000')}"
        subprocess.run(['chown', '-R', owner, str(stage)], check=True)
        directory.mkdir(parents=True, exist_ok=True)
        for source in stage.iterdir():
            source.replace(directory / source.name)
    return True
