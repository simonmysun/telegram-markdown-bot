import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

import mistune


Token = dict[str, Any]

_SPECIAL_CHARACTERS = re.compile(r"([\\_*\[\]()~`>#+\-=|{}.!])")
_LANGUAGE = re.compile(r"[^A-Za-z0-9_+-]")
_MARKDOWN = mistune.create_markdown(
    renderer="ast",
    plugins=[
        "abbr",
        "def_list",
        "footnotes",
        "insert",
        "mark",
        "math",
        "spoiler",
        "strikethrough",
        "subscript",
        "superscript",
        "table",
        "task_lists",
        "url",
    ],
)


def escape_text(text: str) -> str:
    return _SPECIAL_CHARACTERS.sub(r"\\\1", text)


def escape_code(text: str) -> str:
    return text.replace("\\", "\\\\").replace("`", "\\`")


def escape_url(url: str) -> str:
    return url.replace("\\", "\\\\").replace(")", "\\)")


def _plain_text(tokens: list[Token]) -> str:
    parts: list[str] = []
    for token in tokens:
        token_type = token["type"]
        if token_type in {"linebreak", "softbreak"}:
            parts.append("\n")
        elif token_type in {"link", "image"}:
            label = _plain_text(token.get("children", [])) or "Image"
            url = token.get("attrs", {}).get("url", "")
            prefix = "Image: " if token_type == "image" else ""
            parts.append(f"{prefix}{label} ({url})")
        elif "children" in token:
            parts.append(_plain_text(token["children"]))
        elif "raw" in token:
            parts.append(str(token["raw"]))
    return "".join(parts)


def _contains_type(tokens: list[Token], token_types: set[str]) -> bool:
    return any(
        token.get("type") in token_types
        or _contains_type(token.get("children", []), token_types)
        for token in tokens
    )


def _plain_blocks(tokens: list[Token]) -> str:
    blocks: list[str] = []
    for token in tokens:
        token_type = token.get("type")
        if token_type == "blank_line":
            continue
        if token_type in {"block_quote", "block_spoiler"}:
            content = _plain_blocks(token.get("children", []))
        elif token_type in {"block_code", "block_math"}:
            content = token.get("raw", "").rstrip("\n")
        else:
            content = _plain_text(token.get("children", []))
            if not content:
                content = str(token.get("raw", ""))
        if content:
            blocks.append(content)
    return "\n".join(blocks)


def _valid_telegram_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.hostname)
    if parsed.scheme == "tg":
        return bool(parsed.netloc or parsed.path)
    if parsed.scheme == "mailto":
        return "@" in parsed.path
    return False


def _display_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        for character in text
    )


def _pad(text: str, width: int, alignment: str | None) -> str:
    remaining = max(0, width - _display_width(text))
    if alignment == "right":
        return " " * remaining + text
    if alignment == "center":
        left = remaining // 2
        return " " * left + text + " " * (remaining - left)
    return text + " " * remaining


