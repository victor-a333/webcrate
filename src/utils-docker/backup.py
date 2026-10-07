#!/usr/bin/env python3

import os
import subprocess
import tempfile
import yaml
import sys
from datetime import datetime
from munch import munchify
from urllib.parse import unquote, urlparse
import helpers
from log import log

log = log('/webcrate/log/app.log')
log.write(f'Starting backup process')

with open('/webcrate/projects.yml', 'r') as f:
  projects = munchify(yaml.safe_load(f))
  f.close()

with open('/webcrate/services.yml', 'r') as f:
  services = munchify(yaml.safe_load(f))
  f.close()

WEBCRATE_UID = os.environ.get('WEBCRATE_UID', '1000')
WEBCRATE_GID = os.environ.get('WEBCRATE_GID', '1000')
WEBCRATE_FULL_BACKUP_DAYS = os.environ.get('WEBCRATE_FULL_BACKUP_DAYS', '7')
WEBCRATE_MAX_FULL_BACKUPS = os.environ.get('WEBCRATE_MAX_FULL_BACKUPS', '10')
WEBCRATE_BACKUP_URIS = os.environ.get('WEBCRATE_BACKUP_URIS', 'file:///webcrate/backup')
BACKUP_BACKEND = os.environ.get('WEBCRATE_BACKUP_BACKEND', 'duplicity').lower()
BACKUP_URIS = WEBCRATE_BACKUP_URIS.split('^')
WEBCRATE_BACKUP_FILE_PATHS = (
  'config',
  'var/crontabs',
  'var/letsencrypt',
  'var/letsencrypt-meta',
  'var/openssl',
  'var/secrets',
  'var/ssh',
  '.env',
  'projects.yml',
  'redirects.yml',
  'services.yml',
)
PROJECT_NAME = sys.argv[1] if len(sys.argv) > 1 else 'all'
BACKUP_TYPE = sys.argv[2] if len(sys.argv) > 2 else 'all'

if BACKUP_BACKEND not in ('borg', 'duplicity'):
  raise ValueError(f'Unsupported backup backend: {BACKUP_BACKEND}')

BACKUP_ERRORS = []

def record_backup_error(backup_type, repository, error):
  message = f'Backup failed: type={backup_type}, repository={repository}, error={error}'
  BACKUP_ERRORS.append(message)
  log.write(message)
  print(message, file=sys.stderr)

def get_borg_repository(backup_uri, destination):
  if backup_uri.lower().startswith('ftp://'):
    message = f'Skip unsupported Borg FTP backup URI: {backup_uri}'
    log.write(message)
    print(message)
    return None

  repository_uri = f'{backup_uri.rstrip("/")}/{destination}'
  if repository_uri.startswith('file://'):
    parsed_uri = urlparse(repository_uri)
    repository = unquote(parsed_uri.path)
    os.makedirs(os.path.dirname(repository), exist_ok=True)
    return repository

  return repository_uri

