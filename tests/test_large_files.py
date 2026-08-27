import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("BOT_TOKEN", "123456789:AAExampleTokenForLocalTestsOnly")

import bot as bot_module
from aiogram.exceptions import TelegramEntityTooLarge
from bot import FileTooLargeError, check_file_size


class LargeFileSupportActiveTests(unittest.TestCase):
    def setUp(self):
        self._original_support = bot_module.LARGE_FILE_SUPPORT
        self._original_pyro = bot_module.pyro_client

    def tearDown(self):
        bot_module.LARGE_FILE_SUPPORT = self._original_support
        bot_module.pyro_client = self._original_pyro

    def test_requires_both_the_flag_and_a_connected_client(self):
        bot_module.LARGE_FILE_SUPPORT = True
        bot_module.pyro_client = None
        self.assertFalse(bot_module.large_file_support_active())

        bot_module.pyro_client = object()
        self.assertTrue(bot_module.large_file_support_active())

        bot_module.LARGE_FILE_SUPPORT = False
        self.assertFalse(bot_module.large_file_support_active())


class CheckFileSizeTests(unittest.TestCase):
    """check_file_size() is the up-front guard, used before a job is even queued."""

    def setUp(self):
        self._original_support = bot_module.LARGE_FILE_SUPPORT
        self._original_pyro = bot_module.pyro_client

    def tearDown(self):
        bot_module.LARGE_FILE_SUPPORT = self._original_support
        bot_module.pyro_client = self._original_pyro

    def test_unknown_size_is_allowed(self):
        check_file_size(None)  # Telegram didn't report a size — nothing to reject yet.

    def test_small_file_is_allowed(self):
        check_file_size(5 * 1024 * 1024)

    def test_over_20mb_without_support_is_rejected(self):
        bot_module.LARGE_FILE_SUPPORT = False
        with self.assertRaises(FileTooLargeError) as ctx:
            check_file_size(25 * 1024 * 1024)
        self.assertIn("API_ID", str(ctx.exception))

    def test_over_20mb_with_support_is_allowed(self):
        bot_module.LARGE_FILE_SUPPORT = True
        bot_module.pyro_client = object()  # stand-in: only "is not None" is checked
        check_file_size(25 * 1024 * 1024)

    def test_over_20mb_is_rejected_when_mtproto_never_actually_connected(self):
        # Regression: LARGE_FILE_SUPPORT only reflects config (API_ID/API_HASH being set).
        # main() resets pyro_client back to None if the MTProto client failed to start, and
        # this check must follow that, not just the config flag.
        bot_module.LARGE_FILE_SUPPORT = True
        bot_module.pyro_client = None
        with self.assertRaises(FileTooLargeError) as ctx:
            check_file_size(25 * 1024 * 1024)
        self.assertIn("API_ID", str(ctx.exception))

    def test_over_2gb_is_always_rejected_even_with_support(self):
        bot_module.LARGE_FILE_SUPPORT = True
        bot_module.pyro_client = object()
        with self.assertRaises(FileTooLargeError) as ctx:
            check_file_size(3000 * 1024 * 1024)
        self.assertIn("2000", str(ctx.exception))


