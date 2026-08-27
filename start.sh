#!/bin/sh
set -eu

cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "Окружение не установлено. Сначала выполните ./install.sh"
    exit 1
fi

exec .venv/bin/python bot.py
