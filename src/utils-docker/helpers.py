#!/usr/bin/env python3
import os
import subprocess
import yaml
from munch import munchify
from log import log
log = log('/webcrate/log/app.log')

WEBCRATE_UID = os.environ.get('WEBCRATE_UID', '1000')
WEBCRATE_GID = os.environ.get('WEBCRATE_GID', '1000')

def load_openssl_conf(name):
  import certificates
  return certificates.load_openssl_conf(name)

def load_domains(name):
  import certificates
  return certificates.load_domains(name)

def is_nginx_up():
  return "nginx is running" in os.popen(f'docker exec webcrate-nginx service nginx status').read().strip()

def mysql_query(host, password, query, check=False):
  env = os.environ.copy()
  env['MYSQL_PWD'] = password
  return subprocess.run(
    ['mariadb', '--skip-ssl', '-u', 'root', '-h', host, '-e', query],
    env=env,
    text=True,
    capture_output=True,
    check=check
  )

def is_mysql_up(host, password):
  return mysql_query(host, password, 'SELECT 1;').returncode == 0

def mysql_database_exists(host, password, database):
  result = mysql_query(host, password, 'SHOW DATABASES;', check=True)
  return database in result.stdout.splitlines()[1:]

def mysql_identifier(value):
  return f'`{value.replace("`", "``")}`'

def mysql_string(value):
  return "'" + value.replace('\\', '\\\\').replace("'", "''") + "'"

def create_mysql_database_and_user(host, root_password, name, user_password):
  identifier = mysql_identifier(name)
  password = mysql_string(user_password)
  mysql_query(host, root_password, f'CREATE DATABASE {identifier};', check=True)
  mysql_query(host, root_password, f"CREATE USER {identifier}@'%' IDENTIFIED BY {password};", check=True)
  mysql_query(host, root_password, f"GRANT ALL PRIVILEGES ON {identifier}.* TO {identifier}@'%';", check=True)
  mysql_query(host, root_password, 'FLUSH PRIVILEGES;', check=True)

def is_postgresql_up(host, password):
  return os.popen(f'psql -d "host={host} user=postgres password={password}" -tAc "SELECT 1 FROM pg_database LIMIT 1;" 2>/dev/null').read().strip()

def is_container_exists(container_name):
  return os.popen(f'docker container inspect {container_name} 2>/dev/null | grep \\"/{container_name}\\" | wc -l').read().strip() == '1'

def is_network_exists(network_name):
  return os.popen(f'docker network inspect {network_name} 2>/dev/null | grep \\"{network_name}\\" | wc -l').read().strip() == '1'

def is_network_has_connection(network_name, container_name):
  return os.popen(f'docker network inspect {network_name} 2>/dev/null | grep \\"{container_name}\\" | wc -l').read().strip() == '1'

def genereate_openssl_conf(name, domains):
  import certificates
  return certificates.genereate_openssl_conf(name, domains)

def genereate_openssl_root_conf():
  import certificates
  return certificates.genereate_openssl_root_conf()

def init_openssl_root_conf():
  import certificates
  return certificates.init_openssl_root_conf()

def init_letsencrypt_conf():
  import certificates
  return certificates.initialize_account()
