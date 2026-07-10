# 10. Part C - Hướng Dẫn Implement Structural Parent-Child Chunker

**Last Updated:** 2026-07-10

File này tách chi tiết từ guide 07, phần C.

Mục tiêu:

```text
Nhan Markdown body da validate
tach page marker truoc structural parsing
parent tao theo Markdown heading
child tao theo Dieu/Khoan/Diem/Bullet structural boundary
RecursiveCharacterTextSplitter chi dung cho item/paragraph qua dai; table/code co splitter rieng
giu heading_path, item_path, legal_unit_type, page range, table/page marker neu co
tra ve ChunkingResult voi stable chunk keys, warnings va errors
```

Chunker không đọc file, không parse YAML, không ghi DB, không tạo DB id.

---

## 1. File Cần Tạo/Sửa

```text
chatbot/backend/app/ingestion/chunking/__init__.py
chatbot/backend/app/ingestion/chunking/chunker.py
chatbot/backend/app/ingestion/chunking/parent_chunker.py
chatbot/backend/app/ingestion/chunking/child_chunker.py
chatbot/backend/app/ingestion/chunking/table_blocks.py
chatbot/backend/app/ingestion/chunking/text_stats.py
chatbot/backend/app/ingestion/parsing/__init__.py
chatbot/backend/app/ingestion/parsing/page_markers.py
chatbot/backend/app/ingestion/parsing/structural_parser.py
chatbot/backend/test/ingestion/test_chunker.py
chatbot/backend/test/ingestion/test_structural_parser.py
chatbot/backend/requirements.txt
```

Chunker nhận input từ:

```text
app.ingestion.markdown_reader.MarkdownDocument
```

Dependency cần có:

```text
langchain-text-splitters>=0.2
```

Import đề xuất trong từng file:

```python
# child_chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter

# parent_chunker.py va child_chunker.py
from app.ingestion.chunking.text_stats import count_units
```

---

## 1.1 Tách File Theo Trách Nhiệm

Dùng cấu trúc:

```text
app/ingestion/chunking/
    __init__.py
    chunker.py
    parent_chunker.py
    child_chunker.py
    table_blocks.py
    text_stats.py
```

Trách nhiệm:

```text
chunker.py
- public API: chunk_markdown_document(), chunk_markdown_body()
- dieu phoi parent_chunker va child_chunker
- quan ly chunk_index global va child_counter
- return ChunkingResult

parent_chunker.py
- ParentSection dataclass
- build_parent_sections()
- make_parent_section()
- make_parent_chunk()

child_chunker.py
- build_child_splitter()
- ChildUnit dataclass
- build_child_units()
- build_structural_child_units()
- split_long_child_unit()
- make_child_chunks()

table_blocks.py
- TextBlock dataclass
- split_markdown_table_blocks()
- split_large_table_block()
- protect Markdown table truoc khi child splitter cat text

text_stats.py
- count_units()

parsing/structural_parser.py
- StructuralBlock dataclass
- ValidationReport dataclass
- parse_page_blocks()
- classify_line()
- build_item_path()
```

Không tách nhỏ hơn nữa trong MVP. Các file này đủ để clean code mà không làm structure quá phân mảnh.

## 2. Contract Quan Trọng

Trong MVP:

```text
Chunk.chunk_key = stable key trong memory/preview/PostgreSQL/Qdrant
Chunk.parent_chunk_key = stable parent key trong memory/preview/repository input/Qdrant
DocumentChunk.id = internal PostgreSQL primary key sau khi insert DB
DocumentChunk.parent_chunk_id = internal FK sau khi repository map parent_chunk_key -> DB id
PostgreSQL không có cột parent_chunk_key; không tuyên bố structural metadata đã persist nếu schema chưa có JSONB/cột tương ứng
```

Chunker tạo stable key, không tạo DB id.

Stable key đề xuất:

```text
<version_key>::p::<parent_index>
<version_key>::c::<child_index>
```

Ví dụ:

```text
qd3266-2024::p::0001
qd3266-2024::c::0001
```

Lưu ý quan trọng:

```text
parent_index va child_index chi dung de tao stable key rieng tung loai.
chunk_index trong Chunk/DocumentChunk phai la global sequential index trong version.
Khong reset chunk_index rieng cho parent/child, vi DB unique(document_version_id, chunk_index).
```

---

## 3. Chiến Lược Chunking

MVP dùng 3 lớp:

