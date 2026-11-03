#!/usr/bin/env python3
"""Synchronize authoritative project accounts; revoke existing sessions on change."""
import fcntl
import os
from pathlib import Path
import subprocess


def sync():
    container = os.environ.get("WEBCRATE_FTP_CONTAINER", "webcrate-ftp")
    # Serialize CLI/admin syncs and read the current authoritative file under lock.
    with open('/webcrate/meta/ftp-sync.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = subprocess.run(['docker', 'container', 'ls', '-a',
                                '--filter', f'name=^/{container}$', '--format', '{{.State}}'],
                               capture_output=True, text=True, check=True)
        if not state.stdout.strip():
            # Initial installation: the FTP entrypoint will load accounts at startup.
            print('FTP container absent; accounts will load on startup')
            return
        if state.stdout.strip() != 'running':
            raise RuntimeError('FTP container is stopped; cannot synchronize accounts')
        result = subprocess.run(['docker', 'exec', '-i', container,
                                 '/webcrate/parse-projects.py', '--stdin'],
                                input=Path('/webcrate/projects.yml').read_bytes(),
                                capture_output=True, check=True)
        if result.stdout.strip() == b'changed':
            # SIGHUP does not revoke authenticated sessions. Restart only on change.
            subprocess.run(['docker', 'restart', '--time', '10', container], check=True)
        print(result.stdout.decode().strip())


if __name__ == '__main__':
    sync()
