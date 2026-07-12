# 09A. Hướng Dẫn Pre-Chunk Structural Parsing

**Last Updated:** 2026-07-10

File này bổ sung cho guide 09/10. Bước này chạy sau markdown reader và trước parent/child chunker.

Mục tiêu:

```text
Khong sua Markdown nguon.
Giu raw OCR/Markdown de audit.
Xu ly page marker truoc structural parsing.
Nhan dien heading/table/code/item theo thu tu on dinh.
Tao representation trung gian de parent/child chunker dung chung.
```

---

## 1. Quyết Định Chốt

Không convert item như `1.`, `2.`, `a)` thành Markdown heading.

Mô hình thống nhất:

```text
Markdown heading -> cau truc parent
Dieu/Khoan/Diem/Bullet -> cau truc item va ranh gioi child
```

Flow chốt:

```text
MarkdownDocument.body
  -> page_markers.split_body_by_page_markers()
  -> structural_parser.parse_page_blocks(PageBlock[])
       1. page marker da consume truoc parser
       2. fenced code block
       3. Markdown table
       4. Markdown heading
       5. numbered_item
       6. lettered_item
       7. bullet_item
       8. paragraph
  -> parent_chunker build parent theo Markdown heading
  -> child_chunker build child theo item/table/code/paragraph boundary
  -> embedding_text enrich bang heading_path + item_path
```

Page marker đã được consume thành `PageBlock.page_number`, không tạo `StructuralBlock`
và không được phân loại thành `paragraph`.
HTML comment khác cũng không được phân loại thành paragraph và không được đưa vào embedding.

Hard rule:

```text
Dong da bat dau bang Markdown heading marker (#, ##, ###, ####, ...)
luon la block_type = "heading".
Khong demote thanh numbered_item, lettered_item, bullet_item.
Item regex chi chay tren dong khong co Markdown heading marker.
```

Ví dụ:

```text
### 1. Muc dich       -> heading
1. Muc dich           -> numbered_item

### a) Doi tuong      -> heading
a) Doi tuong          -> lettered_item

### - Noi dung        -> heading
- Noi dung            -> bullet_item
```

---

