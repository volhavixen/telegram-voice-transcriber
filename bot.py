"""Telegram bot that transcribes voice and audio messages locally."""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramEntityTooLarge, TelegramUnauthorizedError
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from faster_whisper import WhisperModel

# "pyrogram" is imported from the "kurigram" package (see requirements.txt) — kurigram is an
# actively maintained drop-in replacement for the original, now-stale Pyrogram library, and it
# keeps the same "pyrogram" module name on purpose.
from pyrogram import Client as PyrogramClient

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("voice-transcriber-bot")

MAX_TELEGRAM_MESSAGE_LEN = 4000
SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac", ".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga",
    ".ogg", ".opus", ".wav", ".webm", ".wma",
}

# The regular Telegram Bot API refuses to hand bots files bigger than this.
BOT_API_DOWNLOAD_LIMIT = 20 * 1024 * 1024
# Telegram's current ceiling for bots downloading over MTProto (same as a local Bot API
# server would allow). Telegram, not this constant, has the final say — this is only used
# to reject obviously-too-large files early with a clear message.
MTPROTO_DOWNLOAD_LIMIT = 2000 * 1024 * 1024

LARGE_FILE_DISABLED_MESSAGE = (
    "Файл больше 20 МБ — обычный Telegram Bot API не позволяет ботам скачивать такие файлы.\n"
    "Чтобы бот мог их обрабатывать, администратору нужно получить API_ID и API_HASH на "
    "https://my.telegram.org и указать их в .env (см. README, раздел «Файлы больше 20 МБ»)."
)


class FileTooLargeError(Exception):
    """Raised when a file cannot be downloaded within Telegram's or our own limits."""


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

API_ID_RAW = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
if bool(API_ID_RAW) != bool(API_HASH):
    raise SystemExit(
        "Укажите либо оба API_ID и API_HASH (для файлов больше 20 МБ), либо оставьте оба пустыми."
    )
LARGE_FILE_SUPPORT = bool(API_ID_RAW and API_HASH)
if LARGE_FILE_SUPPORT:
    try:
        API_ID = int(API_ID_RAW)
    except ValueError as error:
        raise SystemExit("API_ID должен быть числом. Получите его на https://my.telegram.org.") from error
    log.info("Поддержка файлов больше 20 МБ включена (заданы API_ID и API_HASH)")
else:
    API_ID = None
    log.info(
        "Поддержка файлов больше 20 МБ выключена — заполните API_ID и API_HASH в .env, чтобы включить"
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
transcription_queue: asyncio.Queue["TranscriptionJob"] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

pyro_client: PyrogramClient | None = None
if LARGE_FILE_SUPPORT:
    pyro_client = PyrogramClient(
        name="large_file_helper",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
    )


@dataclass(slots=True)
class TranscriptionJob:
    message: Message
    status: Message
    audio_path: Path


def is_allowed(user_id: int | None) -> bool:
    return user_id is not None and (not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS)


def check_file_size(file_size: int | None) -> None:
    """Reject obviously too-large files up front, when Telegram reports a size for them."""
    if file_size is None:
        return
    if file_size > MTPROTO_DOWNLOAD_LIMIT:
        raise FileTooLargeError(
            f"Файл больше {MTPROTO_DOWNLOAD_LIMIT // (1024 * 1024)} МБ — "
            "Telegram не позволяет ботам скачивать такие файлы."
        )
    if file_size > BOT_API_DOWNLOAD_LIMIT and not LARGE_FILE_SUPPORT:
        raise FileTooLargeError(LARGE_FILE_DISABLED_MESSAGE)


async def download_audio(media, tmp_path: Path) -> None:
    """Download media into tmp_path, falling back to MTProto for files over 20 MB.

    The regular Bot API (bot.get_file/download_file) refuses files bigger than 20 MB with
    TelegramEntityTooLarge. When API_ID/API_HASH are configured, we retry the same file
    through a Pyrogram/MTProto client instead, which Telegram allows up to ~2 GB for bots.
    """
    try:
        telegram_file = await bot.get_file(media.file_id)
        await bot.download_file(telegram_file.file_path, destination=tmp_path)
        return
    except TelegramEntityTooLarge as error:
        if not LARGE_FILE_SUPPORT or pyro_client is None:
            raise FileTooLargeError(LARGE_FILE_DISABLED_MESSAGE) from error

    log.info("Файл больше 20 МБ, скачиваю через MTProto (API_ID/API_HASH)")
    downloaded = await pyro_client.download_media(media.file_id, file_name=str(tmp_path))
    if downloaded is None:
        raise RuntimeError("MTProto-загрузка не вернула файл (download_media() -> None)")


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
    try:
        check_file_size(getattr(media, "file_size", None))
    except FileTooLargeError as error:
        await message.reply(str(error))
        return
    if transcription_queue.full():
        await message.reply("Очередь переполнена. Попробуйте отправить аудио немного позже.")
        return

    position = transcription_queue.qsize() + 1
    status = await message.reply(f"Принято. Позиция в очереди: {position} ⏳")
    suffix = Path(file_name).suffix or ".ogg"
    fd, tmp_path_str = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        await download_audio(media, tmp_path)
        await transcription_queue.put(TranscriptionJob(message, status, tmp_path))
        log.info(
            "Аудио получено: user=%s duration=%ss queue=%d",
            user_id,
            duration or "unknown",
            transcription_queue.qsize(),
        )
    except FileTooLargeError as error:
        tmp_path.unlink(missing_ok=True)
        await status.edit_text(str(error))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        log.exception("Ошибка при скачивании аудио")
        await status.edit_text("Не удалось скачать аудио 😕 Попробуйте ещё раз.")


async def main() -> None:
    worker_task = asyncio.create_task(worker(), name="transcription-worker")
    if pyro_client is not None:
        await pyro_client.start()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
        if pyro_client is not None:
            await pyro_client.stop()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TelegramUnauthorizedError:
        log.error("Telegram отклонил BOT_TOKEN. Получите актуальный токен у @BotFather и обновите .env.")
    except (KeyboardInterrupt, SystemExit):
        log.info("Бот остановлен")