```text
Layer 1: Page-aware structural parser
  -> PageBlock[]
  -> StructuralParseResult(blocks, reports)
  -> page marker da consume truoc parser
  -> nhan dien code/table/heading/item/paragraph theo thu tu bat buoc

Layer 2: Parent chunker
  -> nhan StructuralBlock[] da parse san
  -> tao parent theo moi Markdown heading
  -> noi dung truoc heading dau tien vao document-root parent

Layer 3: Child chunker
  -> nhan ParentSection.blocks
  -> tao child theo numbered_item / lettered_item / bullet_item / table / code / paragraph boundary
  -> RecursiveCharacterTextSplitter chi split ben trong mot child unit qua dai

Project code
  -> gan stable chunk_key, parent_chunk_key, page_start/page_end, heading_path, item_path, legal_unit_type, chunk_index
```

Lý do:

```text
Markdown heading la parent boundary.
Dieu/Khoan/Diem/Bullet la child boundary.
Khong convert item thanh Markdown heading.
Project code van giu quyen kiem soat metadata, citation, DB mapping.
Khong dua DB id vao chunker.
```

---

## 4. Public API Đề Xuất

File:

```text
chatbot/backend/app/ingestion/chunking/chunker.py
```

Suggested pattern:

```python
from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk


def chunk_markdown_document(document: MarkdownDocument) -> ChunkingResult:
    return chunk_markdown_body(
        body=document.body,
        document_key=document.metadata.document_key,
        version_key=document.metadata.version_key,
    )
```

Hàm core:

```python
DEFAULT_CHILD_CHUNK_SIZE = 1000
DEFAULT_CHILD_CHUNK_OVERLAP = 100


def chunk_markdown_body(
    *,
    body: str,
    document_key: str,
    version_key: str,
    child_chunk_size: int = DEFAULT_CHILD_CHUNK_SIZE,
    child_chunk_overlap: int = DEFAULT_CHILD_CHUNK_OVERLAP,
) -> ChunkingResult:
    ...
```

Return contract:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingResult:
    parent_chunks: list[Chunk]
    child_chunks: list[Chunk]
    warnings: list[ValidationReport]
    errors: list[ValidationReport]
```

`chunk_markdown_document()` và `chunk_markdown_body()` trả `ChunkingResult`, không trả raw `list[Chunk]`.
Caller dùng `result.parent_chunks + result.child_chunks`; preview/API show `result.warnings` và `result.errors`.

Trong MVP, `child_chunk_size` và `child_chunk_overlap` tính theo ký tự vì `RecursiveCharacterTextSplitter` mặc định dùng length function theo character.

Giá trị default lấy từ runtime settings (xem `21_RUNTIME_SETTINGS_GUIDE.md`):

```text
chunking.child_chunk_size = 1000
chunking.child_chunk_overlap = 100
```

Không dùng fallback kiểu `settings.chunking.child_chunk_size or 1000`. Default nằm trong settings model, config YAML chỉ override.

---

## 5. ParentSection Dataclass

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

`ParentSection` nằm trong `parent_chunker.py` vì nó là output của bước tách parent section. Không đặt trong `chunker.py`, vì `chunker.py` chỉ nên điều phối orchestration.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ParentSection:
    heading: str | None
    content: str
    blocks: list[StructuralBlock]
    heading_path: list[str]
    page_start: int
    page_end: int
    context_only: bool = False
    context_only_reason: str | None = None
```

Nếu `child_chunker.py` cần type hint `ParentSection`, import:

```python
from app.ingestion.chunking.parent_chunker import ParentSection
```

`ParentSection` không phải schema/API public; nó chỉ là dataclass nội bộ của ingestion chunking.

---

## 6. Page Marker

OCR/canonical Markdown phải giữ marker:

```markdown
<!-- page: 1 -->
```

Page marker helper được tách riêng ở:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
```

Xem chi tiết tại:

```text
chatbot/.docs/guild_implement/10A_PART_C_PAGE_MARKER_HELPER_GUIDE.md
```

Trong parser/chunker, dùng helper:

```python
from app.ingestion.parsing.page_markers import (
    require_page_range,
    split_body_by_page_markers,
)
```

Rule:

```text
Page marker khong duoc xoa truoc structural parsing.
Parent page_start/page_end lay tu min/max page cua StructuralBlock trong parent.
Child page_start/page_end lay tu ChildUnit.
Neu ChildUnit thieu page nhung parent co page range, fallback sang parent range.
Moi chunk phai resolve duoc page range, khong duoc tra `None`.
Neu toan bo document khong co page marker thi chunker fail som de khong tao chunk sai contract.
```

---

## 6.1 Text Stats Helper

File:

```text
chatbot/backend/app/ingestion/chunking/text_stats.py
```

MVP dùng word count đơn giản để gán `token_count`. Sau này có thể thay bằng tokenizer thật nếu cần.

```python
def count_units(text: str) -> int:
    return len(text.split())