## 2. File Cần Tạo/Sửa

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
chatbot/backend/app/ingestion/parsing/structural_parser.py
chatbot/backend/app/ingestion/chunking/parent_chunker.py
chatbot/backend/app/ingestion/chunking/child_chunker.py
chatbot/backend/app/ingestion/chunking/table_blocks.py
chatbot/backend/app/ingestion/chunking/chunker.py
chatbot/backend/test/ingestion/test_structural_parser.py
chatbot/backend/test/ingestion/test_chunker.py
```

Không tạo:

```text
page_blocks.py
module rieng chi de bien item thanh heading
```

`PageBlock` và `split_body_by_page_markers()` nằm trong `page_markers.py`.

### Code placement: `parse_page_blocks()`

`parse_page_blocks()` nằm trong `backend/app/ingestion/parsing/structural_parser.py`.
Hàm này là entrypoint của structural parser.

Input là `list[PageBlock]`. `PageBlock` được tạo bởi
`split_body_by_page_markers()` trong `backend/app/ingestion/parsing/page_markers.py`.

Output là `StructuralParseResult`, gồm:

```python
blocks: list[StructuralBlock]
reports: list[ValidationReport]
```

Flow sử dụng:

```python
page_blocks = split_body_by_page_markers(markdown_body)
parse_result = parse_page_blocks(page_blocks)
```

Trách nhiệm của `parse_page_blocks()`:

1. Duyệt `PageBlock[]` theo thứ tự gốc.
2. Không tạo block cho page marker vì page marker đã thành `PageBlock.page_number`.
3. Không reset `heading_path` và `item_path` khi đổi trang.
4. Nhận diện block theo đúng thứ tự: fenced code block, Markdown table,
   Markdown heading, numbered item, lettered item, bullet item, paragraph.
5. Tạo `StructuralBlock` cho mỗi block nội dung.
6. Tạo `ValidationReport` khi gặp cấu trúc mơ hồ hoặc lỗi.

Không đặt `parse_page_blocks()` trong `page_markers.py`, `parent_chunker.py`,
`child_chunker.py`, hoặc `chunker.py`.

### Implementation guide: `parse_page_blocks()`

Trong `structural_parser.py`, implement theo thứ tự nhỏ nhất:

1. Khai báo regex ở đầu file.
2. Khai báo `StructuralBlock`, `ValidationReport`, `StructuralParseResult`.
3. Viết helper nhận diện block atomic: fenced code, table.
4. Viết helper classify một dòng thường: heading, numbered item, lettered item,
   bullet item, paragraph.
5. Viết `parse_page_blocks()` giữ state qua toàn bộ tài liệu.

Suggested pattern:

```python
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
NUMBERED_ITEM_RE = re.compile(r"^(\(?\d+(?:\.\d+)*[.)/])\s+(.+)$")
LETTERED_ITEM_RE = re.compile(r"^([A-Za-zĐđ][.)/])\s+(.+)$")
BULLET_ITEM_RE = re.compile(r"^([-+*])\s+(.+)$")
FENCE_START_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
```

Skeleton:

```python
def parse_page_blocks(page_blocks: list[PageBlock]) -> StructuralParseResult:
    blocks: list[StructuralBlock] = []
    reports: list[ValidationReport] = []
    heading_stack: list[tuple[int, str]] = []
    item_stack: list[StructuralBlock] = []
    source_order = 0

    # Flatten once so atomic code/table and paragraphs may cross a page boundary.
    lines = [
        (page_block.page_number, line)
        for page_block in page_blocks
        for line in page_block.content.splitlines()
    ]
    index = 0

    while index < len(lines):
        page_number, line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        # Technical HTML comments, including multiline comments.
        if stripped.startswith("<!--"):
            index = _consume_html_comment(lines, index)
            continue

        # 1. fenced code block
        if FENCE_START_RE.match(stripped):
            raw_content, page_start, page_end, index, report = _consume_fenced_code(
                lines, index, heading_stack, item_stack
            )
            blocks.append(_make_code_block(raw_content, page_start, page_end, source_order, heading_stack, item_stack))
            if report is not None:
                reports.append(report)
            source_order += 1
            continue

        # 2. Markdown table
        if _looks_like_table_start(lines, index):
            raw_content, page_start, page_end, index = _consume_table(lines, index)
            blocks.append(_make_table_block(raw_content, page_start, page_end, source_order, heading_stack, item_stack))
            source_order += 1
            continue

        # A paragraph is adjacent nonblank text, not one block per OCR line.
        if not _starts_structural_block(lines, index):
            raw_content, page_start, page_end, index = _consume_paragraph(lines, index)
            blocks.append(
                _make_paragraph_block(
                    raw_content,
                    page_start,
                    page_end,
                    source_order,
                    heading_stack,
                    item_stack,
                )
            )
            source_order += 1
            continue

        # 3-6. Heading/item line-level classification.
        block, report = _classify_line(
            line,
            page_number,
            source_order,
            heading_stack,
            item_stack,
        )
        blocks.append(block)
        if report is not None:
            reports.append(report)

        _update_state(block, heading_stack, item_stack)
        source_order += 1
        index += 1

    return StructuralParseResult(blocks=blocks, reports=reports)
```

Helper contract cần chốt:

```text
`lines` la list[(page_number, line)] theo source order; khong reset state khi page_number doi.
`_consume_fenced_code()` doc den closing ``` ke ca qua trang. Khong co closing fence: emit
code block den EOF va report error `unclosed_code_fence`.
`_looks_like_table_start()` chi true khi current line va separator line ke tiep tao Markdown table hop le.
`_consume_table()` doc cac row lien tiep, cho phep page_number doi; dung tai blank line hoac non-table line.
`_consume_paragraph()` gom cac dong nonblank lien tiep den heading/item/table/code/HTML comment/blank.
`page_start/page_end` cua block atomic/paragraph la min/max page da consume.
```

### Code helpers trong `structural_parser.py`

Suggested pattern:

```python
LineWithPage = tuple[int, str]


def _consume_html_comment(lines: list[LineWithPage], index: int) -> int:
    """Return index ngay sau closing comment, hoặc EOF nếu comment không đóng."""
    while index < len(lines):
        _, line = lines[index]
        index += 1
        if "-->" in line:
            break
    return index


def _is_closing_fence(line: str, opening_fence: str) -> bool:
    candidate = line.strip()
    return (
        len(candidate) >= len(opening_fence)
        and set(candidate) == {opening_fence[0]}
    )


def _consume_fenced_code(
    lines: list[LineWithPage],
    index: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> tuple[str, int, int, int, ValidationReport | None]:
    start_page, opening_line = lines[index]
    opening_match = FENCE_START_RE.match(opening_line.strip())
    if opening_match is None:
        raise ValueError("Expected fenced code opening")

    opening_fence = opening_match.group(1)
    consumed: list[str] = []
    pages: list[int] = []

    while index < len(lines):
        page_number, line = lines[index]
        consumed.append(line)
        pages.append(page_number)
        index += 1

        if len(consumed) > 1 and _is_closing_fence(line, opening_fence):
            return "\n".join(consumed), min(pages), max(pages), index, None

    heading_path = [text for _, text in heading_stack]
    item_path = item_stack[-1].item_path if item_stack else []
    owner = [*heading_path, *item_path]
    raw_content = "\n".join(consumed)
    report = ValidationReport(
        severity="error",
        code="unclosed_code_fence",
        reason="Fenced code block has no closing fence",
        page=start_page,
        raw_content=raw_content,
        current_heading_path=heading_path,
        current_item_path=item_path,
        selected_owner=owner or None,
        candidate_owners=[owner] if owner else [],
        candidate_types=["code"],
        selected_type="code",
        confidence=1.0,
    )
    return raw_content, min(pages), max(pages), index, report


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return len(cells) >= 2 and all(
        TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells
    )


def _is_table_row(line: str, expected_columns: int) -> bool:
    return "|" in line and len(_table_cells(line)) == expected_columns


def _looks_like_table_start(lines: list[LineWithPage], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    _, header = lines[index]
    _, separator = lines[index + 1]
    header_cells = _table_cells(header)
    return (
        "|" in header
        and len(header_cells) >= 2
        and _is_table_separator(separator)
        and len(_table_cells(separator)) == len(header_cells)
    )


def _consume_table(
    lines: list[LineWithPage],
    index: int,
) -> tuple[str, int, int, int]:
    expected_columns = len(_table_cells(lines[index][1]))
    consumed: list[str] = []
    pages: list[int] = []

    # Header và separator đã được xác nhận bởi _looks_like_table_start().
    for _ in range(2):
        page_number, line = lines[index]
        consumed.append(line)
        pages.append(page_number)
        index += 1

    while index < len(lines):
        page_number, line = lines[index]
        if not line.strip() or not _is_table_row(line, expected_columns):
            break
        consumed.append(line)
        pages.append(page_number)
        index += 1

    return "\n".join(consumed), min(pages), max(pages), index


def _starts_structural_block(lines: list[LineWithPage], index: int) -> bool:
    _, line = lines[index]
    stripped = line.strip()
    return bool(
        stripped.startswith("<!--")
        or FENCE_START_RE.match(stripped)
        or _looks_like_table_start(lines, index)
        or MARKDOWN_HEADING_RE.match(stripped)
        or NUMBERED_ITEM_RE.match(stripped)
        or LETTERED_ITEM_RE.match(stripped)
        or BULLET_ITEM_RE.match(stripped)
    )


def _consume_paragraph(
    lines: list[LineWithPage],
    index: int,
) -> tuple[str, int, int, int]:
    consumed: list[str] = []
    pages: list[int] = []

    while index < len(lines):
        page_number, line = lines[index]
        if not line.strip() or _starts_structural_block(lines, index):
            break
        consumed.append(line)
        pages.append(page_number)
        index += 1

    if not consumed:
        raise ValueError("Expected paragraph content")
    return "\n".join(consumed), min(pages), max(pages), index


def _current_context(
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> tuple[list[str], list[str], str | None]:
    heading_path = [text for _, text in heading_stack]
    item_path = list(item_stack[-1].item_path) if item_stack else []
    parent_item_key = item_stack[-1].logical_item_key if item_stack else None
    return heading_path, item_path, parent_item_key


def _make_code_block(
    raw_content: str,
    page_start: int,
    page_end: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> StructuralBlock:
    heading_path, item_path, parent_item_key = _current_context(heading_stack, item_stack)
    return StructuralBlock(
        block_type="code",
        raw_content=raw_content,
        page_start=page_start,
        page_end=page_end,
        source_order=source_order,
        heading_path=heading_path,
        item_path=item_path,
        parent_item_key=parent_item_key,
        logical_code_key=f"code:{source_order:06d}",
    )


def _make_table_block(
    raw_content: str,
    page_start: int,
    page_end: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> StructuralBlock:
    heading_path, item_path, parent_item_key = _current_context(heading_stack, item_stack)
    return StructuralBlock(
        block_type="table",
        raw_content=raw_content,
        page_start=page_start,
        page_end=page_end,
        source_order=source_order,
        heading_path=heading_path,
        item_path=item_path,
        parent_item_key=parent_item_key,
        logical_table_key=f"table:{source_order:06d}",
    )


def _make_paragraph_block(
    raw_content: str,
    page_start: int,
    page_end: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> StructuralBlock:
    heading_path, item_path, parent_item_key = _current_context(heading_stack, item_stack)
    return StructuralBlock(
        block_type="paragraph",
        raw_content=raw_content,
        page_start=page_start,
        page_end=page_end,
        source_order=source_order,
        heading_path=heading_path,
        item_path=item_path,
        parent_item_key=parent_item_key,
    )
```

