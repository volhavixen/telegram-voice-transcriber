#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo 'Run this script as root.' >&2
  exit 1
fi

cd /opt/telegram-voice-transcriber
test -s .env || { echo 'Missing /opt/telegram-voice-transcriber/.env' >&2; exit 1; }

apt-get update
apt-get install -y --no-install-recommends python3 python3-venv ffmpeg

if ! id -u telegrambot >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /var/lib/telegram-voice-transcriber \
    --shell /usr/sbin/nologin telegrambot
fi

python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt

chown root:telegrambot .env
chmod 0640 .env
install -m 0644 deploy/telegram-voice-transcriber.service \
  /etc/systemd/system/telegram-voice-transcriber.service
systemctl daemon-reload
systemctl enable --now telegram-voice-transcriber.service
systemctl --no-pager --full status telegram-voice-transcriber.service
