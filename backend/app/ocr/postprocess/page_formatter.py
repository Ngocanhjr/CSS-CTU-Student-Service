from __future__ import annotations

"""Render các trang LlamaParse với page marker ổn định."""

import re

from ..engines.llamaparse_engine import ParsedPage


PAGE_MARKER_RE = re.compile(r"<!--\s*page\s*:\s*\d+\s*-->", re.IGNORECASE)
EXTRACTION_MARKER_RE = re.compile(
    r"<!--\s*extraction\s*:\s*[^>]+-->", re.IGNORECASE
)
PAGE_BREAK_RE = re.compile(r"<!--\s*page-break\s*-->", re.IGNORECASE)


def strip_page_markers(markdown: str) -> str:
    """Xóa marker cũ trước khi render lại một trang."""

    text = PAGE_BREAK_RE.sub("", markdown)
    text = PAGE_MARKER_RE.sub("", text)
    text = EXTRACTION_MARKER_RE.sub("", text)
    return re.sub(r"^\s*\d+\s*\n+", "", text).strip()


def render_pages(pages: list[ParsedPage]) -> str:
    """Render HTML page marker và dấu phân cách từ trang hai."""

    chunks: list[str] = []
    for index, page in enumerate(sorted(pages, key=lambda item: item.page_number)):
        parts = [f"<!-- page: {page.page_number} -->", ""]
        if index:
            parts[:0] = ["---", ""]
        parts.append(strip_page_markers(page.text))
        chunks.append("\n".join(parts).rstrip())
    return "\n\n".join(chunks).rstrip() + "\n"