`_starts_structural_block()` phải nhận diện cả code/table/comment. Outer loop đã xử lý
chúng trước paragraph, nhưng `_consume_paragraph()` cũng dùng helper này để không nuốt
block structural nằm ở dòng kế tiếp.

Giới hạn MVP: table cell không hỗ trợ escaped pipe `\|`. Chỉ bổ sung parser escaped pipe
khi canonical Markdown thực sự có trường hợp đó.

`_classify_line()` chỉ nhận heading hoặc item vì code/table/comment/paragraph đã được
outer loop xử lý trước. Hàm trả cả block và warning tùy chọn để caller gom report tại
một chỗ.

Suggested pattern:

```python
def _numbered_depth(marker: str) -> int:
    normalized = marker.strip().lstrip("(").rstrip(".)/")
    return max(1, len([part for part in normalized.split(".") if part]))


def _resolve_item_level(
    block_type: str,
    marker: str,
    item_stack: list[StructuralBlock],
) -> int:
    if block_type == "numbered_item":
        return _numbered_depth(marker)

    # Marker cùng loại gần nhất là sibling, nên dùng lại level của nó.
    for previous in reversed(item_stack):
        if previous.block_type == block_type and previous.item_level is not None:
            return previous.item_level

    if block_type == "lettered_item":
        for previous in reversed(item_stack):
            if previous.block_type == "numbered_item" and previous.item_level is not None:
                return previous.item_level + 1
        return 1

    # Bullet đầu tiên thuộc item đang mở; nếu không có item cha thì là level 1.
    if item_stack and item_stack[-1].item_level is not None:
        return item_stack[-1].item_level + 1
    return 1


def _has_legal_context(
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> bool:
    return any(
        text.casefold().startswith("điều ") for _, text in heading_stack
    ) or any(
        item.legal_unit_type in {"article", "clause", "point"}
        for item in item_stack
    )


def _classify_line(
    line: str,
    page_number: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> tuple[StructuralBlock, ValidationReport | None]:
    candidate = line.strip()

    heading_match = MARKDOWN_HEADING_RE.match(candidate)
    if heading_match:
        heading_level = len(heading_match.group(1))
        heading_text = heading_match.group(2).strip()
        heading_path = [
            text for level, text in heading_stack if level < heading_level
        ]
        heading_path.append(heading_text)
        return StructuralBlock(
            block_type="heading",
            raw_content=line,
            page_start=page_number,
            page_end=page_number,
            source_order=source_order,
            heading_path=heading_path,
            heading_level=heading_level,
            heading_text=heading_text,
            legal_unit_type=(
                "article"
                if heading_text.casefold().startswith("điều ")
                else "none"
            ),
        ), None

    match: re.Match[str] | None
    block_type: str
    match = NUMBERED_ITEM_RE.match(candidate)
    if match:
        block_type = "numbered_item"
    else:
        match = LETTERED_ITEM_RE.match(candidate)
        if match:
            block_type = "lettered_item"
        else:
            match = BULLET_ITEM_RE.match(candidate)
            if match:
                block_type = "bullet_item"
            else:
                raise ValueError("Expected heading or item line")

    marker = match.group(1)
    item_level = _resolve_item_level(block_type, marker, item_stack)
    parent = next(
        (
            item
            for item in reversed(item_stack)
            if item.item_level is not None and item.item_level < item_level
        ),
        None,
    )
    item_path = [*(parent.item_path if parent else []), candidate]
    legal_unit_type = "none"
    if _has_legal_context(heading_stack, item_stack):
        legal_unit_type = {
            "numbered_item": "clause",
            "lettered_item": "point",
            "bullet_item": "bullet",
        }[block_type]

    block = StructuralBlock(
        block_type=block_type,
        raw_content=line,
        page_start=page_number,
        page_end=page_number,
        source_order=source_order,
        heading_path=[text for _, text in heading_stack],
        item_marker=marker,
        item_level=item_level,
        item_path=item_path,
        logical_item_key=f"item:{source_order:06d}",
        parent_item_key=parent.logical_item_key if parent else None,
        legal_unit_type=legal_unit_type,
    )

    if item_level <= 1 or parent is not None:
        return block, None

    heading_path = [text for _, text in heading_stack]
    return block, ValidationReport(
        severity="warning",
        code="item_level_jump",
        reason=f"Item starts at level {item_level} without a parent item",
        page=page_number,
        raw_content=line,
        current_heading_path=heading_path,
        current_item_path=item_path,
        selected_owner=heading_path or None,
        candidate_owners=[heading_path] if heading_path else [],
        candidate_types=[block_type],
        selected_type=block_type,
        confidence=0.6,
    )
```

