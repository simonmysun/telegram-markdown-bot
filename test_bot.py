import unittest
from unittest.mock import ANY, Mock, patch

import urllib.request

from bot import TelegramBot, TelegramError, handle_update


class TelegramBotTest(unittest.TestCase):
    def test_wraps_socket_timeout_as_retryable_telegram_error(self) -> None:
        bot = TelegramBot("token")

        with patch.object(
            urllib.request, "urlopen", side_effect=TimeoutError("timed out")
        ):
            with self.assertRaises(TelegramError) as raised:
                bot.request("getMe")

        self.assertTrue(raised.exception.retryable)
        self.assertIn("timed out", str(raised.exception))

    def test_converts_markdown_before_sending(self) -> None:
        bot = TelegramBot("token")
        bot.request = Mock()
        message = {
            "message_id": 7,
            "chat": {"id": 42},
            "text": "# Title!",
        }

        bot.send_markdown(message)

        bot.request.assert_called_once_with(
            "sendMessage",
            {
                "chat_id": 42,
                "text": "*Title\\!*\n\\=\\=\\=",
                "parse_mode": "MarkdownV2",
                "reply_parameters": {"message_id": 7},
            },
        )

    def test_answers_inline_query_with_converted_markdown(self) -> None:
        bot = TelegramBot("token")
        bot.request = Mock()

        bot.answer_inline_query(
            {"id": "inline-1", "from": {"id": 123}, "query": "# Title!"}
        )

        bot.request.assert_called_once_with(
            "answerInlineQuery",
            {
                "inline_query_id": "inline-1",
                "results": [
                    {
                        "type": "article",
                        "id": ANY,
                        "title": "发送 Markdown",
                        "description": "# Title!",
                        "input_message_content": {
                            "message_text": "*Title\\!*\n\\=\\=\\=",
                            "parse_mode": "MarkdownV2",
                        },
                    }
                ],
                "cache_time": 0,
                "is_personal": True,
            },
        )

    def test_answers_empty_inline_query_without_results(self) -> None:
        bot = TelegramBot("token")
        bot.request = Mock()

        bot.answer_inline_query({"id": "inline-1", "query": "  "})

        payload = bot.request.call_args.args[1]
        self.assertEqual(payload["results"], [])


class HandleUpdateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.message = {
            "message_id": 7,
            "chat": {"id": 42},
            "from": {"id": 123},
            "text": "*bold*",
        }
        self.bot = Mock()
        self.bot.allowed_users = None

    def test_echoes_text_as_markdown(self) -> None:
        handle_update(self.bot, {"message": self.message})

        self.bot.send_markdown.assert_called_once_with(self.message)
        self.bot.send_error.assert_not_called()

    def test_ignores_non_text_messages(self) -> None:
        handle_update(self.bot, {"message": {"sticker": {"file_id": "x"}}})

        self.bot.send_markdown.assert_not_called()

    def test_reports_markdown_errors(self) -> None:
        self.bot.send_markdown.side_effect = TelegramError(
            "Bad Request: can't parse entities"
        )

        handle_update(self.bot, {"message": self.message})

        self.bot.send_error.assert_called_once_with(
            self.message, "Bad Request: can't parse entities"
        )

    def test_propagates_retryable_send_errors(self) -> None:
        self.bot.send_markdown.side_effect = TelegramError(
            "Network error: timed out", retryable=True
        )

        with self.assertRaises(TelegramError):
            handle_update(self.bot, {"message": self.message})

        self.bot.send_error.assert_not_called()

    def test_ignores_users_outside_allowlist(self) -> None:
        self.bot.allowed_users = {456}

        handle_update(self.bot, {"message": self.message})

        self.bot.send_markdown.assert_not_called()

    def test_accepts_users_in_allowlist(self) -> None:
        self.bot.allowed_users = {123}

        handle_update(self.bot, {"message": self.message})

        self.bot.send_markdown.assert_called_once_with(self.message)

    def test_legacy_command_sends_raw_legacy_markdown(self) -> None:
        self.message["text"] = "/legacy *bold* _italic_"

        handle_update(self.bot, {"message": self.message})

        self.bot.send_legacy.assert_called_once_with(
            self.message, "*bold* _italic_"
        )
        self.bot.send_markdown.assert_not_called()

    def test_legacy_command_uses_replied_message(self) -> None:
        self.message["text"] = "/legacy"
        self.message["reply_to_message"] = {"text": "*bold*"}

        handle_update(self.bot, {"message": self.message})

        self.bot.send_legacy.assert_called_once_with(self.message, "*bold*")

    def test_legacy_command_without_content_sends_usage(self) -> None:
        self.message["text"] = "/legacy"

        handle_update(self.bot, {"message": self.message})

        self.bot.send_text.assert_called_once_with(
            self.message,
            "用法：/legacy <Markdown>，或回复一条文本后发送 /legacy",
        )

    def test_answers_authorized_inline_query(self) -> None:
        inline_query = {"id": "inline-1", "from": {"id": 123}, "query": "text"}
        self.bot.allowed_users = {123}

        handle_update(self.bot, {"inline_query": inline_query})

        self.bot.answer_inline_query.assert_called_once_with(inline_query)

    def test_hides_inline_results_from_unauthorized_users(self) -> None:
        inline_query = {"id": "inline-1", "from": {"id": 456}, "query": "text"}
        self.bot.allowed_users = {123}

        handle_update(self.bot, {"inline_query": inline_query})

        self.bot.answer_inline_query.assert_not_called()
        self.bot.request.assert_called_once_with(
            "answerInlineQuery",
            {
                "inline_query_id": "inline-1",
                "results": [],
                "cache_time": 0,
                "is_personal": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
