# Развёртывание на Ubuntu

Бот постоянно опрашивает Telegram через systemd. GitHub Actions в этом проекте
запускает тесты; для работы бота нужен запущенный VPS.

## Требования

- Ubuntu с доступом по SSH для первоначальной настройки.
- Исходящий доступ к Telegram, PyPI и Hugging Face.
- Заполненный локальный `.env` с `BOT_TOKEN` и `ALLOWED_USER_IDS`.
- Для VPS с 1 ГБ RAM начните с `WHISPER_MODEL_SIZE=tiny` и
  `WHISPER_COMPUTE_TYPE=int8`. Потребление памяти проверяйте на самом VPS.

## Первая установка

Выполняйте команды из корня проекта, подставив адрес своего VPS:

```bash
ssh root@SERVER 'install -d -m 0755 /opt/telegram-voice-transcriber'
scp bot.py requirements.txt .env root@SERVER:/opt/telegram-voice-transcriber/
scp -r deploy root@SERVER:/opt/telegram-voice-transcriber/
ssh root@SERVER 'bash /opt/telegram-voice-transcriber/deploy/install-ubuntu.sh'
```

Скрипт установит Python и ffmpeg, создаст виртуальное окружение и отдельного
системного пользователя `telegrambot`, затем включит службу. Токен остаётся
только в `/opt/telegram-voice-transcriber/.env` на VPS; файл доступен root и
группе службы. Не добавляйте `.env` в Git.

## Проверка и обновление

```bash
ssh root@SERVER 'systemctl status telegram-voice-transcriber --no-pager'
ssh root@SERVER 'journalctl -u telegram-voice-transcriber -n 100 --no-pager'
```

После изменения кода скопируйте `bot.py`, `requirements.txt` и файлы `deploy`
на VPS повторно, затем выполните:

```bash
ssh root@SERVER 'bash /opt/telegram-voice-transcriber/deploy/install-ubuntu.sh'
ssh root@SERVER 'systemctl restart telegram-voice-transcriber'
```

Модель загружается при первом запуске и хранится в
`/var/lib/telegram-voice-transcriber/huggingface`. При обычном перезапуске
службы повторная загрузка модели не нужна. Временные аудиофайлы удаляются
после обработки.
