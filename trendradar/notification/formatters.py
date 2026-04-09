# coding=utf-8
"""
通知内容格式转换模块

提供不同推送平台之间的格式转换功能
"""

import re
from typing import Any, Dict, List


_MARKDOWN_OR_URL_PATTERN = re.compile(
    r"\[([^\]]+)\]\((https?://[^)\s]+)\)|(https?://[^\s<>\]]+)"
)
_NUMBERED_ITEM_PATTERN = re.compile(r"^\d+\.\s+")


def strip_markdown(text: str) -> str:
    """去除文本中的 markdown 语法格式，用于个人微信推送"""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", text)

    protected_urls: list[str] = []

    def _protect_url(match: re.Match) -> str:
        protected_urls.append(match.group(0))
        return f"@@URLTOKEN{len(protected_urls) - 1}@@"

    text = re.sub(r"https?://[^\s<>\]]+", _protect_url, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"!\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\-\*]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"<font[^>]*>(.+?)</font>", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    for idx, url in enumerate(protected_urls):
        text = text.replace(f"@@URLTOKEN{idx}@@", url)

    return text.strip()


def _clean_markdown_segment(text: str, *, strip_edges: bool = False) -> str:
    """清理文本片段里的 markdown 标记，但保留原始空格。"""
    text = re.sub(r"!\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"<font[^>]*>(.+?)</font>", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^>\s*", "", text)
    text = re.sub(r"^#+\s*", "", text)
    return text.strip() if strip_edges else text


def _is_separator_line(line: str) -> bool:
    return bool(re.fullmatch(r"[\-\*_]{3,}", line.strip()))


def _is_batch_header(line: str) -> bool:
    return bool(re.fullmatch(r"\[第\s*\d+/\d+\s*批次\]", line.strip()))


def _is_heading_line(raw_line: str, plain_line: str) -> bool:
    raw_line = raw_line.strip()
    plain_line = plain_line.strip()
    if not plain_line:
        return False
    if raw_line.startswith("#"):
        return True
    if raw_line.startswith("**") and raw_line.endswith("**"):
        return True
    if raw_line.startswith("__") and raw_line.endswith("__"):
        return True
    return plain_line.startswith("【") and plain_line.endswith("】")


def _truncate_text(text: str, limit: int = 60) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _is_numbered_item_line(line: str) -> bool:
    return bool(_NUMBERED_ITEM_PATTERN.match(line.strip()))


def _make_text_paragraph(text: str) -> List[Dict[str, str]]:
    return [{"tag": "text", "text": text}]


def _make_blank_paragraph() -> List[Dict[str, str]]:
    return [{"tag": "text", "text": "　"}]


def _is_blank_paragraph(paragraph: List[Dict[str, str]]) -> bool:
    return len(paragraph) == 1 and paragraph[0].get("tag") == "text" and paragraph[0].get("text") == "　"


def _append_blank_paragraph(paragraphs: List[List[Dict[str, str]]]) -> None:
    if not paragraphs or _is_blank_paragraph(paragraphs[-1]):
        return
    paragraphs.append(_make_blank_paragraph())


def _build_link_element(url: str, context_text: str = "") -> Dict[str, str]:
    context_text = context_text.strip()
    label = "点击查看"
    if "原文" in context_text:
        label = "查看原文"
    elif "来源" in context_text:
        label = "查看来源"
    return {"tag": "a", "text": label, "href": url}


def _convert_line_to_feishu_elements(line: str) -> List[Dict[str, str]]:
    elements: List[Dict[str, str]] = []
    cursor = 0

    for match in _MARKDOWN_OR_URL_PATTERN.finditer(line):
        prefix = _clean_markdown_segment(line[cursor:match.start()])
        if prefix.strip():
            elements.append({"tag": "text", "text": prefix})

        markdown_text, markdown_url, bare_url = match.groups()
        if markdown_url:
            link_text = _clean_markdown_segment(markdown_text, strip_edges=True) or "点击查看"
            elements.append({"tag": "a", "text": link_text, "href": markdown_url})
        elif bare_url:
            elements.append(_build_link_element(bare_url, prefix))

        cursor = match.end()

    suffix = _clean_markdown_segment(line[cursor:])
    if suffix.strip():
        elements.append({"tag": "text", "text": suffix})

    if not elements:
        plain_text = _clean_markdown_segment(line, strip_edges=True)
        if plain_text:
            elements.append({"tag": "text", "text": plain_text})

    return elements


def convert_markdown_to_feishu_post(content: str, default_title: str = "TrendRadar") -> Dict[str, Any]:
    """
    将 markdown 内容转换为飞书 post 富文本消息。

    post 的正文更接近普通飞书消息的阅读感受，比 interactive card 更松、更像聊天消息。
    """
    lines = content.replace("\r\n", "\n").split("\n")

    title = default_title
    batch_label = ""
    body_start = 0

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or _is_separator_line(stripped):
            continue

        plain_line = _clean_markdown_segment(stripped, strip_edges=True)
        if not plain_line:
            continue

        if _is_batch_header(plain_line) and not batch_label:
            batch_label = plain_line.strip("[]")
            body_start = idx + 1
            continue

        title = _truncate_text(plain_line)
        body_start = idx + 1
        break

    if batch_label:
        title = _truncate_text(f"{title}（{batch_label}）")

    paragraphs: List[List[Dict[str, str]]] = []
    if batch_label:
        paragraphs.append(_make_text_paragraph(f"【{batch_label}】"))
        paragraphs.append(_make_blank_paragraph())

    blocks: List[tuple[str, Any]] = []
    current_item: List[str] = []

    for line in lines[body_start:]:
        stripped = line.strip()
        if not stripped or _is_separator_line(stripped):
            continue

        plain_line = _clean_markdown_segment(stripped, strip_edges=True)
        if not plain_line:
            continue

        if _is_heading_line(stripped, plain_line):
            if current_item:
                blocks.append(("item", current_item))
                current_item = []
            blocks.append(("heading", plain_line.strip("【】")))
            continue

        if _is_numbered_item_line(plain_line):
            if current_item:
                blocks.append(("item", current_item))
            current_item = [stripped]
            continue

        if current_item:
            current_item.append(stripped)
        else:
            blocks.append(("paragraph", stripped))

    if current_item:
        blocks.append(("item", current_item))

    for idx, (block_type, block_value) in enumerate(blocks):
        if block_type == "heading":
            _append_blank_paragraph(paragraphs)
            paragraphs.append(_make_text_paragraph(f"【{block_value}】"))
            paragraphs.append(_make_blank_paragraph())
            continue

        if block_type == "item":
            for item_line in block_value:
                elements = _convert_line_to_feishu_elements(item_line)
                if elements:
                    paragraphs.append(elements)
            if idx < len(blocks) - 1:
                paragraphs.append(_make_blank_paragraph())
            continue

        elements = _convert_line_to_feishu_elements(block_value)
        if elements:
            paragraphs.append(elements)
            if idx < len(blocks) - 1:
                paragraphs.append(_make_blank_paragraph())

    if not paragraphs:
        paragraphs = [[{"tag": "text", "text": strip_markdown(content) or default_title}]]

    return {
        "zh_cn": {
            "title": title,
            "content": paragraphs,
        }
    }


def convert_markdown_to_mrkdwn(content: str) -> str:
    """
    将标准 Markdown 转换为 Slack 的 mrkdwn 格式

    转换规则：
    - **粗体** -> *粗体*
    - [文本](url) -> <url|文本>
    - 保留其他格式（代码块、列表等）
    """
    content = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", content)
    content = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", content)
    return content
