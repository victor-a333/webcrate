#!/usr/bin/env python3

import os
import yaml
from munch import munchify
from pprint import pprint

with open('/webcrate/services/services.yml', 'r') as f:
  services = munchify(yaml.safe_load(f))

MODE = os.environ.get('WEBCRATE_MODE', 'DEV')
DOCKER_HOST_IP = os.environ.get('DOCKER_HOST_IP', '')

print(f'MODE = {MODE}')

for servicename, service in services.items():
  service.name = servicename

  os.system(f'cp -rf /webcrate/services/{service.name if service.nginx_config == "custom" else "default"}.conf /webcrate/nginx_configs/{service.name}.conf')

  with open(f'/webcrate/nginx_configs/{service.name}.conf', 'r') as f:
    conf = f.read()
    f.close()

  conf = conf.replace('%domains%', " ".join(service.domains))
  conf = conf.replace('%host%', service.name)
  conf = conf.replace('%port%', str(service.port))

  with open(f'/webcrate/nginx_configs/{service.name}.conf', 'w') as f:
    f.write(conf)
    f.close()

  print(f'{service.name} config - generated')

if MODE == "DEV":
  with open(f'/webcrate/dnsmasq_hosts/hosts_nginx', 'a') as f:
    for servicename, service in services.items():
      service.name = servicename
      f.write(f'{DOCKER_HOST_IP} {" ".join(service.domains)}\n')
    f.close()