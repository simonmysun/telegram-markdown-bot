import unittest

from markdown_converter import convert_markdown, escape_code, escape_text, escape_url


class EscapingTest(unittest.TestCase):
    def test_escapes_all_markdown_v2_plain_text_characters(self) -> None:
        source = r"\_*[]()~`>#+-=|{}.!"
        expected = r"\\\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"

        self.assertEqual(escape_text(source), expected)

    def test_code_only_escapes_backticks_and_backslashes(self) -> None:
        self.assertEqual(escape_code(r"a\b`c.txt"), r"a\\b\`c.txt")

    def test_url_only_escapes_closing_parentheses_and_backslashes(self) -> None:
        self.assertEqual(escape_url(r"https://x/a\b_(c)"), r"https://x/a\\b_(c\)")


class BlockConversionTest(unittest.TestCase):
    def test_converts_headings(self) -> None:
        source = "# H1\n## H2\n### H3\n#### H4"

        self.assertEqual(
            convert_markdown(source),
            "*H1*\n\\=\\=\\=\n\n"
            "*H2*\n\\-\\-\\-\n\n"
            "*H3*\n\n"
            "*H4*",
        )
        self.assertEqual(convert_markdown("# ==Marked=="), "*Marked*\n\\=\\=\\=")

    def test_converts_ordered_unordered_and_task_lists(self) -> None:
        source = "3. three\n4. four\n   - nested\n   - [x] done\n   - [ ] todo"

        self.assertEqual(
            convert_markdown(source),
            "3\\. three\n"
            "4\\. four\n"
            "  • nested\n"
            "  ☑ done\n"
            "  ☐ todo",
        )

    def test_converts_quotes_and_thematic_breaks(self) -> None:
        source = "> first!\n> second\n\n---"

        self.assertEqual(
            convert_markdown(source), "> first\\!\n> second\n\n──────────"
        )

    def test_converts_code_blocks_and_math(self) -> None:
        source = "```python\na\\b`c\n```\n\n$$\nx+y\n$$"

        self.assertEqual(
            convert_markdown(source),
            "```python\na\\\\b\\`c\n```\n\n```\nx+y\n```",
        )

    def test_converts_table_to_aligned_code_block(self) -> None:
        source = "| 名称 | Value |\n| --- | ---: |\n| 测试 | 42 |"

        self.assertEqual(
            convert_markdown(source),
            "```\n名称 | Value\n-----+------\n测试 |    42\n```",
        )


class InlineConversionTest(unittest.TestCase):
    def test_converts_formatting_links_images_and_code(self) -> None:
        source = (
            "**bold** *italic* ~~gone~~ ^^under^^ ==mark== "
            "[site](https://example.com/a_(b)) ![logo](logo.png) `a\\b`"
        )

        self.assertEqual(
            convert_markdown(source),
            "*bold* _italic_ ~gone~ __under__ *mark* "
            "[site](https://example.com/a_(b\\)) "
            "Image: logo \\(logo\\.png\\) `a\\\\b`",
        )

    def test_drops_conflicting_outer_styles_around_code(self) -> None:
        self.assertEqual(convert_markdown("**before `code` after**"), "before `code` after")
        self.assertEqual(convert_markdown("^^*x*^^"), "_x_")
        self.assertEqual(convert_markdown("*^^x^^*"), "__x__")

    def test_degrades_relative_links_to_safe_plain_text(self) -> None:
        self.assertEqual(
            convert_markdown("[docs](docs/readme.md) ![logo](logo.png)"),
            "docs \\(docs/readme\\.md\\) Image: logo \\(logo\\.png\\)",
        )

    def test_flattens_nested_quotes_and_quotes_inside_lists(self) -> None:
        self.assertEqual(
            convert_markdown("> outer\n> > inner"), "> outer\n> inner"
        )
        self.assertEqual(convert_markdown("- > quoted"), "• ↳ quoted")

    def test_formats_inline_double_dollar_math_as_code(self) -> None:
        self.assertEqual(
            convert_markdown("before $$x+y$$ after"), "before `x+y` after"
        )

    def test_wide_tables_do_not_expand_beyond_input_size(self) -> None:
        first = "a" * 1800
        second = "b" * 1800
        source = f"| A | B |\n|---|---|\n| {first} | x |\n| x | {second} |"

        self.assertLessEqual(len(convert_markdown(source)), len(source) + 20)

    def test_converts_extended_structures(self) -> None:
        source = (
            "Term\n: definition\n\n"
            "Foot[^a]\n\n[^a]: note\n\n"
            "$x+y$ and >!secret!<"
        )

        self.assertEqual(
            convert_markdown(source),
            "*Term*\n  definition\n\n"
            "Foot\\[1\\]\n\n"
            "`x+y` and ||secret||\n\n"
            "\\[1\\] note",
        )

    def test_escapes_plain_text_instead_of_treating_it_as_telegram_markup(self) -> None:
        self.assertEqual(
            convert_markdown("Hello - a.b! #1"), "Hello \\- a\\.b\\! \\#1"
        )


if __name__ == "__main__":
    unittest.main()