Không thêm fallback paragraph vào `_classify_line()`. Nếu hàm nhận paragraph thì caller
đã vi phạm contract của `_starts_structural_block()` / `_consume_paragraph()`, nên fail
fast bằng `ValueError` dễ debug hơn tạo sai block.

State update rule:

```text
heading block:
  - pop heading_stack cho toi khi top_level < heading_level
  - push (heading_level, heading_text)
  - clear item_stack

item block:
  - `item_level` la depth structural, khong phai legal_unit_type:
    numbered `1.` = 1, `1.1.` = 2; lettered/bullet = parent depth + 1 neu co parent,
    nguoc lai = 1
  - pop item_stack cho toi parent item dung cap
  - parent_item_key = item_stack[-1].logical_item_key neu co parent
  - push item hien tai

paragraph/table/code block:
  - khong doi heading_stack
  - khong doi item_stack
  - ke thua heading_path va item_path hien tai
```

Suggested pattern:

```python
ITEM_BLOCK_TYPES = {"numbered_item", "lettered_item", "bullet_item"}


def _update_state(
    block: StructuralBlock,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> None:
    if block.block_type == "heading":
        if block.heading_level is None or block.heading_text is None:
            raise ValueError("Heading block is missing heading metadata")
        while heading_stack and heading_stack[-1][0] >= block.heading_level:
            heading_stack.pop()
        heading_stack.append((block.heading_level, block.heading_text))
        item_stack.clear()
        return

    if block.block_type not in ITEM_BLOCK_TYPES:
        return
    if block.item_level is None:
        raise ValueError("Item block is missing item_level")

    while item_stack:
        current_level = item_stack[-1].item_level
        if current_level is None:
            raise ValueError("Item stack contains an item without item_level")
        if current_level < block.item_level:
            break
        item_stack.pop()
    item_stack.append(block)
```

Test nhỏ trong `backend/tests/ingestion/test_structural_parser.py`:

```python
def test_update_state_replaces_sibling_and_heading_resets_items() -> None:
    headings = [(1, "H1")]
    first = StructuralBlock(
        block_type="numbered_item",
        raw_content="1. A",
        page_start=1,
        page_end=1,
        source_order=1,
        item_level=1,
    )
    second = StructuralBlock(
        block_type="numbered_item",
        raw_content="2. B",
        page_start=1,
        page_end=1,
        source_order=2,
        item_level=1,
    )
    items = [first]

    _update_state(second, headings, items)
    assert items == [second]

    heading = StructuralBlock(
        block_type="heading",
        raw_content="## H2",
        page_start=1,
        page_end=1,
        source_order=3,
        heading_level=2,
        heading_text="H2",
    )
    _update_state(heading, headings, items)
    assert headings == [(1, "H1"), (2, "H2")]
    assert items == []
```

Key va report toi thieu:

