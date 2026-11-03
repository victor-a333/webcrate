#!/usr/bin/env python3
"""Validate and atomically replace the complete, virtual-only FTP account set."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import sys
import tempfile

import yaml

NAME = re.compile(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,63}\Z')
HASH = re.compile(r'\$(?:[156]|2[aby]|y)\$[^:\s\x00]+\Z')


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value) or value == 'root':
        raise ValueError('Invalid or reserved FTP account/project name')
    return value


def relative_home(value):
    if value is None:
        value = ''
    if not isinstance(value, str) or any(c in value for c in '\x00\r\n:'):
        raise ValueError('Invalid FTP home')
    parts = value.split('/') if value else []
    if any(p in ('', '.', '..') for p in parts) or value.startswith('/'):
        raise ValueError('FTP home must be a relative path without traversal')
    return parts


def directory(root, parts, uid, gid, create=False):
    """Walk using directory descriptors; never follow project/home symlinks."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    return
                os.mkdir(part, 0o755, dir_fd=fd)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.fchown(child, uid, gid)
            os.close(fd)
            fd = child
    finally:
        os.close(fd)


def render(projects, uid, gid, root_count):
    if not isinstance(projects, dict):
        raise ValueError('Projects must be a mapping')
    accounts = {}
    directories = []
    for project_name, project in projects.items():
        project_name = name(project_name)
        if not isinstance(project, dict):
            raise ValueError('Project must be a mapping')
        volume = project.get('volume', 0)
        volume = 0 if volume is None else volume
        if type(volume) is not int or not 0 <= volume < root_count:
            raise ValueError('Project volume is outside the mounted roots')
        root = f'/projects{volume + 1 if volume else ""}'
        virtual = project.get('ftps') or []
        if isinstance(virtual, dict):
            virtual = list(virtual.values())
        if not isinstance(virtual, list):
            raise ValueError('FTP accounts must be a list or mapping')
        entries = [dict(name=project_name, password=project.get('password'), home='')] + virtual
        for account in entries:
            if not isinstance(account, dict):
                raise ValueError('FTP account must be a mapping')
            username = name(account.get('name'))
            if username in accounts:
                raise ValueError(f'Duplicate FTP account: {username}')
            password = account.get('password')
            if not isinstance(password, str) or not HASH.fullmatch(password):
                raise ValueError(f'Invalid password hash for {username}')
            parts = [project_name] + relative_home(account.get('home', ''))
            directory(root, parts, uid, gid)
            home = root + '/' + '/'.join(parts)
            accounts[username] = f'{username}:{password}:{uid}:{gid}::{home}:/bin/false\n'
            directories.append((root, parts))
    return ''.join(accounts[key] for key in sorted(accounts)), directories


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stdin', action='store_true')
    args = parser.parse_args()
    uid = int(os.environ.get('WEBCRATE_UID', '1000'))
    gid = int(os.environ.get('WEBCRATE_GID', '1000'))
    if uid <= 0 or gid <= 0:
        raise ValueError('FTP UID and GID must be non-root')
    root_count = int(os.environ.get('WEBCRATE_FTP_ROOT_COUNT', '1'))
    with open('/run/proftpd/accounts.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.stdin:
            projects = yaml.safe_load(sys.stdin)
        else:
            with open('/webcrate/projects.yml') as source:
                projects = yaml.safe_load(source)
        content, directories = render({} if projects is None else projects, uid, gid, root_count)
        target = Path('/etc/ftp.passwd')
        if target.exists() and target.read_text() == content:
            print('unchanged')
            return
        for root, parts in directories:
            directory(root, parts, uid, gid, create=True)
        fd, temporary = tempfile.mkstemp(prefix='.ftp-', dir=target.parent)
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print('changed')


if __name__ == '__main__':
    main()
