import unittest

from markdown_converter import convert_markdown_to_html


class TelegramHTMLConversionTest(unittest.TestCase):
    def test_converts_common_inline_formatting(self) -> None:
        source = (
            "**bold** *italic* ~~gone~~ ||secret|| `code` "
            "[link](https://example.com?a=1&b=2)"
        )

        self.assertEqual(
            convert_markdown_to_html(source),
            '<b>bold</b> <i>italic</i> <s>gone</s> '
            '<tg-spoiler>secret</tg-spoiler> <code>code</code> '
            '<a href="https://example.com?a=1&amp;b=2">link</a>',
        )

    def test_converts_blocks_and_escapes_plain_text(self) -> None:
        source = "# Title\n\n- one\n- two\n\n> a < b"

        self.assertEqual(
            convert_markdown_to_html(source),
            "<b>Title</b>\n\n• one\n• two\n\n<blockquote>a &lt; b</blockquote>",
        )

    def test_does_not_create_unsafe_relative_link(self) -> None:
        self.assertEqual(
            convert_markdown_to_html("[docs](docs/readme.md)"),
            "docs (docs/readme.md)",
        )


if __name__ == "__main__":
    unittest.main()
