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
  apt-get update || return 1
  apt-get --assume-yes install wkhtmltopdf || return 1
  rm -rf /var/lib/apt/lists/*
}

install_pdf2htmlex() {
  if command -v pdf2htmlEX >/dev/null 2>&1; then
    return
  fi

  echo "$WEBCRATE_PROJECT - installing pdf2htmlex"
  apt-get update || return 1
  apt-get --assume-yes install libfontconfig1 libfreetype6 libglib2.0-0 libx11-6 libxcb1 || return 1
  rm -rf /var/lib/apt/lists/*

  wget -q -O /tmp/pdf2htmlEX.AppImage \
    https://github.com/pdf2htmlEX/pdf2htmlEX/releases/download/v0.18.8.rc1/pdf2htmlEX-0.18.8.rc1-master-20200630-Ubuntu-focal-x86_64.AppImage || return 1
  echo "11de2583a3abce5f141fd7fafb1fea2c67b15886e546d6b7675c600012e6ab8c  /tmp/pdf2htmlEX.AppImage" | sha256sum --check --status || return 1
  chmod u+x /tmp/pdf2htmlEX.AppImage
  mkdir -p /opt/pdf2htmlEX
  (cd /opt/pdf2htmlEX && /tmp/pdf2htmlEX.AppImage --appimage-extract >/dev/null) || return 1
  rm -f /tmp/pdf2htmlEX.AppImage
  ln -sf /opt/pdf2htmlEX/squashfs-root/AppRun /usr/local/bin/pdf2htmlEX
  ln -sf /usr/local/bin/pdf2htmlEX /usr/local/bin/pdf2htmlex
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
    pdf2htmlex)
      install_pdf2htmlex || exit 1
      ;;
    *)
      echo "$WEBCRATE_PROJECT - unsupported application: $application" >&2
      exit 1
      ;;
  esac
done < "$applications_file"
