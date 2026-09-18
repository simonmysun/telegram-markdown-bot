import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock

from bot import TelegramBot


EXAMPLES = Path(__file__).with_name("examples")
RICH_MESSAGE_CHARACTER_LIMIT = 32768


class BalancedHTMLParser(HTMLParser):
    void_elements = {"br", "hr", "img", "input", "tg-map"}

    def __init__(self) -> None:
        super().__init__()
        self.open_tags: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag not in self.void_elements:
            self.open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.open_tags or self.open_tags.pop() != tag:
            self.fail(f"unexpected closing tag </{tag}>")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        pass

    def fail(self, message: str) -> None:
        raise ValueError(message)

    def close(self) -> None:
        super().close()
        if self.open_tags:
            self.fail(f"unclosed tags: {', '.join(self.open_tags)}")


class RichMessageExamplesTest(unittest.TestCase):
    def test_sends_complete_markdown_example_without_modification(self) -> None:
        markdown = (EXAMPLES / "rich-markdown.md").read_text(encoding="utf-8")
        message = {"message_id": 7, "chat": {"id": 42}, "text": markdown}
        bot = TelegramBot("token")
        bot.request = Mock()

        bot.send_markdown(message)

        bot.request.assert_called_once_with(
            "sendRichMessage",
            {
                "chat_id": 42,
                "rich_message": {"markdown": markdown},
                "reply_parameters": {"message_id": 7},
            },
        )

    def test_examples_fit_rich_message_character_limit(self) -> None:
        for path in EXAMPLES.iterdir():
            with self.subTest(path=path.name):
                content = path.read_text(encoding="utf-8")
                self.assertTrue(content)
                self.assertLessEqual(len(content), RICH_MESSAGE_CHARACTER_LIMIT)

    def test_markdown_example_covers_advanced_structures(self) -> None:
        markdown = (EXAMPLES / "rich-markdown.md").read_text(encoding="utf-8")

        for syntax in (
            "# Heading 1",
            "- [x] completed task list item",
            "| Header 1 | Header 2 |",
            "[^id1]: Definition of the first footnote.",
            "$$E = mc^2$$",
            "<details open>",
            "<tg-button-row",
        ):
            with self.subTest(syntax=syntax):
                self.assertIn(syntax, markdown)
        self.assertEqual(markdown.count("```"), 4)

    def test_html_example_is_balanced_and_covers_advanced_structures(self) -> None:
        html = (EXAMPLES / "rich-html.html").read_text(encoding="utf-8")
        parser = BalancedHTMLParser()

        parser.feed(html)
        parser.close()

        for syntax in (
            "<h1>Heading 1</h1>",
            "<blockquote expandable>",
            "<table bordered striped compact>",
            "<tg-math-block>E = mc^2</tg-math-block>",
            "<tg-document ",
            "<tg-button-row",
        ):
            with self.subTest(syntax=syntax):
                self.assertIn(syntax, html)


if __name__ == "__main__":
    unittest.main()
