# Развёртывание на Ubuntu

Бот постоянно опрашивает Telegram через systemd. GitHub Actions в этом проекте
запускает тесты; для работы бота нужен запущенный VPS.

## Требования

- Ubuntu с доступом по SSH для первоначальной настройки.
- Исходящий доступ к Telegram, PyPI и Hugging Face.
- Заполненный локальный `.env` с `BOT_TOKEN` и `ALLOWED_USER_IDS`.
- Для VPS с 1 ГБ RAM начните с `WHISPER_MODEL_SIZE=tiny` и
  `WHISPER_COMPUTE_TYPE=int8`. Для более точной модели `base` может
  потребоваться swap; потребление памяти проверяйте на самом VPS.

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

## Автоматическое обновление из GitHub Actions

После первоначальной установки можно создать отдельного пользователя
`telegramdeploy` и отдельный SSH-ключ для GitHub Actions. Этот пользователь
может обновлять код и перезапускать только службу бота; доступ к другим
службам VPS ему не нужен.

1. Сгенерируйте отдельный ключ Ed25519 для GitHub Actions. Его публичную часть
   скопируйте на VPS и запустите `deploy/setup-actions-user.sh` от root, передав
   путь к публичному ключу.
2. Приватную часть добавьте в секрет репозитория `VPS_DEPLOY_KEY`. Не сохраняйте
   её в Git и не используйте root-ключ для GitHub Actions.
3. Установите переменную репозитория `VPS_DEPLOY_ENABLED=true`. Пока переменной
   нет, шаг развёртывания пропускается.
4. После push в `main` workflow `Tests` сначала выполнит тесты, затем
   скопирует код на VPS, обновит Python-зависимости и перезапустит службу.

Workflow не передаёт `.env`: токен остаётся только на VPS. Ключ сервера SSH
закреплён в workflow; при переустановке VPS его нужно обновить.
