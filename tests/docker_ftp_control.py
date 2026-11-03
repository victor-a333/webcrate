"""Run in the utilities test image with Docker socket and repo at /repository.

Creates only uniquely named fixtures; never addresses production containers.
"""
import json
import subprocess
import time
import uuid

import yaml

prefix = 'webcrate-ftp-check-' + uuid.uuid4().hex[:10]
ftp, utils, admin = (prefix + suffix for suffix in ('-ftp', '-utils', '-admin'))
volume = prefix + '-state'
containers = []


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout.strip()


def publish(projects, deleted=False):
    docker('exec', '-i', admin, 'python3', '-c',
           "import sys; from pathlib import Path; Path('/webcrate/updated-projects.yml').write_text(sys.stdin.read())",
           input=yaml.safe_dump(projects))
    if deleted:
        # The delete action requests immediate sync, without running Apply.
        docker('exec', admin, 'python3', '/fixture-updateprojects.py', '--sync-ftp')
    else:
        docker('exec', admin, 'python3', '/fixture-updateprojects.py')
        docker('exec', utils, '/project-config.py', 'inactive', 'reload')
    wait_ready()


def wait_ready():
    for _ in range(100):
        result = subprocess.run(['docker', 'exec', ftp, 'python3', '-c',
            "import ftplib; ftplib.FTP('127.0.0.1',timeout=1).quit()"], capture_output=True)
        if result.returncode == 0:
            return
        time.sleep(.1)
    raise AssertionError('FTP failed to become ready')


def login(user, allowed=True):
    script = """import ftplib, sys
with ftplib.FTP('127.0.0.1',timeout=3) as f:
    try:
        f.login(sys.argv[1], 'fixture-password')
    except ftplib.error_perm:
        assert sys.argv[2] == 'deny'
    else:
        assert sys.argv[2] == 'allow'
"""
    docker('exec', ftp, 'python3', '-c', script, user, 'allow' if allowed else 'deny')


def started():
    return json.loads(docker('inspect', ftp))[0]['State']['StartedAt']


try:
    docker('volume', 'create', volume)
    docker('run', '-d', '--name', utils, '-v', volume + ':/webcrate',
           '-v', '/var/run/docker.sock:/var/run/docker.sock',
           '-e', 'WEBCRATE_FTP_CONTAINER=' + ftp,
           '--entrypoint', 'sleep', 'webcrate-utils-docker:ftp-check', 'infinity')
    containers.append(utils)
    docker('exec', utils, 'mkdir', '-p', '/webcrate/meta/projects', '/webcrate/nginx',
           '/webcrate/php_pools', '/webcrate/dnsmasq')
    # Generate a known hash without passing any real credentials into fixtures.
    password_hash = docker('run', '--rm', '--entrypoint', 'python3', 'webcrate-ftp:trixie-check', '-c',
        "import ctypes; c=ctypes.CDLL('libcrypt.so.1').crypt; c.restype=ctypes.c_char_p; print(c(b'fixture-password',b'$6$fixture$').decode())")
    projects = {'first': {'password': password_hash, 'ftps': [
        {'name': 'restricted', 'password': password_hash, 'home': 'web'}]},
                'inactive': {'active': False, 'password': password_hash}}
    docker('exec', '-i', utils, 'python3', '-c',
           "import sys; from pathlib import Path; Path('/webcrate/projects.yml').write_text(sys.stdin.read())",
           input=yaml.safe_dump(projects))
    # State volume supplies YAML only; project roots use disposable anonymous volumes.
    docker('run', '-d', '--name', ftp, '--security-opt', 'no-new-privileges:true',
           '-v', volume + ':/fixture-state:ro', '-v', '/projects', '-v', '/projects2',
           '-e', 'WEBCRATE_FTP_ROOT_COUNT=2', '--entrypoint', '/bin/sh',
           'webcrate-ftp:trixie-check', '-c',
           'ln -s /fixture-state/projects.yml /webcrate/projects.yml; exec /entrypoint.sh')
    containers.append(ftp)
    docker('run', '-d', '--name', admin, '-v', volume + ':/webcrate',
           '-v', '/var/run/docker.sock:/var/run/docker.sock',
           '-e', 'WEBCRATE_UTILS_CONTAINER=' + utils,
           '--entrypoint', 'sleep', 'ace5040/webcrate-admin:stable', 'infinity')
    containers.append(admin)
    docker('cp', '/repository/src/admin/updateprojects.py', admin + ':/fixture-updateprojects.py')
    wait_ready()
    login('first')
    initial = started()
    publish(projects)
    assert started() == initial, 'Unchanged accounts restarted FTP'
    projects['added'] = {'volume': 1, 'password': password_hash}
    publish(projects)
    assert started() != initial
    login('added')
    projects['first']['active'] = False
    publish(projects)
    login('first')
    login('restricted')
    projects['first']['active'] = True
    publish(projects)
    login('first')
    # Existing sessions must be terminated when credentials/access are revoked.
    client = subprocess.Popen(['docker', 'exec', ftp, 'python3', '-u', '-c',
        "import ftplib,time; f=ftplib.FTP('127.0.0.1'); f.login('added','fixture-password'); print('ready',flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert client.stdout.readline().strip() == 'ready'
    del projects['added']
    publish(projects, deleted=True)
    client.wait(timeout=10)
    assert client.returncode != 0, 'Existing session survived container restart'
    login('added', False)
    login('restricted')
    # A local Unix account must never act as a fallback.
    docker('exec', ftp, 'useradd', '-d', '/projects/first', 'stale')
    docker('exec', ftp, 'usermod', '-p', password_hash, 'stale')
    login('stale', False)
    print('PASS: admin Apply/delete -> docker-utils -> FTP; add/delete, inactive projects retain FTP, unchanged no-op, session revocation, Unix fallback denied')
finally:
    for container in reversed(containers):
        subprocess.run(['docker', 'rm', '-fv', container], capture_output=True)
    subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)

