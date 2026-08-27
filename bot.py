"""Telegram bot that transcribes voice and audio messages locally."""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from faster_whisper import WhisperModel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("voice-transcriber-bot")

MAX_TELEGRAM_MESSAGE_LEN = 4000
SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac", ".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga",
    ".ogg", ".opus", ".wav", ".webm", ".wma",
}


def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise SystemExit(f"{name} должен быть целым числом, получено: {raw!r}") from error
    if value < minimum:
        raise SystemExit(f"{name} должен быть не меньше {minimum}")
    return value


def parse_user_ids(raw: str) -> frozenset[int]:
    try:
        return frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as error:
        raise SystemExit("ALLOWED_USER_IDS должен содержать Telegram ID через запятую") from error


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните токен.")

ALLOWED_USER_IDS = parse_user_ids(os.getenv("ALLOWED_USER_IDS", ""))
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small").strip()
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu").strip()
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip()
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "").strip() or None
MAX_AUDIO_DURATION = env_int("MAX_AUDIO_DURATION", 1800)
MAX_QUEUE_SIZE = env_int("MAX_QUEUE_SIZE", 20)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
transcription_queue: asyncio.Queue["TranscriptionJob"] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)


@dataclass(slots=True)
class TranscriptionJob:
    message: Message
    status: Message
    audio_path: Path


def is_allowed(user_id: int | None) -> bool:
    return user_id is not None and (not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS)


def load_model() -> WhisperModel:
    log.info(
        "Загружаю Whisper: size=%s device=%s compute_type=%s",
        WHISPER_MODEL_SIZE,
        WHISPER_DEVICE,
        WHISPER_COMPUTE_TYPE,
    )
    loaded_model = WhisperModel(
        WHISPER_MODEL_SIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )
    log.info("Модель загружена")
    return loaded_model


def transcribe_sync(model: WhisperModel, audio_path: Path) -> str:
    segments, _info = model.transcribe(
        str(audio_path),
        language=WHISPER_LANGUAGE,
        vad_filter=True,
        beam_size=1,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def split_text(text: str, limit: int = MAX_TELEGRAM_MESSAGE_LEN) -> list[str]:
    """Split on whitespace when possible, while respecting Telegram's limit."""
    chunks: list[str] = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks


async def send_long_text(message: Message, text: str) -> None:
    if not text:
        await message.reply("Не удалось распознать речь в этом сообщении 🤔")
        return
    for chunk in split_text(text):
        await message.reply(chunk)


async def worker() -> None:
    model: WhisperModel | None = None
    while True:
        job = await transcription_queue.get()
        try:
            await job.status.edit_text("Распознаю голосовое сообщение… ⏳")
            if model is None:
                await job.status.edit_text("Загружаю модель распознавания… Первый запуск дольше обычного ⏳")
                model = await asyncio.to_thread(load_model)
            text = await asyncio.to_thread(transcribe_sync, model, job.audio_path)
            await job.status.delete()
            await send_long_text(job.message, text)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка при распознавании голосового сообщения")
            try:
                await job.status.edit_text("Что-то пошло не так при распознавании 😕 Попробуйте ещё раз.")
            except Exception:
                log.exception("Не удалось обновить сообщение о статусе")
        finally:
            job.audio_path.unlink(missing_ok=True)
            transcription_queue.task_done()


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    if not is_allowed(message.from_user.id if message.from_user else None):
        await message.reply("Извините, у вас нет доступа к этому боту.")
        return
    await message.reply(
        "Привет! Пришлите или перешлите мне голосовое или аудиосообщение — "
        "я локально расшифрую его в текст."
    )


@dp.message(F.voice | F.audio | F.document)
async def on_voice(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_allowed(user_id):
        await message.reply("Извините, у вас нет доступа к этому боту.")
        return

    media = message.voice or message.audio or message.document
    if media is None:
        return
    file_name = getattr(media, "file_name", None) or "audio.ogg"
    if message.document and Path(file_name).suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        await message.reply(
            "Этот файл не похож на поддерживаемое аудио. Подойдут WAV, MP3, M4A, "
            "OGG/OPUS, FLAC, AAC, WMA, WEBM и MP4."
        )
        return
    duration = getattr(media, "duration", 0) or 0
    if duration > MAX_AUDIO_DURATION:
        await message.reply(f"Аудио слишком длинное. Максимум: {MAX_AUDIO_DURATION // 60} мин.")
        return
    if transcription_queue.full():
        await message.reply("Очередь переполнена. Попробуйте отправить аудио немного позже.")
        return

    position = transcription_queue.qsize() + 1
    status = await message.reply(f"Принято. Позиция в очереди: {position} ⏳")
    tmp_path: Path | None = None
    try:
        telegram_file = await bot.get_file(media.file_id)
        suffix = Path(file_name).suffix or Path(telegram_file.file_path or "audio.ogg").suffix or ".ogg"
        fd, tmp_path_str = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        tmp_path = Path(tmp_path_str)
        await bot.download_file(telegram_file.file_path, destination=tmp_path)
        await transcription_queue.put(TranscriptionJob(message, status, tmp_path))
        log.info(
            "Аудио получено: user=%s duration=%ss queue=%d",
            user_id,
            duration or "unknown",
            transcription_queue.qsize(),
        )
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        log.exception("Ошибка при скачивании аудио")
        await status.edit_text("Не удалось скачать аудио 😕 Попробуйте ещё раз.")


async def main() -> None:
    worker_task = asyncio.create_task(worker(), name="transcription-worker")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TelegramUnauthorizedError:
        log.error("Telegram отклонил BOT_TOKEN. Получите актуальный токен у @BotFather и обновите .env.")
    except (KeyboardInterrupt, SystemExit):
        log.info("Бот остановлен")