def get_borg_environment():
  environment = os.environ.copy()
  environment['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'
  environment['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
  return environment

def initialize_borg_repository(repository):
  environment = get_borg_environment()
  result = subprocess.run(
    ['borg', 'info', repository],
    env=environment,
    text=True,
    capture_output=True,
  )
  if result.returncode == 0:
    return

  if os.path.exists(repository):
    raise RuntimeError(f'Could not access existing Borg repository {repository}: {result.stderr.strip()}')

  init_result = subprocess.run(
    ['borg', 'init', '--encryption=none', '--make-parent-dirs', repository],
    env=environment,
    text=True,
    capture_output=True,
  )
  if init_result.returncode != 0:
    error = init_result.stderr.strip() or init_result.stdout.strip()
    raise RuntimeError(f'Could not initialize Borg repository {repository}: {error}')

def get_borg_archive_retention(full_backup_days, max_full_backups):
  return int(full_backup_days) * int(max_full_backups)

def prune_borg_repository(repository, full_backup_days, max_full_backups):
  archive_retention = get_borg_archive_retention(full_backup_days, max_full_backups)
  subprocess.run(
    ['borg', 'prune', '--list', '--keep-last', str(archive_retention), repository],
    env=get_borg_environment(),
    check=True,
  )

def borg_archive_name(backup_type):
  return f'{backup_type}-{datetime.now().strftime("%Y-%m-%dT%H-%M-%S")}'

def borg_pattern_path(path):
  return path.replace('\\', '/').lstrip('/')

def backend_destination(backup_backend, destination):
  return f'{backup_backend}/{destination.lstrip("/")}'

def clear_database_backup_tmp():
  os.system(f'mkdir -p /webcrate/backup-tmp')
  if os.path.isdir(f'/webcrate/backup-tmp') and os.listdir(f'/webcrate/backup-tmp'):
    os.system(f'rm /webcrate/backup-tmp/*')

def read_database_password(password_file):
  password_path = f'/webcrate/secrets/{password_file}'
  with open(password_path, 'r') as f:
    for line in f:
      key, separator, value = line.strip().partition('=')
      if separator and key == 'password':
        return value.strip('"')
  raise ValueError(f'Password not found in {password_path}')

def store_database_backup(destination, backup_uris, full_backup_days, max_full_backups):
  destination = backend_destination('duplicity', destination)
  for backup_uri in backup_uris:
    os.system(f'duplicity --verbosity notice '
      f'--no-encryption '
      f'--full-if-older-than {full_backup_days}D '
      f'--num-retries 3 '
      f'--volsize 5000 '
      f'--archive-dir /webcrate/duplicity/.duplicity '
      f'--log-file /webcrate/duplicity/duplicity.log '
      f'"/webcrate/backup-tmp" '
      f'"{backup_uri}/{destination}"'
    )
    sys.stdout.flush()
    os.system(f'duplicity --verbosity notice '
      f'--archive-dir /webcrate/duplicity/.duplicity '
      f'--log-file /webcrate/duplicity/duplicity.log '
      f'--force '
      f'remove-all-but-n-full {max_full_backups} '
      f'"{backup_uri}/{destination}"'
    )
    sys.stdout.flush()

def store_borg_database_backup(destination, backup_uris, full_backup_days, max_full_backups, dump_command, database_filename, dump_environment=None):
  destination = backend_destination('borg', destination)
  for backup_uri in backup_uris:
    repository = f'{backup_uri.rstrip("/")}/{destination}'
    try:
      repository = get_borg_repository(backup_uri, destination)
      if not repository:
        continue

      initialize_borg_repository(repository)
      with tempfile.TemporaryFile() as dump_file:
        subprocess.run(
          dump_command,
          stdout=dump_file,
          env=dump_environment,
          check=True,
        )
        dump_file.seek(0)
        subprocess.run(
          [
            'borg', 'create', '--stats',
            '--stdin-name', database_filename,
            f'{repository}::{borg_archive_name("database")}',
            '-',
          ],
          stdin=dump_file,
          env=get_borg_environment(),
          check=True,
        )
      prune_borg_repository(repository, full_backup_days, max_full_backups)
    except Exception as error:
      record_backup_error('database', repository, error)

def store_files_backup(source, destination, backup_uris, full_backup_days, max_full_backups, filters, backup_backend):
  destination = backend_destination(backup_backend, destination)
  for mode, path in filters:
    if mode not in ('include', 'exclude'):
      raise ValueError(f'Unsupported backup filter mode: {mode}')

  for backup_uri in backup_uris:
    if backup_backend == 'borg':
      repository = f'{backup_uri.rstrip("/")}/{destination}'
      try:
        repository = get_borg_repository(backup_uri, destination)
        if not repository:
          continue
        initialize_borg_repository(repository)
        borg_command = ['borg', 'create', '--stats']
        for mode, path in filters:
          prefix = '+' if mode == 'include' else '-'
          borg_command.append(f'--pattern={prefix}sh:{borg_pattern_path(path)}')
        borg_command.extend([f'{repository}::{borg_archive_name("files")}', source])
        subprocess.run(borg_command, env=get_borg_environment(), check=True)
        prune_borg_repository(repository, full_backup_days, max_full_backups)
      except Exception as error:
        record_backup_error('files', repository, error)
    else:
      duplicity_filters = ''.join(f'--{mode} "{path}" ' for mode, path in filters)
      os.system(f'duplicity --verbosity notice '
        f'--no-encryption '
        f'--full-if-older-than {full_backup_days}D '
        f'--num-retries 3 '
        f'--allow-source-mismatch '
        f'--volsize 5000 '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'{duplicity_filters}'
        f'"{source}" '
        f'"{backup_uri}/{destination}"'
      )
      sys.stdout.flush()
      os.system(f'duplicity --verbosity notice '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'--force '
        f'remove-all-but-n-full {max_full_backups} '
        f'"{backup_uri}/{destination}"'
      )
      sys.stdout.flush()

def backup_webcrate_files(data_folder, included_paths, backup_uris, full_backup_days, max_full_backups, backup_backend):
  filters = [('include', f'{data_folder}/{path}') for path in included_paths]
  filters.append(('exclude', '**'))
  store_files_backup(data_folder, 'webcrate/files', backup_uris, full_backup_days, max_full_backups, filters, backup_backend)

def backup_mysql_database(name, host, password, destination, database_type, backup_uris, full_backup_days, max_full_backups, backup_backend):
  log.write(f'Backup {database_type} db {name} from {host}')
  print(f'=========================================')
  print(f'backup {database_type} db for {name}')
  print(f'=========================================')
  sys.stdout.flush()
  dump_command = ['mariadb-dump', '--skip-ssl', '--single-transaction', '--max_allowed_packet=64M', '-h', host, '-u', 'root', name]
  dump_environment = os.environ.copy()
  dump_environment['MYSQL_PWD'] = password
  if backup_backend == 'borg':
    store_borg_database_backup(destination, backup_uris, full_backup_days, max_full_backups, dump_command, f'{name}.sql', dump_environment)
  else:
    clear_database_backup_tmp()
    with open(f'/webcrate/backup-tmp/{name}.sql', 'wb') as dump_file:
      subprocess.run(dump_command, stdout=dump_file, env=dump_environment, check=True)
    store_database_backup(destination, backup_uris, full_backup_days, max_full_backups)
    clear_database_backup_tmp()

def backup_postgresql_database(name, host, password, destination, backup_uris, full_backup_days, max_full_backups, backup_backend):
  log.write(f'Backup postgresql db {name} from {host}')
  print(f'=========================================')
  print(f'backup postgresql db for {name}')
  print(f'=========================================')
  sys.stdout.flush()
  dump_command = ['pg_dump', '-U', 'postgres', '-h', host, name]
  dump_environment = os.environ.copy()
  dump_environment['PGPASSWORD'] = password
  if backup_backend == 'borg':
    store_borg_database_backup(destination, backup_uris, full_backup_days, max_full_backups, dump_command, f'{name}.pgsql', dump_environment)
  else:
    clear_database_backup_tmp()
    with open(f'/webcrate/backup-tmp/{name}.pgsql', 'wb') as dump_file:
      subprocess.run(dump_command, stdout=dump_file, env=dump_environment, check=True)
    store_database_backup(destination, backup_uris, full_backup_days, max_full_backups)
    clear_database_backup_tmp()

#backup files for webcrate
if PROJECT_NAME == 'admin' or PROJECT_NAME == 'all':
  if ( BACKUP_TYPE == 'files' or BACKUP_TYPE == 'all' ):
    log.write(f'Backup webcrate files')
    data_folder = f'/webcrate-readonly'
    print(f'=========================================')
    print(f'backup files webcrate-admin')
    print(f'=========================================')
    sys.stdout.flush()
    backup_webcrate_files(data_folder, WEBCRATE_BACKUP_FILE_PATHS, BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, BACKUP_BACKEND)

for servicename,service in services.items():
  service.name = servicename
  if PROJECT_NAME == service.name or PROJECT_NAME == 'all':
    if service.mysql_db and ( BACKUP_TYPE == 'mysql' or BACKUP_TYPE == 'all' ):
      password = read_database_password('mysql.cnf')
      backup_mysql_database(service.name, f'webcrate-{service.name}-mysql', password, f'services/{service.name}/mysql', 'mysql', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, BACKUP_BACKEND)

for projectname,project in projects.items():
  project.name = projectname
  if project.backup and project.active and ( PROJECT_NAME == projectname or PROJECT_NAME == 'all' ):

    #backup files
    if ( BACKUP_TYPE == 'files' or BACKUP_TYPE == 'all' ):
      print(f'=========================================')
      print(f'backup files for project {project.name}')
      print(f'=========================================')
      sys.stdout.flush()
      if hasattr(project, 'volume'):
        project.folder = f'/projects{(project.volume + 1) if project.volume else ""}/{project.name}'
      else:
        project.folder = f'/projects/{project.name}'
      log.write(f'Backup files for project {project.name}')
      data_folder = f'{project.folder}/{project.root_folder.split("/")[0]}'
      filters = []
      if hasattr(project, 'duplicity_filters'):
        for duplicity_filter in project.duplicity_filters:
          filters.append((duplicity_filter.mode, f'{data_folder}/{duplicity_filter.path}'))
      if os.path.isdir(f'{data_folder}'):
        store_files_backup(data_folder, f'projects/{project.name}/files', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, filters, BACKUP_BACKEND)
      #backup solr cores
      log.write(f'Backup solr cores for project {project.name}')
      if os.path.isdir(f'{project.folder}/var/solr/cores'):
        solr_folder = f'{project.folder}/var/solr/cores'
        filters = [('exclude', f'{solr_folder}/**/data')]
        store_files_backup(solr_folder, f'projects/{project.name}/solr-cores', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, filters, BACKUP_BACKEND)

    #connect to project network
    if not helpers.is_network_has_connection(f'webcrate_network_{project.name}', 'webcrate-utils-docker'):
      os.system(f'docker network connect webcrate_network_{project.name} webcrate-utils-docker')

    #backup project mysql
    if project.mysql_db and ( BACKUP_TYPE == 'mysql' or BACKUP_TYPE == 'all' ):
      password = read_database_password('mysql.cnf')
      backup_mysql_database(project.name, f'webcrate-{project.name}-mysql', password, f'projects/{project.name}/project-mysql', 'mysql', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, BACKUP_BACKEND)


    #backup project mysql5
    if project.mysql5_db and ( BACKUP_TYPE == 'mysql5' or BACKUP_TYPE == 'all' ):
      password = read_database_password('mysql5.cnf')
      backup_mysql_database(project.name, f'webcrate-{project.name}-mysql5', password, f'projects/{project.name}/project-mysql5', 'mysql5', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, BACKUP_BACKEND)

    #backup project postgresql
    if project.postgresql_db and ( BACKUP_TYPE == 'postgresql' or BACKUP_TYPE == 'all' ):
      password = read_database_password('postgres.cnf')
      backup_postgresql_database(project.name, f'webcrate-{project.name}-postgresql', password, f'projects/{project.name}/project-postgresql', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, BACKUP_BACKEND)
    #disconnect from project network
    os.system(f'docker network disconnect webcrate_network_{project.name} webcrate-utils-docker')

os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/backup')
os.system(f'chmod -R a-rw,u+rw /webcrate/backup')
os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/duplicity')
if BACKUP_ERRORS:
  summary = f'Backup process ended with {len(BACKUP_ERRORS)} error(s)'
  log.write(summary)
  print(summary, file=sys.stderr)
  sys.stderr.flush()
else:
  log.write(f'Backup process ended successfully')
sys.stdout.flush()
