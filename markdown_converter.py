import html
import re
from typing import Any
from urllib.parse import urlparse

import mistune


Token = dict[str, Any]

_LANGUAGE = re.compile(r"[^A-Za-z0-9_+-]")
_SPOILER = re.compile(r"\|\|(.+?)\|\|")
_MARKDOWN = mistune.create_markdown(
    renderer="ast",
    plugins=["mark", "spoiler", "strikethrough", "table", "task_lists", "url"],
)


def _escape(text: object) -> str:
    return html.escape(str(text), quote=False)


def _render_text(text: object) -> str:
    raw = str(text)
    parts: list[str] = []
    position = 0
    for match in _SPOILER.finditer(raw):
        parts.append(_escape(raw[position : match.start()]))
        parts.append(f"<tg-spoiler>{_escape(match.group(1))}</tg-spoiler>")
        position = match.end()
    parts.append(_escape(raw[position:]))
    return "".join(parts)


def _contains_code(tokens: list[Token]) -> bool:
    return any(
        token.get("type") in {"codespan", "block_code"}
        or _contains_code(token.get("children", []))
        for token in tokens
    )


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.hostname)
    if parsed.scheme == "tg":
        return bool(parsed.netloc or parsed.path)
    if parsed.scheme == "mailto":
        return "@" in parsed.path
    if parsed.scheme == "tel":
        return bool(parsed.path)
    return False


class TelegramHTMLRenderer:
    def render(self, tokens: list[Token]) -> str:
        return "\n\n".join(
            rendered
            for token in tokens
            if (rendered := self.render_block(token))
        ).strip()

    def render_inline(self, tokens: list[Token]) -> str:
        parts: list[str] = []
        for token in tokens:
            token_type = token["type"]
            children = token.get("children", [])

            if token_type == "text":
                parts.append(_render_text(token.get("raw", "")))
            elif token_type in {"linebreak", "softbreak"}:
                parts.append("\n")
            elif token_type == "strong":
                content = self.render_inline(children)
                parts.append(content if _contains_code(children) else f"<b>{content}</b>")
            elif token_type == "emphasis":
                content = self.render_inline(children)
                parts.append(content if _contains_code(children) else f"<i>{content}</i>")
            elif token_type == "strikethrough":
                content = self.render_inline(children)
                parts.append(content if _contains_code(children) else f"<s>{content}</s>")
            elif token_type == "inline_spoiler":
                content = self.render_inline(children)
                parts.append(
                    content if _contains_code(children) else f"<tg-spoiler>{content}</tg-spoiler>"
                )
            elif token_type == "mark":
                content = self.render_inline(children)
                parts.append(content if _contains_code(children) else f"<b>{content}</b>")
            elif token_type == "codespan":
                parts.append(f"<code>{_escape(token.get('raw', ''))}</code>")
            elif token_type == "link":
                label = self.render_inline(children)
                url = str(token.get("attrs", {}).get("url", ""))
                if _valid_url(url) and not _contains_code(children):
                    parts.append(f'<a href="{html.escape(url, quote=True)}">{label}</a>')
                else:
                    parts.append(f"{label} ({_escape(url)})")
            elif token_type == "image":
                label = self.render_inline(children) or "Image"
                url = str(token.get("attrs", {}).get("url", ""))
                if _valid_url(url):
                    parts.append(
                        f'<a href="{html.escape(url, quote=True)}">Image: {label}</a>'
                    )
                else:
                    parts.append(f"Image: {label} ({_escape(url)})")
            elif children:
                parts.append(self.render_inline(children))
            else:
                parts.append(_escape(token.get("raw", "")))
        return "".join(parts)

    def render_block(self, token: Token) -> str:
        token_type = token["type"]
        children = token.get("children", [])

        if token_type == "blank_line":
            return ""
        if token_type in {"paragraph", "block_text"}:
            return self.render_inline(children)
        if token_type == "heading":
            return f"<b>{self.render_inline(children)}</b>"
        if token_type == "thematic_break":
            return "──────────"
        if token_type == "block_code":
            info = str(token.get("attrs", {}).get("info", "")).split(maxsplit=1)[0]
            language = _LANGUAGE.sub("", info)
            code = _escape(str(token.get("raw", "")).rstrip("\n"))
            class_name = f' class="language-{language}"' if language else ""
            return f"<pre><code{class_name}>{code}</code></pre>"
        if token_type == "block_quote":
            return f"<blockquote>{self.render(children)}</blockquote>"
        if token_type == "list":
            return self.render_list(token)
        if token_type == "table":
            rows: list[str] = []
            for section in children:
                section_rows = (
                    [section] if section.get("type") == "table_head" else section.get("children", [])
                )
                for row in section_rows:
                    cells = [
                        self.render_inline(cell.get("children", []))
                        for cell in row.get("children", [])
                    ]
                    rows.append(" | ".join(cells))
            return f"<pre>{'\n'.join(rows)}</pre>" if rows else ""
        if children:
            return self.render(children)
        return _escape(token.get("raw", "")).strip()

    def render_list(self, token: Token) -> str:
        attrs = token.get("attrs", {})
        ordered = attrs.get("ordered", False)
        start = attrs.get("start", 1)
        lines: list[str] = []
        for index, item in enumerate(token.get("children", [])):
            if item.get("type") == "task_list_item":
                marker = "☑" if item.get("attrs", {}).get("checked") else "☐"
            elif ordered:
                marker = f"{start + index}."
            else:
                marker = "•"
            content = self.render(item.get("children", []))
            lines.append(f"{marker} {content}")
        return "\n".join(lines)


def convert_markdown_to_html(text: str) -> str:
    return TelegramHTMLRenderer().render(_MARKDOWN(text)) or _escape(text)
