#!/usr/bin/env python3

import os
import sys
import subprocess

with open('/webcrate/updated-projects.yml', 'r') as updated:
  with open(f'/webcrate/projects.yml', 'w') as projects:
      projects.write(updated.read())
      projects.close()
  updated.close()
os.system(f'rm /webcrate/updated-projects.yml')
# Deletion needs immediate revocation; ordinary saves still wait for Apply.
if '--sync-ftp' in sys.argv[1:]:
  subprocess.run(['docker', 'exec', os.environ.get('WEBCRATE_UTILS_CONTAINER', 'webcrate-utils-docker'), '/ftp-sync.py'], check=True)
sys.exit(0)