```text
Parser tao key deterministic tu source_order: `item:000001`, `table:000002`, `code:000003`.
Chunker chi copy key nay; khong tao lai key sau khi split.
`item_level_jump` la warning parser toi thieu. Chi them
Paragraph ke thua owner hien tai tu parser stack va khong emit report trong MVP.
`unclosed_code_fence` la error.
Duplicate logical key va split boundary la error o child/chunker layer, khong phai parser line-level.
```

Lazy rule:

```text
Dung helper nho, khong tao class parser rieng trong MVP.
Chi tao class ParserState neu tham so helper bat dau qua dai hoac test kho doc.
```

---

## 3. Data Structures

Suggested pattern:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StructuralBlock:
    block_type: str  # heading | numbered_item | lettered_item | bullet_item | paragraph | table | code
    raw_content: str
    page_start: int
    page_end: int
    source_order: int
    heading_path: list[str] = field(default_factory=list)
    heading_level: int | None = None
    heading_text: str | None = None
    item_marker: str | None = None
    item_level: int | None = None
    item_path: list[str] = field(default_factory=list)
    logical_item_key: str | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None
    legal_unit_type: str = "none"  # article | clause | point | bullet | none
    confidence: float = 1.0
```

Validation report:

```python
@dataclass(frozen=True)
class ValidationReport:
    severity: str  # warning | error
    code: str
    reason: str
    page: int
    raw_content: str
    current_heading_path: list[str]
    current_item_path: list[str]
    selected_owner: list[str] | None
    candidate_owners: list[list[str]]
    candidate_types: list[str]
    selected_type: str | None
    confidence: float
    file: str | None = None
```

Parse result:

```python
@dataclass(frozen=True)
class StructuralParseResult:
    blocks: list[StructuralBlock]
    reports: list[ValidationReport] = field(default_factory=list)
```

---

## 4. Parser Order

Parser nhận `PageBlock[]` đã tách sẵn và chạy stateful đúng một lần theo source order.
Không reset heading/item context khi đổi trang. Trong từng `PageBlock`, parser chạy theo thứ tự:

```text
1. page marker da consume truoc parser
2. fenced code block
3. Markdown table
4. Markdown heading
5. numbered_item
6. lettered_item
7. bullet_item
8. paragraph
```

Lý do:

```text
Page marker da thanh PageBlock.page_number, khong thanh StructuralBlock.
HTML comment khac bi bo qua hoac tao non-embedding technical block, khong thanh paragraph.
Marker nhu 1. hoac a) trong table/code khong duoc parse thanh item.
Markdown heading phai thang item regex.
Paragraph chi la fallback cuoi cung.
```

---

## 5. Block Classification Rules

Markdown heading:

```python
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
```

Nếu match, luôn tạo:

```python
block_type = "heading"
heading_level = len(match.group(1))
heading_text = match.group(2).strip()
legal_unit_type = "article" nếu heading_text bắt đầu bằng "Điều "
```

Item regex chỉ chạy khi line không phải heading/table/code/comment/page marker.

Suggested pattern:

```python
NUMBERED_ITEM_RE = re.compile(r"^(\(?\d+(?:\.\d+)*[.)/])\s+(.+)$")
LETTERED_ITEM_RE = re.compile(r"^([A-Za-zĐđ][.)/])\s+(.+)$")
BULLET_ITEM_RE = re.compile(r"^([-+*])\s+(.+)$")
```

Marker cần hỗ trợ:

```text
numbered_item: 1., 1), 1/, (1), 1.1., 1.1)
lettered_item: a., a), a/, A., A), A/
bullet_item: -, +, *
```

Mapping block type và legal unit phải tách biệt:

```text
Markdown heading "Điều ..." -> block_type = heading; legal_unit_type = article
1., 2., 1.1.              -> block_type = numbered_item
a), b), A.                -> block_type = lettered_item
-, +, *                   -> block_type = bullet_item
```

`legal_unit_type` không được suy ra chỉ từ marker. Chỉ gán `clause`, `point`,
`bullet` khi item nằm trong legal context đã được xác nhận, ví dụ ancestor heading
`Điều ...` hoặc structural ancestor pháp lý. Danh sách thông thường dùng
`legal_unit_type = none`.

---

## 6. Legal Hierarchy Và item_path

Cấu trúc:

```text
Điều
└── Khoản
    └── Điểm
        └── Gạch đầu dòng