```

Rule:

```text
token_count khong duoc null.
Parent va child chunk deu dung cung helper nay.
```

---

## 7. Tạo Parent Sections Từ Structural Blocks

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

Parent chỉ dựa trên `StructuralBlock(block_type="heading")`.

Helper nhỏ:

```python
def make_parent_section(
    *,
    blocks: list[StructuralBlock],
    heading_path: list[str],
) -> ParentSection:
    content = "\n\n".join(block.raw_content for block in blocks).strip()
    page_start = min(block.page_start for block in blocks)
    page_end = max(block.page_end for block in blocks)
    return ParentSection(
        heading=heading_path[-1] if heading_path else None,
        content=content,
        blocks=blocks,
        heading_path=heading_path,
        page_start=page_start,
        page_end=page_end,
    )
```

Function chính:

```python
def build_parent_sections(blocks: list[StructuralBlock]) -> list[ParentSection]:
    sections: list[ParentSection] = []
    current_blocks: list[StructuralBlock] = []
    current_heading_path: list[str] = ["document-root"]

    for block in blocks:
        if block.block_type == "heading":
            if current_blocks:
                sections.append(
                    make_parent_section(
                        blocks=current_blocks,
                        heading_path=current_heading_path,
                    )
                )
                current_blocks = []

            current_heading_path = update_heading_path(
                current_heading_path,
                level=block.heading_level or 1,
                text=block.heading_text or block.raw_content.strip(),
            )

        current_blocks.append(block)

    if current_blocks:
        sections.append(
            make_parent_section(
                blocks=current_blocks,
                heading_path=current_heading_path,
            )
        )

    return sections  # Không merge qua Markdown heading boundary.
```

`update_heading_path()`:

```python
def update_heading_path(path: list[str], *, level: int, text: str) -> list[str]:
    if path == ["document-root"]:
        path = []
    return [*path[: max(level - 1, 0)], text]
```

Lưu ý:

```text
Markdown heading co san luon la heading, ke ca "### 1. Muc dich" hoac "### a) Doi tuong".
Item khong tao parent.
Noi dung truoc heading dau tien thuoc heading_path ["document-root"].
Page range lay tu min/max page cua StructuralBlock, khong doan bang marker sau khi split text.
```

---

## 8. Tạo Parent Chunk

Parent chunk lưu full section trong PostgreSQL, không embed trong MVP.

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

```python
from app.ingestion.chunking.text_stats import count_units


def make_parent_chunk(
    *,
    section: ParentSection,
    document_key: str,
    version_key: str,
    parent_index: int,
    chunk_index: int,
) -> Chunk:
    parent_key = f"{version_key}::p::{parent_index:04d}"
    return Chunk(
        document_key=document_key,
        version_key=version_key,
        chunk_key=parent_key,
        chunk_type="parent",
        content=section.content,
        heading_path=section.heading_path,
        page_start=section.page_start,
        page_end=section.page_end,
        chunk_index=chunk_index,
        token_count=count_units(section.content),
    )
```

---

## 9. Protect Markdown Table Blocks Trước Khi Split Child

Markdown table không được để `RecursiveCharacterTextSplitter` cắt tùy ý theo từng dòng, vì row table mất header sẽ mất ngữ cảnh retrieval.

Ví dụ cần bảo vệ:

```markdown
| Điểm số<br>theo thang điểm 10 | Điểm chữ | Điểm số<br>theo thang điểm 4 |
| --- | --- | --- |
| 9,0 - 10,0 | A | 4,0 |
| 8,0 - 8,9 | B+ | 3,5 |
```

Rule:

```text
Bang ngan hon child_chunk_size thi giu nguyen thanh 1 child text rieng.
Bang khong duoc tron chung voi cau truoc/sau neu co the tach rieng.
Bang dai hon child_chunk_size thi split theo nhom row, moi child table phai lap lai header + separator.
Khong split ngang mot row table.
Page marker nam gan bang phai duoc giu de child table resolve page_start/page_end.
```

File nên đặt helper:

```text
chatbot/backend/app/ingestion/chunking/table_blocks.py
```

Dataclass gợi ý:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TextBlock:
    content: str
    block_type: str  # "text" | "table"
```

Detect Markdown table block:

```python
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
```

Heuristic:

```text
Mot table block can co it nhat:
- 1 dong header bat dau/ket thuc bang "|"
- 1 dong separator ngay sau header
- 0..n dong data lien tiep bat dau/ket thuc bang "|"
```

API gợi ý:

```python
def split_markdown_table_blocks(text: str) -> list[TextBlock]:
    ...


def split_large_table_block(
    table: str,
    *,
    child_chunk_size: int,
) -> list[str]:
    ...
```

`split_large_table_block()` phải giữ:

```text
header
separator
row group
```

trong từng child table.

