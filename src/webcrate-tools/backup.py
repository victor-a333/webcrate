#!/usr/bin/env python3

import os
import yaml
from munch import munchify
from pprint import pprint

with open('/webcrate/projects.yml', 'r') as f:
  projects = munchify(yaml.safe_load(f))
  f.close()

WEBCRATE_MODE = os.environ.get('WEBCRATE_MODE', 'DEV')
WEBCRATE_UID = os.environ.get('WEBCRATE_UID', '1000')
WEBCRATE_GID = os.environ.get('WEBCRATE_GID', '1000')
WEBCRATE_FULL_BACKUP_DAYS = os.environ.get('WEBCRATE_FULL_BACKUP_DAYS', '7')
WEBCRATE_MAX_FULL_BACKUPS = os.environ.get('WEBCRATE_MAX_FULL_BACKUPS', '10')
REMOTE_BACKUP_URI = os.environ.get('REMOTE_BACKUP_URI', 'file:///webcrate/backup')
for projectname,project in projects.items():
  project.name = projectname
  if project.backup:
    #backup files
    if hasattr(project, 'volume'):
      data_folder = f'/projects{(project.volume + 1) if project.volume else ""}/{project.name}/{project.root_folder.split("/")[0]}'
    else:
      data_folder = f'/projects/{project.name}/{project.root_folder.split("/")[0]}'
    FILTERS = ''
    if hasattr(project, 'duplicity_filters'):
      for duplicity_filter in project.duplicity_filters:
        FILTERS = f'{FILTERS}--{duplicity_filter.mode} "{data_folder}/{duplicity_filter.path}" '
    if os.path.isdir(f'{data_folder}'):
      print(f'backup files for project {project.name}')
      os.system(f'duplicity --verbosity notice '
        f'--no-encryption '
        f'--full-if-older-than {WEBCRATE_FULL_BACKUP_DAYS}D '
        f'--num-retries 3 '
        f'--asynchronous-upload '
        f'--allow-source-mismatch '
        f'--volsize 500 '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'{FILTERS}'
        f'"{data_folder}" '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/files"'
      )
      os.system(f'duplicity --verbosity notice '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'--force '
        f'remove-all-but-n-full {WEBCRATE_MAX_FULL_BACKUPS} '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/files"'
      )
    #backup mysql
    if project.mysql_db:
      print(f'backup mysql db for project {project.name}')
      mysql_root_password = os.popen(f'cat /webcrate/secrets/mysql.cnf | grep "password="').read().strip().split("=")[1][1:][:-1].replace("$", "\$")
      os.system(f'mkdir -p /webcrate/backup/tmp')
      os.system(f'rm /webcrate/backup/tmp/*')
      os.system(f'mysqldump --single-transaction --max_allowed_packet=64M -h mysql -u root -p"{mysql_root_password}" --result-file "/webcrate/backup/tmp/{project.name}.sql" "{project.name}"')
      os.system(f'duplicity --verbosity notice '
        f'--no-encryption '
        f'--full-if-older-than {WEBCRATE_FULL_BACKUP_DAYS}D '
        f'--num-retries 3 '
        f'--asynchronous-upload '
        f'--volsize 500 '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'"/webcrate/backup/tmp" '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/mysql"'
      )
      os.system(f'rm /webcrate/backup/tmp/*')
      os.system(f'duplicity --verbosity notice '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'--force '
        f'remove-all-but-n-full {WEBCRATE_MAX_FULL_BACKUPS} '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/mysql"'
      )
    #backup mysql5
    if project.mysql5_db:
      print(f'backup mysql5 db for project {project.name}')
      mysql5_root_password = os.popen(f'cat /webcrate/secrets/mysql5.cnf | grep "password="').read().strip().split("=")[1][1:][:-1].replace("$", "\$")
      os.system(f'mkdir -p /webcrate/backup/tmp')
      os.system(f'rm /webcrate/backup/tmp/*')
      os.system(f'mysqldump --single-transaction --max_allowed_packet=64M -h mysql5 -u root -p"{mysql5_root_password}" --result-file "/webcrate/backup/tmp/{project.name}.sql" "{project.name}"')
      os.system(f'duplicity --verbosity notice '
        f'--no-encryption '
        f'--full-if-older-than {WEBCRATE_FULL_BACKUP_DAYS}D '
        f'--num-retries 3 '
        f'--asynchronous-upload '
        f'--volsize 500 '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'"/webcrate/backup/tmp" '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/mysql5"'
      )
      os.system(f'rm /webcrate/backup/tmp/*')
      os.system(f'duplicity --verbosity notice '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'--force '
        f'remove-all-but-n-full {WEBCRATE_MAX_FULL_BACKUPS} '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/mysql5"'
      )
    #backup postgresql
    if project.postgresql_db:
      print(f'backup postgresql db for project {project.name}')
      postgres_root_password = os.popen(f'cat /webcrate/secrets/postgres.cnf | grep "password="').read().strip().split("=")[1][1:][:-1].replace("$", "\$")
      os.system(f'mkdir -p /webcrate/backup/tmp')
      os.system(f'rm /webcrate/backup/tmp/*')
      os.system(f'PGPASSWORD={postgres_root_password} pg_dump -U postgres -h postgres {project.name} > /webcrate/backup/tmp/{project.name}.pgsql')
      os.system(f'duplicity --verbosity notice '
        f'--no-encryption '
        f'--full-if-older-than {WEBCRATE_FULL_BACKUP_DAYS}D '
        f'--num-retries 3 '
        f'--asynchronous-upload '
        f'--volsize 500 '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'"/webcrate/backup/tmp" '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/postgresql"'
      )
      os.system(f'rm /webcrate/backup/tmp/*')
      os.system(f'duplicity --verbosity notice '
        f'--archive-dir /webcrate/duplicity/.duplicity '
        f'--log-file /webcrate/duplicity/duplicity.log '
        f'--force '
        f'remove-all-but-n-full {WEBCRATE_MAX_FULL_BACKUPS} '
        f'"{REMOTE_BACKUP_URI}/projects/{project.name}/postgresql"'
      )

os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/backup')
os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/duplicity')