class DownloadAudioTests(unittest.IsolatedAsyncioTestCase):
    """download_audio() is the actual download step, with the MTProto fallback."""

    def setUp(self):
        self._original_support = bot_module.LARGE_FILE_SUPPORT
        self._original_pyro = bot_module.pyro_client

    def tearDown(self):
        bot_module.LARGE_FILE_SUPPORT = self._original_support
        bot_module.pyro_client = self._original_pyro

    async def test_normal_download_uses_bot_api_only(self):
        tmp_path = Path("/tmp/does-not-matter.ogg")
        fake_file = type("FakeFile", (), {"file_path": "voice/file_1.ogg"})()
        media = type("FakeMedia", (), {"file_id": "abc123"})()
        bot_module.pyro_client = AsyncMock()

        with patch.object(bot_module.bot, "get_file", AsyncMock(return_value=fake_file)) as get_file_mock, \
                patch.object(bot_module.bot, "download_file", AsyncMock()) as download_file_mock:
            await bot_module.download_audio(media, tmp_path)

        get_file_mock.assert_awaited_once_with("abc123")
        download_file_mock.assert_awaited_once_with("voice/file_1.ogg", destination=tmp_path)
        bot_module.pyro_client.download_media.assert_not_awaited()

    async def test_falls_back_to_mtproto_when_file_too_large(self):
        tmp_path = Path("/tmp/does-not-matter.ogg")
        media = type("FakeMedia", (), {"file_id": "big-file-id"})()
        too_large = TelegramEntityTooLarge(method=None, message="Request Entity Too Large")

        bot_module.LARGE_FILE_SUPPORT = True
        bot_module.pyro_client = AsyncMock()
        bot_module.pyro_client.download_media = AsyncMock(return_value=str(tmp_path))

        with patch.object(bot_module.bot, "get_file", AsyncMock(side_effect=too_large)), \
                patch.object(bot_module.bot, "download_file", AsyncMock()) as download_file_mock:
            await bot_module.download_audio(media, tmp_path)

        download_file_mock.assert_not_awaited()
        bot_module.pyro_client.download_media.assert_awaited_once_with(
            "big-file-id", file_name=str(tmp_path)
        )

    async def test_raises_friendly_error_when_too_large_and_unsupported(self):
        tmp_path = Path("/tmp/does-not-matter.ogg")
        media = type("FakeMedia", (), {"file_id": "big-file-id"})()
        too_large = TelegramEntityTooLarge(method=None, message="Request Entity Too Large")

        bot_module.LARGE_FILE_SUPPORT = False
        bot_module.pyro_client = None

        with patch.object(bot_module.bot, "get_file", AsyncMock(side_effect=too_large)):
            with self.assertRaises(FileTooLargeError) as ctx:
                await bot_module.download_audio(media, tmp_path)
        self.assertIn("API_ID", str(ctx.exception))

    async def test_raises_friendly_error_when_flag_set_but_client_never_connected(self):
        tmp_path = Path("/tmp/does-not-matter.ogg")
        media = type("FakeMedia", (), {"file_id": "big-file-id"})()
        too_large = TelegramEntityTooLarge(method=None, message="Request Entity Too Large")

        bot_module.LARGE_FILE_SUPPORT = True
        bot_module.pyro_client = None  # e.g. MTProto failed to start in main()

        with patch.object(bot_module.bot, "get_file", AsyncMock(side_effect=too_large)):
            with self.assertRaises(FileTooLargeError):
                await bot_module.download_audio(media, tmp_path)

    async def test_raises_when_mtproto_download_returns_none(self):
        tmp_path = Path("/tmp/does-not-matter.ogg")
        media = type("FakeMedia", (), {"file_id": "big-file-id"})()
        too_large = TelegramEntityTooLarge(method=None, message="Request Entity Too Large")

        bot_module.LARGE_FILE_SUPPORT = True
        bot_module.pyro_client = AsyncMock()
        bot_module.pyro_client.download_media = AsyncMock(return_value=None)

        with patch.object(bot_module.bot, "get_file", AsyncMock(side_effect=too_large)):
            with self.assertRaises(RuntimeError):
                await bot_module.download_audio(media, tmp_path)

    async def test_other_bot_api_errors_are_not_swallowed(self):
        tmp_path = Path("/tmp/does-not-matter.ogg")
        media = type("FakeMedia", (), {"file_id": "abc123"})()

        with patch.object(bot_module.bot, "get_file", AsyncMock(side_effect=ValueError("boom"))):
            with self.assertRaises(ValueError):
                await bot_module.download_audio(media, tmp_path)


class LoadModelTests(unittest.TestCase):
    def test_load_model_passes_configured_cpu_threads(self):
        original_threads = bot_module.WHISPER_CPU_THREADS
        bot_module.WHISPER_CPU_THREADS = 4
        try:
            with patch.object(bot_module, "WhisperModel") as whisper_model_cls:
                bot_module.load_model()
        finally:
            bot_module.WHISPER_CPU_THREADS = original_threads

        _, kwargs = whisper_model_cls.call_args
        self.assertEqual(kwargs["cpu_threads"], 4)


class TranscribeSyncTests(unittest.TestCase):
    def test_transcribe_sync_disables_previous_text_conditioning(self):
        fake_model = MagicMock()
        fake_model.transcribe.return_value = ([], None)

        bot_module.transcribe_sync(fake_model, Path("/tmp/whatever.wav"))

        _, kwargs = fake_model.transcribe.call_args
        self.assertFalse(kwargs["condition_on_previous_text"])


class GetModelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_task = bot_module.model_load_task

    def tearDown(self):
        bot_module.model_load_task = self._original_task

    async def test_get_model_loads_once_and_reuses_the_same_task(self):
        bot_module.model_load_task = None
        sentinel = object()

        with patch.object(bot_module, "load_model", return_value=sentinel) as load_model_mock:
            first = await bot_module.get_model()
            second = await bot_module.get_model()

        self.assertIs(first, sentinel)
        self.assertIs(second, sentinel)
        load_model_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