class TelegramMarkdownRenderer:
    def render(self, tokens: list[Token]) -> str:
        blocks = [self.render_block(token) for token in tokens]
        return "\n\n".join(block for block in blocks if block).strip()

    def render_inline(
        self, tokens: list[Token], *, suppress_bold: bool = False
    ) -> str:
        parts: list[str] = []
        for token in tokens:
            token_type = token["type"]
            children = token.get("children", [])

            if token_type == "text":
                parts.append(escape_text(token.get("raw", "")))
            elif token_type in {"linebreak", "softbreak"}:
                parts.append("\n")
            elif token_type == "strong":
                content = self.render_inline(children, suppress_bold=suppress_bold)
                unsafe = _contains_type(children, {"codespan", "inline_math", "block_math"})
                parts.append(content if suppress_bold or unsafe else f"*{content}*")
            elif token_type == "emphasis":
                content = self.render_inline(children)
                unsafe = _contains_type(
                    children, {"codespan", "inline_math", "block_math", "insert"}
                )
                parts.append(content if unsafe else f"_{content}_")
            elif token_type == "strikethrough":
                content = self.render_inline(children)
                unsafe = _contains_type(children, {"codespan", "inline_math", "block_math"})
                parts.append(content if unsafe else f"~{content}~")
            elif token_type == "insert":
                content = self.render_inline(children)
                unsafe = _contains_type(
                    children, {"codespan", "inline_math", "block_math", "emphasis"}
                )
                parts.append(content if unsafe else f"__{content}__")
            elif token_type == "mark":
                content = self.render_inline(children, suppress_bold=True)
                unsafe = _contains_type(children, {"codespan", "inline_math", "block_math"})
                parts.append(content if suppress_bold or unsafe else f"*{content}*")
            elif token_type == "inline_spoiler":
                content = self.render_inline(children)
                unsafe = _contains_type(children, {"codespan", "inline_math", "block_math"})
                parts.append(content if unsafe else f"||{content}||")
            elif token_type == "codespan":
                parts.append(f"`{escape_code(token.get('raw', ''))}`")
            elif token_type in {"inline_math", "block_math"}:
                parts.append(f"`{escape_code(token.get('raw', ''))}`")
            elif token_type == "link":
                label = self.render_inline(children)
                raw_url = token.get("attrs", {}).get("url", "")
                if _valid_telegram_url(raw_url) and not _contains_type(
                    children, {"codespan", "inline_math", "block_math"}
                ):
                    parts.append(f"[{label}]({escape_url(raw_url)})")
                else:
                    parts.append(f"{label} \\({escape_text(raw_url)}\\)")
            elif token_type == "image":
                label = self.render_inline(children) or "Image"
                raw_url = token.get("attrs", {}).get("url", "")
                image_label = f"Image: {label}"
                if _valid_telegram_url(raw_url):
                    parts.append(f"[{image_label}]({escape_url(raw_url)})")
                else:
                    parts.append(f"{image_label} \\({escape_text(raw_url)}\\)")
            elif token_type == "abbr":
                label = self.render_inline(children)
                title = escape_text(token.get("attrs", {}).get("title", ""))
                parts.append(f"{label} \\({title}\\)")
            elif token_type == "superscript":
                parts.append(f"^\\({self.render_inline(children)}\\)")
            elif token_type == "subscript":
                parts.append(f"\\_\\({self.render_inline(children)}\\)")
            elif token_type == "footnote_ref":
                index = token.get("attrs", {}).get("index", token.get("raw", ""))
                parts.append(f"\\[{index}\\]")
            elif children:
                parts.append(self.render_inline(children))
            else:
                parts.append(escape_text(str(token.get("raw", ""))))
        return "".join(parts)

    def render_block(self, token: Token) -> str:
        token_type = token["type"]
        children = token.get("children", [])

        if token_type in {"blank_line"}:
            return ""
        if token_type in {"paragraph", "block_text"}:
            return self.render_inline(children)
        if token_type == "heading":
            level = token.get("attrs", {}).get("level", 3)
            title = self.render_inline(children, suppress_bold=True)
            decorated_title = (
                title
                if _contains_type(children, {"codespan", "inline_math", "block_math"})
                else f"*{title}*"
            )
            if level == 1:
                return f"{decorated_title}\n\\=\\=\\="
            if level == 2:
                return f"{decorated_title}\n\\-\\-\\-"
            return decorated_title
        if token_type == "thematic_break":
            return "──────────"
        if token_type == "block_code":
            info = token.get("attrs", {}).get("info", "").split(maxsplit=1)[0]
            language = _LANGUAGE.sub("", info)
            code = escape_code(token.get("raw", "").rstrip("\n"))
            return f"```{language}\n{code}\n```"
        if token_type == "block_math":
            code = escape_code(token.get("raw", "").rstrip("\n"))
            return f"```\n{code}\n```"
        if token_type == "block_quote":
            if _contains_type(children, {"codespan", "inline_math", "block_math", "block_code"}):
                content = escape_text(_plain_blocks(children))
            else:
                content = self.render(children)
            lines: list[str] = []
            for line in content.splitlines():
                while line.startswith("> "):
                    line = line[2:]
                if line:
                    lines.append(f"> {line}")
            return "\n".join(lines)
        if token_type == "block_spoiler":
            content = self.render(children)
            if _contains_type(children, {"codespan", "inline_math", "block_math", "block_code"}):
                return content
            return f"||{content}||"
        if token_type == "list":
            return self.render_list(token, token.get("attrs", {}).get("depth", 0))
        if token_type == "table":
            return self.render_table(token)
        if token_type == "def_list":
            return self.render_definition_list(children)
        if token_type == "footnotes":
            return self.render_footnotes(children)
        if token_type in {"block_html", "raw_html"}:
            return escape_text(token.get("raw", "").strip())
        if children:
            return self.render(children)
        return escape_text(str(token.get("raw", "")).strip())

    def render_list(self, token: Token, depth: int) -> str:
        attrs = token.get("attrs", {})
        ordered = attrs.get("ordered", False)
        start = attrs.get("start", 1)
        lines: list[str] = []

        for index, item in enumerate(token.get("children", [])):
            is_task = item.get("type") == "task_list_item"
            if is_task:
                marker = "☑" if item.get("attrs", {}).get("checked") else "☐"
            elif ordered:
                marker = f"{start + index}\\."
            else:
                marker = "•"

            content_blocks: list[str] = []
            nested_lists: list[str] = []
            for child in item.get("children", []):
                if child.get("type") == "list":
                    nested_lists.append(self.render_list(child, depth + 1))
                elif child.get("type") == "block_quote":
                    rendered = "↳ " + escape_text(_plain_blocks(child.get("children", [])))
                    content_blocks.append(rendered)
                else:
                    rendered = self.render_block(child)
                    if rendered:
                        content_blocks.append(rendered)

            content = "\n\n".join(content_blocks)
            indent = "  " * depth
            continuation = indent + "  "
            content_lines = content.splitlines() or [""]
            lines.append(f"{indent}{marker} {content_lines[0]}")
            lines.extend(f"{continuation}{line}" for line in content_lines[1:])
            lines.extend(nested_lists)
        return "\n".join(lines)

    def render_table(self, token: Token) -> str:
        rows: list[list[str]] = []
        alignments: list[str | None] = []
        for section in token.get("children", []):
            if section.get("type") == "table_head":
                cells = section.get("children", [])
                rows.append([_plain_text(cell.get("children", [])) for cell in cells])
                alignments = [cell.get("attrs", {}).get("align") for cell in cells]
            elif section.get("type") == "table_body":
                for row in section.get("children", []):
                    rows.append(
                        [
                            _plain_text(cell.get("children", []))
                            for cell in row.get("children", [])
                        ]
                    )

        if not rows:
            return ""
        rows = [
            [cell.replace("\n", " ").replace("|", "│") for cell in row]
            for row in rows
        ]
        column_count = max(len(row) for row in rows)
        widths = [
            max(
                _display_width(row[column]) if column < len(row) else 0
                for row in rows
            )
            for column in range(column_count)
        ]
        alignments.extend([None] * (column_count - len(alignments)))

        projected_size = len(rows) * (sum(widths) + 3 * (column_count - 1))
        align_columns = projected_size <= 3500 and max(widths, default=0) <= 80
        rendered_rows: list[str] = []
        for row_index, row in enumerate(rows):
            if align_columns:
                cells = [
                    _pad(
                        row[column] if column < len(row) else "",
                        widths[column],
                        alignments[column],
                    )
                    for column in range(column_count)
                ]
            else:
                cells = [row[column] if column < len(row) else "" for column in range(column_count)]
            rendered_rows.append(" | ".join(cells).rstrip())
            if row_index == 0:
                separator_widths = widths if align_columns else [3] * column_count
                rendered_rows.append("-+-".join("-" * width for width in separator_widths))
        table = escape_code("\n".join(rendered_rows))
        return f"```\n{table}\n```"

    def render_definition_list(self, tokens: list[Token]) -> str:
        lines: list[str] = []
        for token in tokens:
            if token["type"] == "def_list_head":
                term = self.render_inline(token.get("children", []), suppress_bold=True)
                lines.append(f"*{term}*")
            elif token["type"] == "def_list_item":
                definition = self.render(token.get("children", []))
                lines.extend(f"  {line}" for line in definition.splitlines())
        return "\n".join(lines)

    def render_footnotes(self, tokens: list[Token]) -> str:
        lines: list[str] = []
        for token in tokens:
            index = token.get("attrs", {}).get("index", token.get("attrs", {}).get("key"))
            content = self.render(token.get("children", []))
            content_lines = content.splitlines() or [""]
            lines.append(f"\\[{index}\\] {content_lines[0]}")
            lines.extend(f"    {line}" for line in content_lines[1:])
        return "\n".join(lines)


def convert_markdown(text: str) -> str:
    converted = TelegramMarkdownRenderer().render(_MARKDOWN(text))
    return converted or escape_text(text)