```

Rule:

```text
Item con ke thua item_path cua item cha.
Item cung cap dong item truoc do.
Item cap cao hon dong cac item con ben duoi.
Neu marker nhay cap bat thuong, ghi ValidationReport warning/error tuy muc do.
```

Ví dụ:

```text
1. Hồ sơ gồm:
a) Đơn đăng ký.
b) Bản sao căn cước.
```

Child metadata:

```text
item_path = ["1. Hồ sơ gồm:", "a) Đơn đăng ký."]
legal_unit_type = point  # chi khi legal context da xac nhan
logical_item_key = stable key cua item hien tai
parent_item_key = stable key cua item cha neu co
```

`item_path` phải lấy từ dòng item gốc:

```text
Giu marker.
Bo marker khi tao semantic label noi bo neu can, nhung output item_path van giu marker + nhan ngan.
Giu noi dung goc, co the gioi han do dai.
Khong dung LLM de tom tat hoac tu sinh nhan.
Khong chi luu ["1.", "a)"].
Khong sao chep toan bo noi dung dai cua item cha vao item_path.
```

---

## 7. Parent Và Child Boundary

Parent:

```text
Tao theo Markdown heading.
Noi dung truoc heading dau tien thuoc document-root parent.
Parent giu full section, heading_path, page_start, page_end.
Parent khong embed trong MVP.
```

Child:

```text
StructuralBlock != Chunk: parser luon tao block rieng; child_chunker moi quyet dinh ChildUnit/Chunk.
numbered_item, lettered_item luon tao Child rieng, ke ca item ngan hoac ket thuc bang ":".
bullet ngan lien ke co the gop thanh mot Child khi cung heading_path va parent_item_key,
va tong content khong vuot child_chunk_size.
Khong gop numbered_item/lettered_item; khong gop bullet khac parent_item_key, qua table/code,
paragraph, heading, hoac child_chunk_size.
Chunk bullet gop giu logical_item_keys cua tat ca bullet thanh vien.
RecursiveCharacterTextSplitter chi chay sau structural parsing.
Neu item qua dai, split ben trong item do va giu logical_item_key, parent_item_key, item_path.
Item cha co item con van tao Child rieng.
Item con tao Child rieng va link ve item cha bang parent_item_key.
Child item cha khong chua noi dung item con.
```

Paragraph sau item:

```text
Gan vao Child item hien tai.
Dung khi gap heading moi hoac bat ky item moi.
Neu item moi co cap thap hon thi item do thanh item con.
Page marker khong lam ket thuc item va khong lam mat item_path.
Neu paragraph khong thuoc item nao, tao paragraph Child trong Parent hien tai.
Paragraph sau danh sach ke thua item dang mo; khong tao ValidationReport rieng.
Khong am tham gan sai.
```

Item/paragraph quá dài:

```text
Chi split ben trong chinh don vi do.
Khong split sang item ke tiep.
Moi phan split dung chung logical_item_key.
Giu cung heading_path, item_path, parent_item_key.
Gan split_index va split_count trong metadata.
```

---

## 8. Table Và Code

Rule:

```text
Table va fenced code duoc nhan dien truoc item regex.
Marker 1. hoac a) trong table/code khong parse thanh item.
Table/code nam trong item ke thua heading_path, item_path va parent_item_key.
Table va fenced code luon tao atomic Child rieng, khong append vao raw content cua Child item.
Truoc khi emit table/code Child, flush Child item hien tai nhung giu item stack de ke thua context.
Table ngan giu nguyen.
Table dai split theo row group, lap lai header + separator va khong cat giua row.
Code block nho giu nguyen. Code block dai split theo ranh gioi dong; moi split giu opening/closing fence hop le, cung logical_code_key va split_index/split_count. Khong cat bang generic recursive splitter.
```

Table chỉ xử lý ở child layer vì parent phải giữ full section.

---

## 9. Embedding Preparation

Raw child content giữ nguyên.

`embedding_text` được tạo thêm, không ghi đè raw content:

```text
heading_path
ancestor item labels = item_path[:-1]
limited parent item context neu Child con qua ngan
legal_unit_type
raw child content
```

Không thêm thông tin suy diễn. Không tự tóm tắt. Context prepend cho child quá ngắn chỉ lấy
nguyên văn có giới hạn từ `heading_path` và nhãn các item cha; raw content của Child giữ nguyên.

Ví dụ:

```text
Raw:
a) Don dang ky.

