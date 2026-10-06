#!/usr/bin/env python3

import os
import yaml
import sys
from munch import munchify
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
        return value.strip('"').replace('$', '\$')
  raise ValueError(f'Password not found in {password_path}')

def store_database_backup(destination, backup_uris, full_backup_days, max_full_backups):
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

def store_files_backup(source, destination, backup_uris, full_backup_days, max_full_backups, filters=''):
  for backup_uri in backup_uris:
    os.system(f'duplicity --verbosity notice '
      f'--no-encryption '
      f'--full-if-older-than {full_backup_days}D '
      f'--num-retries 3 '
      f'--allow-source-mismatch '
      f'--volsize 5000 '
      f'--archive-dir /webcrate/duplicity/.duplicity '
      f'--log-file /webcrate/duplicity/duplicity.log '
      f'{filters}'
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

def backup_webcrate_files(data_folder, included_paths, backup_uris, full_backup_days, max_full_backups):
  filters = ''.join(f'--include "{data_folder}/{path}" ' for path in included_paths)
  filters += '--exclude "**" '
  store_files_backup(data_folder, 'webcrate/files', backup_uris, full_backup_days, max_full_backups, filters)

def backup_mysql_database(name, host, password, destination, database_type, backup_uris, full_backup_days, max_full_backups):
  log.write(f'Backup {database_type} db {name} from {host}')
  print(f'=========================================')
  print(f'backup {database_type} db for {name}')
  print(f'=========================================')
  sys.stdout.flush()
  clear_database_backup_tmp()
  os.system(f'mysqldump --single-transaction --max_allowed_packet=64M -h {host} -u root -p"{password}" --result-file "/webcrate/backup-tmp/{name}.sql" "{name}"')
  store_database_backup(destination, backup_uris, full_backup_days, max_full_backups)
  clear_database_backup_tmp()

def backup_postgresql_database(name, host, password, destination, backup_uris, full_backup_days, max_full_backups):
  log.write(f'Backup postgresql db {name} from {host}')
  print(f'=========================================')
  print(f'backup postgresql db for {name}')
  print(f'=========================================')
  sys.stdout.flush()
  clear_database_backup_tmp()
  os.system(f'PGPASSWORD={password} pg_dump -U postgres -h {host} {name} > /webcrate/backup-tmp/{name}.pgsql')
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
    backup_webcrate_files(data_folder, WEBCRATE_BACKUP_FILE_PATHS, BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS)

for servicename,service in services.items():
  service.name = servicename
  if PROJECT_NAME == service.name or PROJECT_NAME == 'all':
    if service.mysql_db and ( BACKUP_TYPE == 'mysql' or BACKUP_TYPE == 'all' ):
      password = read_database_password('mysql.cnf')
      backup_mysql_database(service.name, f'webcrate-{service.name}-mysql', password, f'services/{service.name}/mysql', 'mysql', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS)

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
      filters = ''
      if hasattr(project, 'duplicity_filters'):
        for duplicity_filter in project.duplicity_filters:
          filters = f'{filters}--{duplicity_filter.mode} "{data_folder}/{duplicity_filter.path}" '
      if os.path.isdir(f'{data_folder}'):
        store_files_backup(data_folder, f'projects/{project.name}/files', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, filters)
      #backup solr cores
      log.write(f'Backup solr cores for project {project.name}')
      if os.path.isdir(f'{project.folder}/var/solr/cores'):
        solr_folder = f'{project.folder}/var/solr/cores'
        filters = f'--exclude "{solr_folder}/**/data" '
        store_files_backup(solr_folder, f'projects/{project.name}/solr-cores', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS, filters)

    #connect to project network
    if not helpers.is_network_has_connection(f'webcrate_network_{project.name}', 'webcrate-utils-docker'):
      os.system(f'docker network connect webcrate_network_{project.name} webcrate-utils-docker')

    #backup project mysql
    if project.mysql_db and ( BACKUP_TYPE == 'mysql' or BACKUP_TYPE == 'all' ):
      password = read_database_password('mysql.cnf')
      backup_mysql_database(project.name, f'webcrate-{project.name}-mysql', password, f'projects/{project.name}/project-mysql', 'mysql', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS)


    #backup project mysql5
    if project.mysql5_db and ( BACKUP_TYPE == 'mysql5' or BACKUP_TYPE == 'all' ):
      password = read_database_password('mysql5.cnf')
      backup_mysql_database(project.name, f'webcrate-{project.name}-mysql5', password, f'projects/{project.name}/project-mysql5', 'mysql5', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS)

    #backup project postgresql
    if project.postgresql_db and ( BACKUP_TYPE == 'postgresql' or BACKUP_TYPE == 'all' ):
      password = read_database_password('postgres.cnf')
      backup_postgresql_database(project.name, f'webcrate-{project.name}-postgresql', password, f'projects/{project.name}/project-postgresql', BACKUP_URIS, WEBCRATE_FULL_BACKUP_DAYS, WEBCRATE_MAX_FULL_BACKUPS)
    #disconnect from project network
    os.system(f'docker network disconnect webcrate_network_{project.name} webcrate-utils-docker')

os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/backup')
os.system(f'chmod -R a-rw,u+rw /webcrate/backup')
os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/duplicity')
log.write(f'Backup process ended')
sys.stdout.flush()
