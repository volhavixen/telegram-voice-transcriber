#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 || $# -ne 1 || ! -s "$1" ]]; then
  echo 'Usage: sudo bash deploy/setup-actions-user.sh /path/to/actions-public-key.pub' >&2
  exit 1
fi

app_dir=/opt/telegram-voice-transcriber
test -s "$app_dir/.env"
test -d "$app_dir/.venv"

if ! id -u telegramdeploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash telegramdeploy
fi

install -d -m 0700 -o telegramdeploy -g telegramdeploy /home/telegramdeploy/.ssh
printf 'restrict %s\n' "$(cat "$1")" > /home/telegramdeploy/.ssh/authorized_keys
chown telegramdeploy:telegramdeploy /home/telegramdeploy/.ssh/authorized_keys
chmod 0600 /home/telegramdeploy/.ssh/authorized_keys

chown telegramdeploy:telegrambot "$app_dir"
chmod 2750 "$app_dir"
chown telegramdeploy:telegrambot "$app_dir/bot.py" "$app_dir/requirements.txt"
chown -R telegramdeploy:telegrambot "$app_dir/deploy" "$app_dir/.venv"
chown root:telegrambot "$app_dir/.env"
chmod 0640 "$app_dir/.env"

cat > /etc/sudoers.d/telegram-voice-transcriber-deploy <<'EOF'
telegramdeploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart telegram-voice-transcriber.service, /usr/bin/systemctl is-active telegram-voice-transcriber.service
EOF
chmod 0440 /etc/sudoers.d/telegram-voice-transcriber-deploy
visudo -cf /etc/sudoers.d/telegram-voice-transcriber-deploy
