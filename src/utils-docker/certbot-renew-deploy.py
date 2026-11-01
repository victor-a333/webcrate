#!/usr/bin/env python3
"""Make renewed keys readable before validating and reloading Nginx."""
import os
import subprocess
import nginx_tls

owner = f"{os.environ.get('WEBCRATE_UID', '1000')}:{os.environ.get('WEBCRATE_GID', '1000')}"
subprocess.run(['chown', '-R', owner, '/webcrate/letsencrypt'], check=True)
nginx_tls.reload_nginx()
