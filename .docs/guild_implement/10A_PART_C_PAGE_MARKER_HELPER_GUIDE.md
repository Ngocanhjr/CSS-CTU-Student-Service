# 10A. Part C - Hướng Dẫn Tách Page Marker Helper

**Last Updated:** 2026-07-10

File này tách riêng logic parse page marker để `chunker.py` sạch hơn và dễ tái sử dụng sau này.

## 1. Mục Tiêu

Tạo helper riêng:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
```

Module này chỉ phụ trách:

```text
- Tim marker dang <!-- page: n --> trong Markdown text.
- Tach Markdown body thanh PageBlock theo page marker.
- Gan page_number cho PageBlock de structural parser/builders truyen tiep metadata.
- Cung cap extract_page_range/require_page_range chi cho debug hoac legacy caller.
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


PAGE_NUMBER_LINE_RE = re.compile(r"^\s*\d+\s*$")
HORIZONTAL_PAGE_RULE_RE = re.compile(r"^\s*---\s*$")


def strip_page_boundary_artifacts(
    text: str,
    *,
    current_page_number: int,
    next_page_number: int | None,
) -> str:
    """Remove only artifacts that can be tied to an explicit page boundary."""
    lines = text.splitlines()

    while lines and not lines[0].strip():
        lines.pop(0)

    # OCR may repeat the current page number immediately after its marker.
    if lines and lines[0].strip() == str(current_page_number):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)

    while lines and not lines[-1].strip():
        lines.pop()

    # OCR commonly emits "---" and the next page number immediately before
    # the next explicit marker. Remove only this verified boundary suffix.
    if next_page_number is not None and lines and lines[-1].strip() == str(next_page_number):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    if next_page_number is not None and lines and HORIZONTAL_PAGE_RULE_RE.fullmatch(lines[-1]):
        lines.pop()

    return "\n".join(lines).strip()


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
    """Legacy/debug helper; normative chunking propagates page metadata from blocks."""
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
        content_start = match.end()
        content_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(body)
        )
        next_page_number = (
            int(matches[index + 1].group(1))
            if index + 1 < len(matches)
            else None
        )
        content = strip_page_boundary_artifacts(
            body[content_start:content_end],
            current_page_number=page_number,
            next_page_number=next_page_number,
        )
        if content:
            blocks.append(PageBlock(page_number=page_number, content=content))

    return blocks
```

## 5. Cách Dùng Trong Chunker

Chỉ core chunker gọi page marker helper trước structural parser:

```python
from app.ingestion.parsing.page_markers import split_body_by_page_markers

page_blocks = split_body_by_page_markers(markdown_body)
parse_result = parse_page_blocks(page_blocks)
```

Không gọi `split_body_by_page_markers()` trong `parent_chunker.py` hoặc `child_chunker.py`.

`extract_page_range()` và `require_page_range()` chỉ phục vụ test/debug hoặc legacy caller. Hai hàm này không thuộc normative production flow sau khi `PageBlock[]` đã được tạo.

Không parse page range từ parent/child content:

```text
- Page marker đã được consume thành PageBlock.metadata trước parser.
- PageBlock.content không còn chứa marker.
- ParentSection.page_start/page_end lấy từ StructuralBlock page metadata.
- Child page_start/page_end kế thừa từ ChildUnit/ParentSection metadata.
- Child content/raw content không được dùng để dò lại page marker.
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
    assert blocks[0].content == "A"
    assert blocks[1].content == "B"
    assert "<!-- page:" not in blocks[0].content
    assert "<!-- page:" not in blocks[1].content


def test_split_body_removes_only_page_boundary_artifacts():
    text = """1

<!-- page: 1 -->

Noi dung trang 1

---

2

<!-- page: 2 -->

Noi dung trang 2
"""

    blocks = split_body_by_page_markers(text)

    assert blocks[0].content == "Noi dung trang 1"
    assert blocks[1].content == "Noi dung trang 2"
    assert all("<!-- page:" not in block.content for block in blocks)


def test_standalone_number_inside_normal_content_is_preserved():
    text = "<!-- page: 1 -->\nMuc tieu\n42\nDon vi"

    blocks = split_body_by_page_markers(text)

    assert "42" in blocks[0].content
```

## 7. Done Khi

- [x] Có `app/ingestion/parsing/page_markers.py`.
- [x] `page_markers.py` chứa `PageBlock`.
- [x] `page_markers.py` chứa `split_body_by_page_markers()`.
- [ ] `chunker.py` import `split_body_by_page_markers` từ helper trước khi gọi `parse_page_blocks()`.
- [ ] `parent_chunker.py` không gọi `split_body_by_page_markers()` hoặc parse page range từ content.
- [ ] Child builder không parse page range từ child content/raw content.
- [ ] Markdown reader vẫn giữ nguyên marker `<!-- page: n -->` trong body.
- [ ] Tests page marker pass.
- [ ] Tests chunker pass.

## 8. Contract Bổ Sung Bắt Buộc

```text
PageBlock.content bắt đầu sau current page marker và kết thúc trước next page marker.
Page marker đã được consume thành PageBlock.page_number, không còn trong content.
HTML comment kỹ thuật không tạo StructuralBlock, paragraph Child hoặc embedding text.
Số trang OCR đứng riêng và dấu --- chỉ được bỏ khi nằm sát page boundary đã xác định.
Không được xóa standalone number hoặc horizontal rule ở nội dung bình thường.
```



Note done
Được. Theo guild hiện tại, **nên bỏ luôn `require_page_range()` khỏi 10A**.

Vì flow mới đã chốt:

```
Markdown body
-> split_body_by_page_markers()
-> PageBlock(page_number, content không còn marker)
-> parse_page_blocks()
-> StructuralBlock.page_start/page_end
-> ParentSection/ChildUnit/Chunk kế thừa page metadata
```

Nên không còn chỗ hợp lý để gọi:

```
require_page_range(content)
```

Nếu giữ lại, nó gây nhiễu vì người implement dễ hiểu nhầm là parent/child content vẫn cần dò `<!-- page: n -->`.

Nên trong `10A_PART_C_PAGE_MARKER_HELPER_GUIDE.md`, sửa như sau:

- Xóa hàm `extract_page_range()`.
- Xóa hàm `require_page_range()`.
- Xóa tests:
    - `test_extract_page_range`
    - `test_extract_page_range_missing_marker`
    - `test_require_page_range_uses_fallback`
    - `test_require_page_range_rejects_missing_marker_without_fallback`
- Giữ:
    - `PAGE_RE`
    - `PageBlock`
    - `strip_page_boundary_artifacts()`
    - `extract_page_numbers()` nếu còn muốn test marker detection
    - `split_body_by_page_markers()`

Sau khi bỏ, contract 10A sạch hơn:

```
page_markers.py chỉ làm:
- nhận diện page marker;
- split Markdown body thành PageBlock;
- consume marker khỏi PageBlock.content;
- giữ page_number làm metadata.
```

Không còn page-range parsing từ text nữa.