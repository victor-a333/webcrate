#!/bin/sh
set -eu
umask 077
mkdir -p /webcrate/tls /run/proftpd
if [ ! -f /webcrate/tls/server.crt ] && [ ! -f /webcrate/tls/server.key ]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
    -subj '/CN=Webcrate FTP' \
    -keyout /webcrate/tls/server.key -out /webcrate/tls/server.crt
fi
# A partial or invalid certificate pair is an error, never silently replaced.
/webcrate/parse-projects.py
exec /usr/sbin/proftpd --nodaemon --config /etc/proftpd/proftpd.conf
