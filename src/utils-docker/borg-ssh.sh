#!/bin/sh

case "$WEBCRATE_BORG_SSH_KEY" in
  ''|.|..|*/*)
    echo "WEBCRATE_BORG_SSH_KEY must contain a key filename from var/ssh, not a path" >&2
    exit 2
    ;;
esac

private_key="/webcrate-readonly/var/ssh/$WEBCRATE_BORG_SSH_KEY"
if [ ! -f "$private_key" ]; then
  echo "Borg SSH private key not found: $private_key" >&2
  exit 2
fi

exec ssh \
  -i "$private_key" \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=accept-new \
  "$@"
