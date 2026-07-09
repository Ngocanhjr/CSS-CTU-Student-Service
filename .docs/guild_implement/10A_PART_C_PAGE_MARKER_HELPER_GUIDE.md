# 10A. Part C - Hướng Dẫn Tách Page Marker Helper

**Last Updated:** 2026-06-24

File này tách riêng logic parse page marker để `chunker.py` sạch hơn và dễ tái sử dụng sau này.

## 1. Mục Tiêu

Tạo helper riêng:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
```

Module này chỉ phụ trách:

```text
- Tim marker dang <!-- page: n --> trong Markdown text.
- Tra ve page range.
- Tach Markdown body thanh PageBlock theo page marker.
- Bat buoc page range khi chunker can tao Chunk hop le.
```

Không làm các việc sau:

```text
- Khong doc file Markdown.
- Khong parse YAML frontmatter.
- Khong split chunk.
- Khong tao Chunk.
- Khong ghi DB.
```

## 2. Contract

Page marker chuẩn:

```markdown
<!-- page: 1 -->
```

Quy ước:

```text
page_start/page_end/token_count khong duoc null trong Chunk.
Neu khong tim duoc page marker va khong co fallback, helper phai raise ValueError.
Khong tao module rieng page_blocks.py; PageBlock nam chung trong page_markers.py.
```

## 3. File Cần Tạo

```text
chatbot/backend/app/ingestion/parsing/__init__.py
chatbot/backend/app/ingestion/parsing/page_markers.py
chatbot/backend/test/ingestion/test_page_markers.py
```

## 4. Implementation Đề Xuất

```python
from __future__ import annotations

from dataclasses import dataclass
import re

PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->", re.IGNORECASE)


@dataclass(frozen=True)
class PageBlock:
    page_number: int
    content: str


def extract_page_numbers(text: str) -> list[int]:
    return [int(match.group(1)) for match in PAGE_RE.finditer(text)]


def extract_page_range(text: str) -> tuple[int | None, int | None]:
    pages = extract_page_numbers(text)
    if not pages:
        return None, None
    return min(pages), max(pages)


def require_page_range(
    text: str,
    *,
    fallback: tuple[int, int] | None = None,
) -> tuple[int, int]:
    page_start, page_end = extract_page_range(text)
    if page_start is not None and page_end is not None:
        return page_start, page_end
    if fallback is not None:
        return fallback
    raise ValueError("Chunk content requires page marker before chunking")


def split_body_by_page_markers(body: str) -> list[PageBlock]:
    matches = list(PAGE_RE.finditer(body))
    if not matches:
        raise ValueError("Markdown body requires page marker before chunking")

    blocks: list[PageBlock] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        if content:
            blocks.append(PageBlock(page_number=page_number, content=content))

    return blocks
```

## 5. Cách Dùng Trong Chunker

Trong `chatbot/backend/app/ingestion/chunking/chunker.py`, import helper:

```python
from app.ingestion.parsing.page_markers import require_page_range
```

Trong `chatbot/backend/app/ingestion/chunking/parent_chunker.py`, import page block helper:

```python
from app.ingestion.parsing.page_markers import split_body_by_page_markers
```

Parent section:

```python
page_start, page_end = require_page_range(content)
```

Child chunk:

```python
page_start, page_end = require_page_range(
    text,
    fallback=(section.page_start, section.page_end),
)
```

## 6. Test Cần Có

File:

```text
chatbot/backend/test/ingestion/test_page_markers.py
```

Tests:

```python
import pytest

from app.ingestion.parsing.page_markers import (
    extract_page_numbers,
    extract_page_range,
    require_page_range,
    split_body_by_page_markers,
)


def test_extract_page_numbers():
    text = "<!-- page: 2 -->\nNoi dung\n<!-- page: 5 -->"

    assert extract_page_numbers(text) == [2, 5]


def test_extract_page_range():
    text = "<!-- page: 5 -->\nNoi dung\n<!-- page: 2 -->"

    assert extract_page_range(text) == (2, 5)


def test_extract_page_range_missing_marker():
    assert extract_page_range("No marker") == (None, None)


def test_require_page_range_uses_fallback():
    assert require_page_range("No marker", fallback=(3, 4)) == (3, 4)


def test_require_page_range_rejects_missing_marker_without_fallback():
    with pytest.raises(ValueError, match="page marker"):
        require_page_range("No marker")


def test_split_body_by_page_markers():
    text = "<!-- page: 1 -->\nA\n<!-- page: 2 -->\nB"

    blocks = split_body_by_page_markers(text)

    assert [block.page_number for block in blocks] == [1, 2]
    assert "A" in blocks[0].content
    assert "B" in blocks[1].content
```

## 7. Done Khi

- [ ] Có `app/ingestion/parsing/page_markers.py`.
- [ ] `page_markers.py` chứa `PageBlock`.
- [ ] `page_markers.py` chứa `split_body_by_page_markers()`.
- [ ] Chunker import `require_page_range` từ helper, không tự định nghĩa regex riêng.
- [ ] Parent chunker import `split_body_by_page_markers` từ helper.
- [ ] Markdown reader vẫn giữ nguyên marker `<!-- page: n -->` trong body.
- [ ] Tests page marker pass.
- [ ] Tests chunker pass.
