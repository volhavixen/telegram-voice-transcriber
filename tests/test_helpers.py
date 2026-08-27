import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123456789:AAExampleTokenForLocalTestsOnly")

from bot import env_int, parse_user_ids, split_text


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


if __name__ == "__main__":
    unittest.main()