---

## 10. Tạo Child Units Theo Structural Boundary

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

Child boundary:

```text
numbered_item
lettered_item
bullet_item
table
code
paragraph ro rang doc lap
```

Không gộp hai item khác nhau chỉ để đạt `child_chunk_size`.

Dataclass gợi ý:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ChildUnit:
    content: str
    block_type: str
    page_start: int
    page_end: int
    item_marker: str | None
    item_level: int | None
    item_path: list[str]
    logical_item_key: str | None
    parent_item_key: str | None
    logical_table_key: str | None = None
    logical_code_key: str | None = None
    legal_unit_type: str
    split_index: int = 0
    split_count: int = 1
```

Rule cho item:

```text
numbered_item, lettered_item, bullet_item luon tao it nhat mot Child rieng.
Item ngan va item ket thuc bang ":" van tao Child.
Item cha co item con van tao Child rieng; item con tao Child rieng.
Item con link ve item cha bang parent_item_key.
Child item cha khong gom noi dung item con.
Khong gop hai marker khac nhau vao cung mot Child.
```

`item_path` lấy xác định từ dòng item gốc:

```python
MAX_ITEM_LABEL_LENGTH = 120


def item_path_label(block: StructuralBlock) -> str:
    marker = block.item_marker or ""
    text = strip_item_marker(block.raw_content, marker).strip()
    label = f"{marker} {text}".strip()
    if len(label) <= MAX_ITEM_LABEL_LENGTH:
        return label
    return label[: MAX_ITEM_LABEL_LENGTH - 3].rstrip() + "..."
```

Rule:

```text
Giu marker va nhan ngan trong item_path.
Khong chi luu marker.
Khong dung LLM de tom tat.
Khong dua toan bo noi dung dai cua item cha vao item_path.
```

Recursive splitter chỉ dùng cho một unit quá dài:

```python
def build_child_splitter(
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )
```

Build child units:

```python
def build_structural_child_units(section: ParentSection) -> tuple[list[ChildUnit], list[ValidationReport]]:
    units: list[ChildUnit] = []
    reports: list[ValidationReport] = []
    current: ChildUnit | None = None
    item_stack: list[StructuralBlock] = []

    for block in section.blocks:
        if block.block_type == "heading":
            current = None
            item_stack = []
            continue

        if block.block_type in {"numbered_item", "lettered_item", "bullet_item"}:
            if current:
                units.append(current)
            item_stack = close_deeper_or_same_level_items(item_stack, block)
            parent_item = item_stack[-1] if item_stack else None
            item_stack.append(block)
            current = child_unit_from_item(block, parent_item_key=get_item_key(parent_item))
            continue

        if block.block_type in {"table", "code"}:
            if current:
                units.append(current)
                current = None
            parent_item = item_stack[-1] if item_stack else None
            units.append(
                child_unit_from_block(
                    block,
                    section.heading_path,
                    item_path=build_item_path(item_stack),
                    parent_item_key=get_item_key(parent_item),
                )
            )
            continue

        if block.block_type == "paragraph":
            if current:
                current = append_block_to_unit(current, block)
            else:
                # Sau table/code, paragraph vẫn có thể thuộc item đang mở về mặt
                # cấu trúc nhưng phải là paragraph Child riêng, không mở lại Child cũ.
                parent_item = item_stack[-1] if item_stack else None
                units.append(
                    child_unit_from_block(
                        block,
                        section.heading_path,
                        item_path=build_item_path(item_stack),
                        parent_item_key=get_item_key(parent_item),
                    )
                )

    if current:
        units.append(current)

    if not units:
        heading = first_heading_block(section.blocks)
        if heading and is_normative_or_independent_heading(heading):
            units.append(make_heading_content_unit(heading, section))
        else:
            reports.append(
                ValidationReport(
                    severity="warning",
                    code="context_only_parent",
                    reason="Parent has no child content; heading is context-only",
                    page=section.page_start,
                    raw_content=heading.raw_content if heading else "",
                    current_heading_path=section.heading_path,
                    current_item_path=[],
                    selected_owner=section.heading_path,
                    candidate_owners=[section.heading_path],
                    candidate_types=["context_only"],
                    selected_type="context_only",
                    confidence=1.0,
                )
            )

    return units, reports


