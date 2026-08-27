# Telegram Voice Transcriber

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10--3.14-blue)
![Docker](https://img.shields.io/badge/docker-ready-blue)

Личный Telegram-бот для локальной расшифровки голосовых и аудиосообщений.
Аудио обрабатывается на компьютере или сервере владельца через
`faster-whisper`: платный API и отправка записей в LLM не используются.

## Что понадобится

- Windows 10/11, macOS или Linux;
- Python 3.10–3.14 **или** Docker Desktop;
- интернет для Telegram и однократной загрузки модели Whisper;
- примерно 2 ГБ свободного места для стандартной модели `small` и окружения.

## Быстрый старт на Windows

1. Установите Python с [python.org](https://www.python.org/downloads/).
   При установке отметьте **Add Python to PATH**.
2. Распакуйте этот архив.
3. Нажмите правой кнопкой на `install.ps1` → **Run with PowerShell**.
   Если Windows блокирует сценарий, откройте PowerShell в папке и выполните:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

4. Откройте созданный файл `.env` в Блокноте и заполните токен и ID.
5. Дважды щёлкните `start.bat`.

## Быстрый старт на macOS/Linux

Распакуйте архив, откройте терминал в папке проекта и выполните:

```bash
chmod +x install.sh start.sh
./install.sh
```

Откройте `.env` любым текстовым редактором, заполните токен и ID, затем:

```bash
./start.sh
```

## Создание собственного Telegram-бота

1. Откройте [@BotFather](https://t.me/BotFather).
2. Отправьте `/newbot`, задайте отображаемое имя и уникальный username.
3. Скопируйте полученный токен в `.env` после `BOT_TOKEN=`.
4. Узнайте свой числовой ID у [@userinfobot](https://t.me/userinfobot) и
   укажите его после `ALLOWED_USER_IDS=`. Несколько ID разделяются запятыми.

Пример (значения вымышлены):

```dotenv
BOT_TOKEN=123456789:AAExampleReplaceWithRealToken
ALLOWED_USER_IDS=123456789,987654321
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LANGUAGE=ru
MAX_AUDIO_DURATION=1800
MAX_QUEUE_SIZE=20
```

Не публикуйте `.env` и не пересылайте токен. Если токен утёк, отзовите его
через BotFather и выпустите новый.

## Docker: одинаковый запуск на любой системе

Установите Docker Desktop, создайте `.env` из `.env.example`, затем:

```bash
docker compose up -d --build
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

Кеш модели хранится в Docker volume и сохраняется между перезапусками.

## Использование

Пока `start.sh`, `start.bat` или контейнер запущен:

1. Откройте своего бота в Telegram и нажмите **Start**.
2. Отправьте или перешлите голосовое либо аудиофайл. Поддерживаются WAV,
   MP3, M4A, OGG/OPUS, FLAC, AAC, WMA, WEBM и MP4; файл можно отправить как
   аудио или как документ.
3. Дождитесь текстовой расшифровки.

Первое сообщение обрабатывается дольше: модель загружается в память. Бот
работает последовательно, чтобы несколько файлов не исчерпали RAM.

## Выбор модели

| Модель | Скорость | Качество | Ориентировочно |
|---|---:|---:|---:|
| `tiny` | максимальная | базовое | слабые компьютеры |
| `base` | высокая | хорошее | 4 ГБ RAM |
| `small` | средняя | очень хорошее | рекомендуемый вариант |
| `medium` | низкая | выше | 8+ ГБ RAM |
| `large-v3` | минимальная | максимальное | мощный GPU/сервер |

Для русского языка оставьте `WHISPER_LANGUAGE=ru`. Для разных языков
оставьте значение пустым: `WHISPER_LANGUAGE=`.

## Диагностика

- `Unauthorized` — токен неверный или отозван; выпустите новый в BotFather.
- `Conflict: terminated by other getUpdates request` — с этим токеном уже
  работает другой экземпляр. Остановите его.
- Бот не отвечает — процесс должен оставаться запущенным; проверьте окно
  терминала или `docker compose logs -f`.
- Первый запуск долго стоит на загрузке — скачивается модель; дождитесь
  завершения и не закрывайте терминал.
- На слабом компьютере выберите `WHISPER_MODEL_SIZE=base` или `tiny`.

## Обновление и удаление

Для обновления зависимостей снова запустите `install.sh` или `install.ps1`.
Для удаления локальной установки достаточно удалить распакованную папку;
модель может оставаться в пользовательском кеше Hugging Face.

## Лицензия

Проект распространяется по лицензии MIT. Зависимости имеют собственные
лицензии.
