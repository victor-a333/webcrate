#!/bin/bash

applications_file="/home/$WEBCRATE_PROJECT/.webcrate/applications"

if [ ! -f "$applications_file" ]; then
  exit 0
fi

install_wkhtmltox() {
  if command -v wkhtmltopdf >/dev/null 2>&1; then
    return
  fi

  echo "$WEBCRATE_PROJECT - installing wkhtmltox"
  pacman -U --needed --noconfirm \
    https://archive.archlinux.org/packages/o/openssl-1.1/openssl-1.1-1.1.1.w-2-x86_64.pkg.tar.zst || return 1
  wget -q -O /tmp/wkhtmltox.pkg.tar.xz \
    https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-3/wkhtmltox-0.12.6-3.archlinux-x86_64.pkg.tar.xz || return 1
  tar -xf /tmp/wkhtmltox.pkg.tar.xz -C / || return 1
  rm -f /tmp/wkhtmltox.pkg.tar.xz
  rm -rf /var/cache/pacman/pkg/*
}

while IFS= read -r application || [ -n "$application" ]; do
  application="${application%%#*}"
  application="${application#"${application%%[![:space:]]*}"}"
  application="${application%"${application##*[![:space:]]}"}"

  case "$application" in
    "")
      ;;
    wkhtmltox)
      install_wkhtmltox || exit 1
      ;;
    *)
      echo "$WEBCRATE_PROJECT - unsupported application: $application" >&2
      exit 1
      ;;
  esac
done < "$applications_file"