def build_child_units(
    section: ParentSection,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> tuple[list[ChildUnit], list[ValidationReport]]:
    units, reports = build_structural_child_units(section)
    result: list[ChildUnit] = []

    for unit in units:
        if unit.block_type == "table":
            result.extend(split_table_child_unit(unit, child_chunk_size=child_chunk_size))
            continue

        if unit.block_type == "code":
            result.extend(split_code_child_unit(unit, child_chunk_size=child_chunk_size))
            continue

        if len(unit.content) > child_chunk_size:
            result.extend(
                split_long_child_unit(
                    unit,
                    child_chunk_size=child_chunk_size,
                    child_chunk_overlap=child_chunk_overlap,
                )
            )
            continue

        result.append(unit)

    return result, reports
```

Post-scan fallback:

```text
Normative/independent heading with no children -> create heading_content Child and embed it.
Context-only heading -> do not create fake content; emit explicit context_only_reason/report.
Every Parent must have at least one Child or an explicit context_only_reason.
```

Paragraph rule:

```text
Paragraph sau item gan vao Child hien tai.
Dung khi gap heading moi hoac bat ky item moi.
Neu item moi co cap thap hon thi thanh item con.
Page marker khong lam ket thuc item va khong lam mat item_path.
Paragraph khong thuoc item nao tao paragraph Child trong Parent hien tai.
Neu khong ro paragraph thuoc item cuoi hay item cha, dung fallback bao thu va ghi ValidationReport warning/error tuy muc do.
```

Lý do dùng `ParentSection`:

```text
StructuralParser chi chay mot lan o chunk_markdown_body().
ParentSection giu blocks da parse san.
Child builder dung section.blocks, khong parse lai parent_chunk.content.
Flow dung:
PageBlock[] -> StructuralParseResult -> ParentSection.blocks -> ChildUnit -> child Chunks
```

Lưu ý về table:

```text
RecursiveCharacterTextSplitter khong hieu semantic table cua du an.
Phai detect table truoc item regex va truoc recursive splitter.
Table ngan thanh 1 child chunk rieng.
Table dai split theo row group va lap lai header/separator.
```

---

## 10.1 Split Fenced Code Dài

Fenced code là atomic structural unit. Chỉ khi vượt giới hạn cứng mới split theo ranh giới dòng; không dùng `RecursiveCharacterTextSplitter`.

```python
from dataclasses import replace


def split_code_child_unit(
    unit: ChildUnit,
    *,
    child_chunk_size: int,
) -> list[ChildUnit]:
    if len(unit.content) <= child_chunk_size:
        return [unit]

    # parse_fenced_code() preserves the original fence token/length and language tag.
    opening_fence, language, body_lines, closing_fence = parse_fenced_code(unit.content)
    groups = group_complete_lines(
        body_lines,
        max_size=child_chunk_size - len(opening_fence) - len(closing_fence) - 2,
    )
    split_count = len(groups)

    return [
        replace(
            unit,
            content="\n".join([
                f"{opening_fence}{language}",
                *group,
                closing_fence,
            ]),
            split_index=index,
            split_count=split_count,
        )
        for index, group in enumerate(groups)
    ]
```

Contract:

```text
- Không cắt giữa một dòng.
- Mỗi split giữ opening/closing fence và là fenced Markdown hợp lệ.
- Các split dùng chung logical_code_key.
- Marker heading/item bên trong code không được parse lại.
- split_index bắt đầu từ 0 và split_count giống nhau trong cả group.
```

---

## 11. Tạo Child Chunks

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

```python
def make_child_chunks(
    *,
    child_units: list[ChildUnit],
    parent_chunk: Chunk,
    document_key: str,
    version_key: str,
    child_start_index: int,
    chunk_start_index: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for offset, unit in enumerate(child_units):
        child_number = child_start_index + offset

        chunks.append(
            Chunk(
                document_key=document_key,
                version_key=version_key,
                chunk_key=f"{version_key}::c::{child_number:04d}",
                parent_chunk_key=parent_chunk.chunk_key,
                chunk_type="child",
                content=unit.content,
                heading_path=parent_chunk.heading_path,
                page_start=unit.page_start,
                page_end=unit.page_end,
                chunk_index=chunk_start_index + offset,
                token_count=count_units(unit.content),
                metadata={
                    "item_marker": unit.item_marker,
                    "item_level": unit.item_level,
                    "item_path": unit.item_path,
                    "logical_item_key": unit.logical_item_key,
                    "parent_item_key": unit.parent_item_key,
                    "logical_table_key": unit.logical_table_key,
                    "logical_code_key": unit.logical_code_key,
                    "legal_unit_type": unit.legal_unit_type,
                    "block_type": unit.block_type,
                    "split_index": unit.split_index,
                    "split_count": unit.split_count,
                },
            )
        )
    return chunks
```

Lý do `make_child_chunks()` không cần `section`:

```text
build_child_units(section) da tao ChildUnit tu section.blocks.
parent_chunk la Chunk cha chinh thuc da tao tu ParentSection.
make_child_chunks chi can parent_chunk de lay:
- parent_chunk.chunk_key lam parent_chunk_key
- parent_chunk.heading_path
- parent_chunk.page_start/page_end lam fallback khi structural unit thieu page
```

Khong parse lai parent_chunk.content trong child_builder.

---

## 12. Hàm Core `chunk_markdown_body`

File:

```text
chatbot/backend/app/ingestion/chunking/chunker.py
```

Suggested pattern:

```python
from app.ingestion.chunking.child_chunker import (
    build_child_units,
    make_child_chunks,
)
from app.ingestion.chunking.parent_chunker import (
    build_parent_sections,
    make_parent_chunk,
)
from app.ingestion.parsing.page_markers import split_body_by_page_markers
from app.ingestion.parsing.structural_parser import parse_page_blocks


DEFAULT_CHILD_CHUNK_SIZE = 1000
DEFAULT_CHILD_CHUNK_OVERLAP = 100


def chunk_markdown_body(
    *,
    body: str,
    document_key: str,
    version_key: str,
    child_chunk_size: int = DEFAULT_CHILD_CHUNK_SIZE,
    child_chunk_overlap: int = DEFAULT_CHILD_CHUNK_OVERLAP,
) -> ChunkingResult:
    if not body.strip():
        raise ValueError("Markdown body is empty")

    page_blocks = split_body_by_page_markers(body)
    parse_result = parse_page_blocks(page_blocks)
    sections = build_parent_sections(parse_result.blocks)
    parent_chunks: list[Chunk] = []
    child_chunks: list[Chunk] = []
    child_reports: list[ValidationReport] = []
    child_counter = 1
    chunk_index = 0

    for parent_counter, section in enumerate(sections, start=1):
        parent = make_parent_chunk(
            section=section,
            document_key=document_key,
            version_key=version_key,
            parent_index=parent_counter,
            chunk_index=chunk_index,
        )
        parent_chunks.append(parent)
        chunk_index += 1

        child_units, section_reports = build_child_units(
            section,
            child_chunk_size=child_chunk_size,
            child_chunk_overlap=child_chunk_overlap,
        )
        child_reports.extend(section_reports)
        children = make_child_chunks(
            child_units=child_units,
            parent_chunk=parent,
            document_key=document_key,
            version_key=version_key,
            child_start_index=child_counter,
            chunk_start_index=chunk_index,
        )
        child_chunks.extend(children)
        child_counter += len(children)
        chunk_index += len(children)

    return ChunkingResult(
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
        warnings=[
            report for report in [*parse_result.reports, *child_reports]
            if report.severity == "warning"
        ],
        errors=[
            report for report in [*parse_result.reports, *child_reports]
            if report.severity == "error"
        ],
    )
```

Trong production caller, truyền `child_chunk_size` và `child_chunk_overlap` từ `get_rag_settings().chunking`. Function vẫn có default để test/unit call đơn giản, nhưng không rải magic number ở pipeline.

---

## 13. Test Cần Có

File:

```text
chatbot/backend/test/ingestion/test_chunker.py
```

Test fixture:

```python
SAMPLE_BODY = """<!-- page: 1 -->

# Tai lieu mau

## Chuong I

### Dieu 1. Pham vi

Noi dung dieu 1.

| Cot A | Cot B |
|---|---|
| A | B |

<!-- page: 2 -->

### Dieu 2. Doi tuong

Noi dung dieu 2.
"""
```

Tests:

```python
from app.ingestion.chunking.chunker import chunk_markdown_body


def all_chunks(result):
    return [*result.parent_chunks, *result.child_chunks]


def test_chunker_creates_parent_and_child():
    result = chunk_markdown_body(
        body=SAMPLE_BODY,
        document_key="doc",
        version_key="doc-v1",
    )
    chunks = all_chunks(result)

    assert any(chunk.chunk_type == "parent" for chunk in chunks)
    assert any(chunk.chunk_type == "child" for chunk in chunks)


def test_child_chunks_have_parent_key():
    chunks = all_chunks(chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1"))
    parent_keys = {chunk.chunk_key for chunk in chunks if chunk.chunk_type == "parent"}

    for chunk in chunks:
        if chunk.chunk_type == "child":
            assert chunk.parent_chunk_key in parent_keys


def test_chunker_uses_stable_key_pattern():
    chunks = all_chunks(chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1"))

    assert any(chunk.chunk_key.startswith("doc-v1::p::") for chunk in chunks)
    assert any(chunk.chunk_key.startswith("doc-v1::c::") for chunk in chunks)


def test_chunk_index_is_global_sequential():
    chunks = all_chunks(chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1"))

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunker_tracks_heading_path():
    chunks = all_chunks(chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1"))
    assert any("Dieu 1. Pham vi" in chunk.heading_path for chunk in chunks)


def test_chunker_tracks_page_range():
    chunks = all_chunks(chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1"))
    assert any(chunk.page_start == 1 for chunk in chunks)


def test_chunker_keeps_page_marker_before_heading():
    body = """<!-- page: 1 -->

# Title

Content on page 1.
"""
    chunks = all_chunks(chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1"))

    assert chunks
    assert all(chunk.page_start == 1 and chunk.page_end == 1 for chunk in chunks)


def test_chunker_rejects_empty_body():
    with pytest.raises(ValueError):
        chunk_markdown_body(body="", document_key="doc", version_key="doc-v1")


def test_chunker_rejects_missing_page_marker():
    with pytest.raises(ValueError):
        chunk_markdown_body(
            body="# Title\n\nNo page marker.",
            document_key="doc",
            version_key="doc-v1",
        )
```

Table test:

```python
def test_chunker_keeps_small_table_as_one_child_chunk():
    chunks = all_chunks(chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1"))
    table_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_type == "child" and "| Cot A | Cot B |" in chunk.content
    ]

    assert len(table_chunks) == 1
    assert "|---|---|" in table_chunks[0].content
    assert "| A | B |" in table_chunks[0].content
```

Với table lớn hơn `child_chunk_size`, test phải assert mỗi child table vẫn có header + separator:

```python
def test_large_table_chunks_repeat_header_and_separator():
    ...
    table_chunks = [...]

    assert len(table_chunks) > 1
    for chunk in table_chunks:
        assert "| Cot A | Cot B |" in chunk.content
        assert "|---|---|" in chunk.content
```

Item hierarchy tests:

```python
def test_parent_item_with_colon_still_creates_child():
    body = """<!-- page: 1 -->

# Title

1. Ho so gom:
a) Don dang ky.
"""
    chunks = all_chunks(chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1"))
    child_chunks = [chunk for chunk in chunks if chunk.chunk_type == "child"]

    assert any(chunk.content.startswith("1. Ho so gom:") for chunk in child_chunks)
    assert any(chunk.content.startswith("a) Don dang ky.") for chunk in child_chunks)


def test_child_item_has_parent_item_key_and_full_item_path_label():
    body = """<!-- page: 1 -->

# Title

1. Ho so gom:
a) Don dang ky.
"""
    chunks = all_chunks(chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1"))
    point = next(chunk for chunk in chunks if chunk.content.startswith("a) Don dang ky."))
    metadata = point.metadata or {}

    assert metadata["parent_item_key"]
    assert metadata["item_path"] == ["1. Ho so gom:", "a) Don dang ky."]


def test_parent_item_child_does_not_include_nested_item_content():
    body = """<!-- page: 1 -->

# Title

1. Ho so gom:
a) Don dang ky.
"""
    chunks = all_chunks(chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1"))
    parent_item = next(chunk for chunk in chunks if chunk.content.startswith("1. Ho so gom:"))

    assert "a) Don dang ky." not in parent_item.content


def test_split_long_item_keeps_logical_item_metadata():
    long_text = " ".join(f"noi-dung-{index}" for index in range(240))
    body = f"""<!-- page: 1 -->

# Title

1. {long_text}
2. Item tiep theo khong duoc bi tron vao item 1.
"""
    chunks = all_chunks(chunk_markdown_body(
        body=body,
        document_key="doc",
        version_key="doc-v1",
        child_chunk_size=100,
        child_chunk_overlap=10,
    ))
    item_chunks = [chunk for chunk in chunks if (chunk.metadata or {}).get("logical_item_key")]
    keys = {(chunk.metadata or {})["logical_item_key"] for chunk in item_chunks}

    assert len(keys) == 1
    assert len(item_chunks) > 1
    assert all((chunk.metadata or {})["split_count"] == len(item_chunks) for chunk in item_chunks)
    assert [chunk.metadata["split_index"] for chunk in item_chunks] == list(range(len(item_chunks)))
    assert all("2. Item tiep theo" not in chunk.content for chunk in item_chunks)
    assert any(chunk.content.startswith("2. Item tiep theo") for chunk in chunks)
```

Fenced code atomic-child test:

````python
def test_fenced_code_is_atomic_child_and_not_item_content():
    body = """<!-- page: 1 -->

# Title

1. Huong dan:

```text
1. marker trong code
a) marker trong code
```

Noi dung sau code.
"""
    chunks = all_chunks(chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1"))
    code_chunks = [
        chunk for chunk in chunks
        if chunk.chunk_type == "child" and (chunk.metadata or {}).get("block_type") == "code"
    ]
    parent_item = next(chunk for chunk in chunks if chunk.content.startswith("1. Huong dan:"))

    assert len(code_chunks) == 1
    assert "1. marker trong code" in code_chunks[0].content
    assert "1. marker trong code" not in parent_item.content
````

Structural parser/chunker tests bắt buộc:

```text
1. Danh sách 5 mục dưới một heading tạo 1 parent và 5 child.
2. Item không bị convert thành heading.
3. `### 1. Mục đích` vẫn là heading.
4. `### 1) Phạm vi` vẫn là heading.
5. `### a) Đối tượng` vẫn là heading.
6. `### - Nội dung` vẫn là heading.
7. Markdown heading không bị demote thành numbered_item/lettered_item/bullet_item.
8. Điều -> Khoản -> Điểm -> Bullet tạo đúng item_path.
9. Paragraph được gắn đúng item hoặc sinh ValidationReport warning.
10. Item con kế thừa context cha.
11. Item cha kết thúc bằng ":" vẫn tạo child riêng.
12. Item cha có item con không chứa nội dung item con.
13. Item con có parent_item_key.
14. item_path giữ marker và nhãn ngắn, không chỉ lưu marker.
15. Bullet -, +, * tạo atomic child.
16. Item quá dài chỉ split nội bộ và giữ logical_item_key.
17. Split child có split_index/split_count.
18. Không child nào chứa nội dung của hai item khác nhau.
19. Marker trong table/code không bị parse thành item.
20. Nội dung trước heading đầu tiên thuộc document-root parent.
21. Table/code trong item kế thừa đúng context.
22. Child ngắn có embedding_text chứa context thật.
23. Page marker/HTML comment không bị đưa vào embedding_text.
```

---

## 14. Lệnh Test

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_chunker.py
```

---

## 15. Done Khi

- [ ] Có dependency `langchain-text-splitters`.
- [ ] Chunker không mất nội dung body.
- [ ] Parent chunk không có `parent_chunk_key`.
- [ ] Child chunk có `parent_chunk_key` là stable parent key.
- [ ] `chunk_key` theo pattern `<version_key>::p/c::<0001>`.
- [ ] `chunk_index` global sequential trong version.
- [ ] `heading_path` được gán theo Markdown headers.
- [ ] Mọi chunk đều có `page_start`, `page_end`, `token_count`.
- [ ] `page_start <= page_end`.
- [ ] Small table thành đúng một child chunk riêng.
- [ ] Large table nếu bị split thì mỗi child table có header + separator.
- [ ] Test chunker pass.

---

## 16. Lỗi Dễ Gặp

### Lỗi: import langchain sai

Nguyên nhân:

```text
Dung import cu `from langchain.text_splitter import ...`
```

Xử lý:

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

### Lỗi: child chunk parent id không tồn tại

Nguyên nhân:

```text
parent_chunk_key bi set bang DB id truoc khi insert DB.
```

Xử lý:

```text
Trong chunker chi dung stable parent key.
Repository moi map stable key sang DB id.
```

### Lỗi: unique constraint chunk_index

Nguyên nhân:

```text
chunk_index reset rieng cho parent va child.
```

Xử lý:

```text
Dung chunk_index global sequential cho tat ca parent + child chunks trong cung version.
```

### Lỗi: table bị split

Nguyên nhân:

```text
Recursive splitter cat theo character/paragraph, khong hieu semantic table.
```

Xử lý MVP:

```text
Tang child_chunk_size va them test small table.
Neu van khong du, implement protect table blocks truoc khi split.
```

## 19. Reconciliation Contract Bắt Buộc

Các rule dưới đây ghi đè pseudocode cũ nếu có mâu thuẫn:

```text
1. Mỗi Markdown heading mở Parent mới; Parent cũ đóng ngay trước heading tiếp theo.
2. Không merge hai Parent có hai source heading khác nhau.
3. Parent không body nhưng heading chứa nội dung độc lập tạo heading_content Child nguyên văn.
4. Heading context như Chương/Phần/Mục có thể context_only; mọi Parent phải có Child hoặc context_only_reason.
5. Cặp "Chương I" + "TÊN CHƯƠNG" liên tiếp giữ derived heading_path kết hợp, không sửa raw Markdown.
6. Table và fenced code luôn là atomic Child riêng; không append vào Child item.
7. Table dài split theo row group và lặp header; code dài split theo dòng, giữ fence hợp lệ và logical_code_key.
8. legal_unit_type chỉ gán khi có legal context, không suy ra chỉ từ marker.
9. Validation report có severity; warning không block publish, error mới block theo mặc định.
10. Chunk.metadata là metadata trong memory; không đồng nghĩa đã persist PostgreSQL.
```

`embedding_text` của item con prepend `heading_path` và ancestor item labels (`item_path[:-1]`).
Không lặp current label vì raw content đã chứa item hiện tại.
