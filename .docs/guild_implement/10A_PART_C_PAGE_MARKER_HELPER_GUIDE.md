# 10A. Part C - Huong Dan Tach Page Marker Helper

**Last Updated:** 2026-06-24

File nay tach rieng logic parse page marker de `chunker.py` sach hon va de tai su dung sau nay.

## 1. Muc Tieu

Tao helper rieng:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
```

Module nay chi phu trach:

```text
- Tim marker dang <!-- page: n --> trong Markdown text.
- Tra ve page range.
- Bat buoc page range khi chunker can tao Chunk hop le.
```

Khong lam cac viec sau:

```text
- Khong doc file Markdown.
- Khong parse YAML frontmatter.
- Khong split chunk.
- Khong tao Chunk.
- Khong ghi DB.
```

## 2. Contract

Page marker chuan:

```markdown
<!-- page: 1 -->
```

Quy uoc:

```text
page_start/page_end/token_count khong duoc null trong Chunk.
Neu khong tim duoc page marker va khong co fallback, helper phai raise ValueError.
```

## 3. File Can Tao

```text
chatbot/backend/app/ingestion/parsing/__init__.py
chatbot/backend/app/ingestion/parsing/page_markers.py
chatbot/backend/test/ingestion/test_page_markers.py
```

## 4. Implementation De Xuat

```python
from __future__ import annotations

import re

PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->", re.IGNORECASE)


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
```

## 5. Cach Dung Trong Chunker

Trong `chatbot/backend/app/ingestion/chunking/chunker.py`, import helper:

```python
from app.ingestion.parsing.page_markers import require_page_range
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

## 6. Test Can Co

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
```

## 7. Done Khi

- [ ] Co `app/ingestion/parsing/page_markers.py`.
- [ ] Chunker import `require_page_range` tu helper, khong tu dinh nghia regex rieng.
- [ ] Markdown reader van giu nguyen marker `<!-- page: n -->` trong body.
- [ ] Tests page marker pass.
- [ ] Tests chunker pass.
