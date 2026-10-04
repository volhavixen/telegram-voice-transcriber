import os
import unittest
from unittest.mock import AsyncMock

os.environ.setdefault("BOT_TOKEN", "123456789:AAExampleTokenForLocalTestsOnly")

from bot import env_int, parse_user_ids, send_long_text, split_text


class HelperTests(unittest.TestCase):
    def test_parse_user_ids(self):
        self.assertEqual(parse_user_ids("1, 2,,3"), frozenset({1, 2, 3}))

    def test_split_text_prefers_spaces(self):
        self.assertEqual(split_text("one two three", 7), ["one two", "three"])

    def test_split_text_handles_long_word(self):
        self.assertEqual(split_text("abcdefgh", 3), ["abc", "def", "gh"])

    def test_env_int(self):
        os.environ["TEST_INTEGER"] = "42"
        self.assertEqual(env_int("TEST_INTEGER", 1), 42)


class SendTextTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_transcript_reuses_status_message(self):
        message, status = AsyncMock(), AsyncMock()

        await send_long_text(message, status, "им не понравился")

        status.edit_text.assert_awaited_once_with("им не понравился")
        message.reply.assert_not_awaited()

    async def test_long_transcript_sends_remaining_chunks(self):
        message, status = AsyncMock(), AsyncMock()
        text = "а" * 4000 + " " + "б" * 5

        await send_long_text(message, status, text)

        status.edit_text.assert_awaited_once_with("а" * 4000)
        message.reply.assert_awaited_once_with("б" * 5)


if __name__ == "__main__":
    unittest.main()
