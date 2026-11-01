#!/usr/bin/env python3

import os
import sys
import yaml
import idna
import helpers
import certificates
import asyncio
from munch import munchify
from log import log

log = log('/webcrate/log/app.log')

with open('/webcrate/redirects.yml', 'r') as f:
  redirects = munchify(yaml.safe_load(f))
  f.close()

WEBCRATE_UID = os.environ.get('WEBCRATE_UID', '1000')
WEBCRATE_GID = os.environ.get('WEBCRATE_GID', '1000')
WEBCRATE_PWD = os.environ.get('WEBCRATE_PWD', '')
REDIRECT_NAME = sys.argv[1]

async def initCertificates (redirect):
  return certificates.initialize(redirect, template='redirect-ssl.conf')


async def asyncOps (redirect):
  initCertificatesTask = asyncio.create_task(initCertificates(redirect))
  await initCertificatesTask
  return initCertificatesTask.result()

for redirectname,redirect in redirects.items():
  if REDIRECT_NAME == redirectname and redirect.active:
    redirect.name = f'redirect-{redirectname}'
    nginx_reload_needed = asyncio.run(asyncOps(redirect))
    log.write(f'{redirect.name} - started')

sys.stdout.flush()
sys.exit(0)
