"""Render and deploy Nginx TLS configuration with validation and rollback."""

from pathlib import Path
import os
import subprocess


def reload_nginx():
    command = ['docker', 'exec', os.environ.get('WEBCRATE_NGINX_CONTAINER', 'webcrate-nginx'), 'nginx']
    config = os.environ.get('WEBCRATE_NGINX_CONFIG')
    if config:
        command += ['-c', config]
    subprocess.run(command + ['-t'], check=True)
    subprocess.run(command + ['-s', 'reload'], check=True)


def render(name, mode, template='ssl.conf', root=Path('/webcrate')):
    directory = root / ('letsencrypt/live' if mode == 'letsencrypt' else 'openssl') / name
    if not all((directory / part).is_file() for part in ('privkey.pem', 'fullchain.pem')):
        return None
    return (root / template).read_text().replace('%type%', mode).replace(
        '%path%', ('live/' if mode == 'letsencrypt' else '') + name)


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
