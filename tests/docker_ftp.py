"""Run in the FTP image with disposable volumes at /projects and /projects2."""
import ctypes
import ftplib
import io
import os
from pathlib import Path
import ssl
import subprocess
import time

import yaml

os.environ['WEBCRATE_FTP_ROOT_COUNT'] = '2'
PASSWORD = 'fixture-password'
crypt = ctypes.CDLL('libcrypt.so.1').crypt
crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
crypt.restype = ctypes.c_char_p
password_hash = crypt(PASSWORD.encode(), b'$6$ftpfixture$').decode()
projects = {
    'first': {'password': password_hash, 'ftps': [
        {'name': 'restricted', 'password': password_hash, 'home': 'web'}]},
    'second': {'volume': 1, 'password': password_hash},
}


class ReusingFTP_TLS(ftplib.FTP_TLS):
    """Reuse the authenticated TLS session for data, as ProFTPD requires."""
    def ntransfercmd(self, cmd, rest=None):
        connection, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            connection = self.context.wrap_socket(
                connection, server_hostname=self.host, session=self.sock.session)
        return connection, size


def configure():
    Path('/webcrate/projects.yml').write_text(yaml.safe_dump(projects))


def generate(data):
    return subprocess.run(['/webcrate/parse-projects.py', '--stdin'],
                          input=yaml.safe_dump(data), text=True, capture_output=True)


def start():
    process = subprocess.Popen(['/entrypoint.sh'])
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError(f'FTP exited: {process.returncode}')
        try:
            with ftplib.FTP('127.0.0.1', timeout=1):
                return process
        except OSError:
            time.sleep(.1)
    process.terminate()
    raise RuntimeError('FTP startup timed out')


def stop(process):
    process.terminate()
    process.wait(timeout=10)
    assert process.returncode == 0, process.returncode


def transfer(user, home, tls=False):
    if tls:
        context = ssl.create_default_context(cafile='/webcrate/tls/server.crt')
        context.check_hostname = False  # The generated fixture certificate has a generic CN.
        client = ReusingFTP_TLS(context=context, timeout=5)
        client.connect('127.0.0.1')
    else:
        client = ftplib.FTP('127.0.0.1', timeout=5)
    with client as ftp:
        ftp.login(user, PASSWORD)
        if tls:
            ftp.prot_p()
            assert ftp.sock.version() in ('TLSv1.2', 'TLSv1.3')
        assert ftp.pwd() == '/'
        ftp.storbinary('STOR fixture.txt', io.BytesIO(b'passive transfer'))
        data = bytearray()
        ftp.retrbinary('RETR fixture.txt', data.extend)
        assert data == b'passive transfer'
        assert Path(home, 'fixture.txt').read_bytes() == data
        ftp.cwd('..')
        assert ftp.pwd() == '/'
        try:
            ftp.cwd('/etc')
        except ftplib.error_perm:
            pass
        else:
            raise AssertionError('Account escaped home')
        for command in ('SITE CHMOD 777 fixture.txt', 'SITE CPFR fixture.txt', 'SITE EXEC id'):
            try:
                ftp.sendcmd(command)
            except ftplib.error_perm:
                pass
            else:
                raise AssertionError(f'Unexpected privileged command: {command}')


def denied(user):
    with ftplib.FTP('127.0.0.1', timeout=5) as ftp:
        try:
            ftp.login(user, PASSWORD)
        except ftplib.error_perm:
            return
    raise AssertionError(f'Revoked account authenticated: {user}')


configure()
process = start()
try:
    subprocess.run(['/usr/sbin/proftpd', '--config', '/etc/proftpd/proftpd.conf', '--configtest'], check=True)
    transfer('first', '/projects/first')
    transfer('second', '/projects2/second', tls=True)
    transfer('restricted', '/projects/first/web', tls=True)
    assert 'first:' not in Path('/etc/passwd').read_text()
    baseline = Path('/etc/ftp.passwd').read_bytes()
    for home in ('../second', '/projects2/second', 'web/../../second', 'bad\nfield', 'bad:field'):
        invalid = {'first': {'password': password_hash, 'ftps': [
            {'name': 'bad', 'password': password_hash, 'home': home}]}}
        assert generate(invalid).returncode != 0, home
        assert Path('/etc/ftp.passwd').read_bytes() == baseline
    Path('/projects/first/escape').symlink_to('/projects2/second', target_is_directory=True)
    invalid['first']['ftps'][0]['home'] = 'escape'
    assert generate(invalid).returncode != 0
    assert Path('/etc/ftp.passwd').read_bytes() == baseline
    # Shell metacharacters are inert path characters, never commands.
    invalid['first']['ftps'][0]['home'] = 'web; touch marker'
    assert generate(invalid).returncode == 0
    assert not Path('/marker').exists()
    invalid = {'bad;touch marker': {'password': password_hash}}
    assert generate(invalid).returncode != 0
    assert generate(projects).returncode == 0
finally:
    stop(process)
print('PASS: FTP/FTPS, transfers, confinement, minimal commands, injection/traversal/symlink defenses', flush=True)

# Deletion revokes accounts; inactive projects keep FTP access.
del projects['second']
projects['disabled'] = {'active': False, 'password': password_hash}
projects['added'] = {'volume': 1, 'password': password_hash}
configure()
process = start()
try:
    denied('second')
    transfer('restricted', '/projects/first/web')
    transfer('disabled', '/projects/disabled', tls=True)
    transfer('added', '/projects2/added', tls=True)
finally:
    stop(process)
projects['disabled']['active'] = True
configure()
process = start()
try:
    transfer('restricted', '/projects/first/web')
    transfer('disabled', '/projects/disabled', tls=True)
    unchanged = generate(projects)
    assert unchanged.returncode == 0 and unchanged.stdout.strip() == 'unchanged'
    lines = Path('/etc/ftp.passwd').read_text().splitlines()
    assert len(lines) == 4, lines
finally:
    stop(process)
print('PASS: add/delete accounts, inactive projects retain FTP, unchanged detection, restart without changing mounts')
