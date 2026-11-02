#!/bin/bash
set -e

app_uid=${WEBCRATE_UID:-1000}
app_gid=${WEBCRATE_GID:-1000}

if [ "$app_gid" != '0' ] && [ "$app_gid" != "$(id -g app)" ]; then
  groupmod -o -g "$app_gid" app
fi
if [ "$app_uid" != '0' ] && [ "$app_uid" != "$(id -u app)" ]; then
  usermod -o -u "$app_uid" app
fi

mkdir -p /run/php /app/var /app/logs
chown app:app /webcrate
chown -R app:app /app/var /app/logs

/webcrate/init-db.py

# Initialization creates Symfony caches as root; FPM runs as app.
chown -R app:app /app/var /app/logs

exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