Embedding text:
Dieu kien ho so > Khoan 1. Ho so gom > Diem a) Don dang ky.
```

Page marker và HTML comment kỹ thuật khác không được đưa vào `embedding_text`.

---

## 10. Tests Bắt Buộc

- [ ] Danh sách 5 numbered/lettered item dưới một heading tạo 1 parent và 5 child.
- [ ] Item không bị convert thành heading.
- [ ] `### 1. Mục đích` vẫn là heading.
- [ ] `### 1) Phạm vi` vẫn là heading.
- [ ] `### a) Đối tượng` vẫn là heading.
- [ ] `### - Nội dung` vẫn là heading.
- [ ] Markdown heading không bị demote thành item.
- [ ] Điều -> Khoản -> Điểm -> Bullet tạo đúng `item_path`.
- [ ] Paragraph kế thừa item đang mở; paragraph ngoài item tạo Child trong Parent hiện tại.
- [ ] Item con kế thừa context cha.
- [ ] Item cha kết thúc bằng `:` vẫn tạo child riêng.
- [ ] Item cha có item con không chứa nội dung item con.
- [ ] Item con có `parent_item_key` trỏ về item cha.
- [ ] `item_path` giữ marker và nhãn ngắn, không chỉ lưu marker.
- [ ] Parser tạo một `bullet_item` StructuralBlock cho mỗi bullet.
- [ ] Bullet ngắn liền kề cùng heading_path/parent_item_key được gộp; numbered/lettered luôn riêng.
- [ ] Bullet group giữ đủ `logical_item_keys`.
- [ ] Item quá dài chỉ split nội bộ và giữ `logical_item_key`.
- [ ] Split child có `split_index` và `split_count`.
- [ ] Không Child chứa hai numbered/lettered item hoặc bullet khác parent; bullet group hợp lệ là ngoại lệ.
- [ ] Marker trong table/code không bị parse thành item.
- [ ] Nội dung trước heading đầu tiên thuộc `document-root` parent.
- [ ] Table/code trong item kế thừa đúng context.
- [ ] Child ngắn có `embedding_text` chứa context thật.
- [ ] Page marker không bị đưa vào `embedding_text`.
- [ ] HTML comment kỹ thuật khác không bị đưa vào `embedding_text`.
- [ ] HTML comment nhiều dòng không tạo block và paragraph sau comment vẫn được parse.
- [ ] Paragraph ngay trước table/code dừng đúng index, không nuốt block atomic kế tiếp.
- [ ] Dòng có pipe nhưng không có separator hợp lệ vẫn là paragraph, không phải table.
- [ ] Markdown table hợp lệ giữ header/separator/rows và đúng page range.
- [ ] Fenced code bằng backtick hoặc tilde được consume nguyên block.
- [ ] Paragraph nhiều dòng tạo một `StructuralBlock` và giữ đúng page range.
- [ ] Fenced code/table qua page tạo đúng một block atomic với `page_start/page_end`.
- [ ] Fenced code không đóng tạo `unclosed_code_fence` error.
- [ ] `logical_item_key`, `logical_table_key`, `logical_code_key` deterministic theo `source_order`.

---

## 11. Done Khi

- [ ] Không còn logic convert `1.`, `a)` thành Markdown heading.
- [ ] Có structural block parser.
- [ ] Markdown heading được nhận diện trước item regex.
- [ ] Parent chunker chỉ dựa trên Markdown heading.
- [ ] Child chunker dựa trên structural item/table/code/paragraph boundary.
- [ ] Ambiguous cases có report.
- [ ] Tests parser/chunker pass.

## 11. Validation Severity Và Canonical Markdown Warning

`ValidationReport` phải có tối thiểu:

```text
severity: warning | error
code
reason
page
selected_owner
candidate_owners
```

```text
warning không tự động chặn publish.
error mới chặn publish theo mặc định.
heading context kép và heading dài bất thường là warning.
missing page range, duplicate logical_item_key, child thiếu parent_chunk_key hoặc split phá boundary là error.
```

Markdown heading có sẵn vẫn luôn là heading. Parser không tự demote heading sai, nhưng phải tạo
`canonical_markdown_warning` cho heading quá dài, nhiều câu, level bất thường, hai heading cùng cấp
liên tiếp không có body hoặc Parent không có Child.
