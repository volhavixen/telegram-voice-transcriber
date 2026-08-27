FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg нужен faster-whisper/ffmpeg-based декодированию аудио форматов Telegram (.ogg/opus)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# Модель Whisper скачается и закешируется в /root/.cache при первом запуске.
# Монтируйте volume на этот путь в docker-compose.yml, чтобы не скачивать
# модель заново при каждом перезапуске контейнера.
CMD ["python", "-u", "bot.py"]
