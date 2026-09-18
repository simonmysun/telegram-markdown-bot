#!/usr/bin/env python3

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from markdown_converter import convert_markdown_to_html


LOG = logging.getLogger("telegram-markdown-bot")


class TelegramError(Exception):
    def __init__(
        self,
        description: str,
        retry_after: int | None = None,
        error_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(description)
        self.retry_after = retry_after
        self.error_code = error_code
        self.retryable = retryable


class TelegramBot:
    def __init__(
        self,
        token: str,
        allowed_users: set[int] | None = None,
    ) -> None:
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.allowed_users = allowed_users

    def request(
        self, method: str, payload: dict[str, Any] | None = None
    ) -> Any:
        request = urllib.request.Request(
            f"{self.api_url}/{method}",
            data=json.dumps(payload or {}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            try:
                result = json.load(error)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise TelegramError(
                    f"Telegram HTTP error {error.code}",
                    error_code=error.code,
                    retryable=error.code == 429 or error.code >= 500,
                ) from error
        except urllib.error.URLError as error:
            raise TelegramError(
                f"Network error: {error.reason}", retryable=True
            ) from error
        except TimeoutError as error:
            raise TelegramError(f"Network error: {error}", retryable=True) from error

        if not result.get("ok"):
            parameters = result.get("parameters", {})
            error_code = result.get("error_code")
            raise TelegramError(
                result.get("description", "Unknown Telegram API error"),
                parameters.get("retry_after"),
                error_code,
                bool(parameters.get("retry_after"))
                or error_code == 429
                or (error_code is not None and error_code >= 500),
            )
        return result["result"]

    def send_text(self, message: dict[str, Any], text: str) -> None:
        payload: dict[str, Any] = {
            "chat_id": message["chat"]["id"],
            "text": text,
            "reply_parameters": {"message_id": message["message_id"]},
        }
        if thread_id := message.get("message_thread_id"):
            payload["message_thread_id"] = thread_id
        self.request("sendMessage", payload)

    def send_markdown(self, message: dict[str, Any]) -> None:
        payload: dict[str, Any] = {
            "chat_id": message["chat"]["id"],
            "rich_message": {"markdown": message["text"]},
            "reply_parameters": {"message_id": message["message_id"]},
        }
        if thread_id := message.get("message_thread_id"):
            payload["message_thread_id"] = thread_id
        self.request("sendRichMessage", payload)

    def send_error(self, message: dict[str, Any], description: str) -> None:
        self.send_text(message, f"Markdown 解析失败：{description}")

    def answer_inline_query(self, inline_query: dict[str, Any]) -> None:
        query = inline_query.get("query", "").strip()
        results: list[dict[str, Any]] = []
        if query:
            results.append(
                {
                    "type": "article",
                    "id": hashlib.sha256(query.encode()).hexdigest(),
                    "title": "发送 Markdown（兼容模式）",
                    "description": query[:100],
                    "input_message_content": {
                        "message_text": convert_markdown_to_html(query),
                        "parse_mode": "HTML",
                    },
                }
            )
        self.request(
            "answerInlineQuery",
            {
                "inline_query_id": inline_query["id"],
                "results": results,
                "cache_time": 0,
                "is_personal": True,
            },
        )


def handle_update(bot: TelegramBot, update: dict[str, Any]) -> None:
    inline_query = update.get("inline_query")
    if inline_query:
        user_id = inline_query.get("from", {}).get("id")
        if bot.allowed_users is not None and user_id not in bot.allowed_users:
            LOG.info("Ignoring inline query from unauthorized user %s", user_id)
            bot.request(
                "answerInlineQuery",
                {
                    "inline_query_id": inline_query["id"],
                    "results": [],
                    "cache_time": 0,
                    "is_personal": True,
                },
            )
            return
        bot.answer_inline_query(inline_query)
        return

    message = update.get("message")
    if not message or not isinstance(message.get("text"), str):
        return
    user_id = message.get("from", {}).get("id")
    if bot.allowed_users is not None and user_id not in bot.allowed_users:
        LOG.info("Ignoring message from unauthorized user %s", user_id)
        return

    try:
        bot.send_markdown(message)
    except TelegramError as error:
        if error.retryable:
            raise
        LOG.warning("Could not send message %s: %s", message["message_id"], error)
        description = str(error).lower()
        formatting_error = any(
            text in description
            for text in (
                "can't parse",
                "failed to parse",
                "entity url",
                "wrong http url",
            )
        )
        if not formatting_error:
            return
        try:
            bot.send_error(message, str(error))
        except TelegramError as send_error:
            LOG.error("Could not send error response: %s", send_error)


def process_update(bot: TelegramBot, update: dict[str, Any]) -> None:
    try:
        handle_update(bot, update)
    except TelegramError as error:
        if error.retryable:
            raise
        LOG.warning("Skipping update %s: %s", update.get("update_id"), error)


def run(bot: TelegramBot) -> None:
    bot_user = bot.request("getMe")
    LOG.info("Running as @%s", bot_user.get("username"))

    offset: int | None = None
    while True:
        try:
            payload: dict[str, Any] = {
                "timeout": 30,
                "allowed_updates": ["message", "inline_query"],
            }
            if offset is not None:
                payload["offset"] = offset
            updates = bot.request(
                "getUpdates",
                payload,
            )
            for update in updates:
                process_update(bot, update)
                offset = update["update_id"] + 1
        except TelegramError as error:
            delay = error.retry_after or 3
            LOG.warning("Telegram request failed; retrying in %ss: %s", delay, error)
            time.sleep(delay)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")

    allowed_users_value = os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").strip()
    try:
        allowed_users = (
            {int(user_id.strip()) for user_id in allowed_users_value.split(",")}
            if allowed_users_value
            else None
        )
    except ValueError:
        raise SystemExit(
            "ALLOWED_TELEGRAM_USER_IDS must contain comma-separated Telegram user IDs"
        )

    try:
        run(TelegramBot(token, allowed_users))
    except KeyboardInterrupt:
        LOG.info("Stopped")


if __name__ == "__main__":
    main()
