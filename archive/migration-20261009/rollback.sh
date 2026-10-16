#!/bin/sh
set -eu
# Restore ONLY XServer production entrypoints; credentials/units never changed.
systemctl stop xserver-checkin@afternoon.service xserver-checkin@evening.service
cd /
sha256sum -c /var/backups/xserver/20261009-migration/prechange.tar.gz.sha256
tar -xzf /var/backups/xserver/20261009-migration/prechange.tar.gz -C / opt/xserver/app/main.py opt/xserver/app/run_xserver_notify.py
# Do not start a batch now. Existing enabled timers will use restored code.
systemctl reset-failed xserver-checkin@afternoon.service xserver-checkin@evening.service
systemctl list-timers --all --no-pager 'xserver*'
