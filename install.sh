#!/bin/sh
set -eu

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python 3 не найден. Установите Python 3.10–3.14: https://www.python.org/downloads/"
    exit 1
fi

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 15) else "Нужен Python 3.10–3.14")'

if [ ! -d .venv ]; then
    "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Создан файл .env — впишите в него BOT_TOKEN и ALLOWED_USER_IDS."
else
    echo "Файл .env уже существует и сохранён без изменений."
fi

echo "Установка завершена. После настройки .env запустите: ./start.sh"
