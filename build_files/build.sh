#!/usr/bin/bash

set -euo pipefail

# Keep the base image lean. GUI apps offered by G Store are installed by the
# user, while PySide supplies the native G Store and G Mode interfaces.
dnf5 install -y python3-pyside6
dnf5 clean all

install -d \
  /usr/libexec/g-os/apps \
  /usr/share/g-os/catalog \
  /usr/share/g-os/profiles

cp -a /ctx/apps/. /usr/libexec/g-os/apps/
cp -a /ctx/catalog/. /usr/share/g-os/catalog/
cp -a /ctx/profiles/. /usr/share/g-os/profiles/
cp -a /ctx/system_files/. /

chmod 0755 /usr/bin/g-store /usr/bin/g-mode
