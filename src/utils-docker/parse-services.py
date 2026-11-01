#!/usr/bin/env python3

import os
import nginx_tls
import service_settings
import yaml
from munch import munchify
from pprint import pprint

with open('/webcrate/services.yml', 'r') as f:
  services = munchify(yaml.safe_load(f))

DOCKER_HOST_IP = os.environ.get('DOCKER_HOST_IP', '')
WEBCRATE_UID = os.environ.get('WEBCRATE_UID', '1000')
WEBCRATE_GID = os.environ.get('WEBCRATE_GID', '1000')

WEBCRATE_SERVICE_HTMLTOPDF = os.environ.get('WEBCRATE_SERVICE_HTMLTOPDF', 'false') == 'true'
WEBCRATE_SERVICE_DOCTOHTML = os.environ.get('WEBCRATE_SERVICE_DOCTOHTML', 'false') == 'true'
WEBCRATE_SERVICE_STATS = os.environ.get('WEBCRATE_SERVICE_STATS', 'false') == 'true'
WEBCRATE_SERVICE_DOCXTOPDF = os.environ.get('WEBCRATE_SERVICE_DOCXTOPDF', 'false') == 'true'
WEBCRATE_SERVICE_PDFFOOTER = os.environ.get('WEBCRATE_SERVICE_PDFFOOTER', 'false') == 'true'

for servicename, service in services.items():
  if service_settings.enabled(servicename):

    service.name = servicename

    template = 'default';
    if os.path.isfile(f'/webcrate/nginx-templates/{service.name}-service.conf'):
      template = service.name
    os.system(f'cp -rf /webcrate/nginx-templates/{template}-service.conf /webcrate/nginx/confs/{service.name}-service.conf')

    with open(f'/webcrate/nginx/confs/{service.name}-service.conf', 'r') as f:
      conf = f.read()
      f.close()

    conf = conf.replace('%domain%', service.domain)
    conf = conf.replace('%host%', f'webcrate-{service.name}')
    conf = conf.replace('%service%', service.name)
    conf = conf.replace('%port%', str(service.port))

    with open(f'/webcrate/nginx/confs/{service.name}-service.conf', 'w') as f:
      f.write(conf)
      f.close()

    print(f'{service.name} config - generated')

    nginx_tls.configure(service.name, service.https)
    with open(f'/webcrate/dnsmasq/hosts/{service.name}.hosts', 'w') as f:
      f.write(f'{DOCKER_HOST_IP} {service.domain}\n')
      f.close()

os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/nginx/confs')
os.system(f'chown -R {WEBCRATE_UID}:{WEBCRATE_GID} /webcrate/dnsmasq')
