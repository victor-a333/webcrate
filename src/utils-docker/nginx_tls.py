"""Render and deploy Nginx TLS configuration with validation and rollback."""

from pathlib import Path
import os
import re
import subprocess


def reload_nginx():
    command = ['docker', 'exec', os.environ.get('WEBCRATE_NGINX_CONTAINER', 'webcrate-nginx'), 'nginx']
    config = os.environ.get('WEBCRATE_NGINX_CONFIG')
    if config:
        command += ['-c', config]
    subprocess.run(command + ['-t'], check=True)
    subprocess.run(command + ['-s', 'reload'], check=True)


def nginx_version():
    """Use the host-detected version, or inspect Docker for runtime entry points."""
    supplied = os.environ.get('WEBCRATE_NGINX_VERSION')
    if supplied is not None:
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', supplied)
        # An explicit unknown value prevents pointless Docker calls in generators.
        return tuple(map(int, match.groups())) if match else None
    container = os.environ.get('WEBCRATE_NGINX_CONTAINER', 'webcrate-nginx')
    try:
        result = subprocess.run(['docker', 'exec', container, 'nginx', '-v'],
                                capture_output=True, text=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        try:
            # Configuration generation also runs before Nginx is started.
            image = subprocess.run(['docker', 'inspect', '--format', '{{.Image}}', container],
                                   capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            image = 'ace5040/webcrate-nginx:stable'
        try:
            result = subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                                     '--entrypoint', 'nginx', image, '-v'],
                                    capture_output=True, text=True, check=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None
    match = re.search(r'nginx/(\d+)\.(\d+)\.(\d+)', result.stdout + result.stderr)
    return tuple(map(int, match.groups())) if match else None


def tls_listen():
    version = nginx_version()
    if version is not None and version >= (1, 25, 1):
        return 'listen 1443 ssl;\nhttp2 on;'
    # This syntax remains compatible when version detection is unavailable.
    return 'listen 1443 ssl http2;'


def render(name, mode, template='ssl.conf', root=Path('/webcrate')):
    directory = root / ('letsencrypt/live' if mode == 'letsencrypt' else 'openssl') / name
    if not all((directory / part).is_file() for part in ('privkey.pem', 'fullchain.pem')):
        return None
    content = (root / template).read_text().replace('%type%', mode).replace(
        '%path%', ('live/' if mode == 'letsencrypt' else '') + name)
    if '%tls_listen%' in content:
        content = content.replace('%tls_listen%', tls_listen())
    elif 'listen 1443 ssl http2;' in content:
        # Also support templates retained from older utilities images.
        content = content.replace('listen 1443 ssl http2;', tls_listen())
    return content


def write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    try:
        temporary.write_text(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def configure(name, mode, template='ssl.conf', root=Path('/webcrate'), reload=False):
    path = root / 'nginx/ssl' / f'{name}.conf'
    old = path.read_text() if path.exists() else None
    content = render(name, mode, template, root) if mode in ('openssl', 'letsencrypt') else None
    if content == old:
        return False
    if content is None:
        path.unlink(missing_ok=True)
    else:
        write_atomic(path, content)
    if reload:
        try:
            reload_nginx()
        except Exception:
            if old is None:
                path.unlink(missing_ok=True)
            else:
                write_atomic(path, old)
            raise
    return True
